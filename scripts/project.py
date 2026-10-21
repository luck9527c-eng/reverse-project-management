#!/usr/bin/env python3
"""Initialize and validate a repository's reverse-engineering management records.

Only init/index/probe --output write files. No command launches analysis tools,
executes targets, installs packages, or changes global configuration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import shutil
import sys
import tempfile
from urllib.parse import quote
from impact import (CONDITION_STATES, REVIEW_OUTCOMES, affected_routes,
                    impact_report, read_records, report_for_project)
from governance import audit_scope, management_summary, validate_management
from integrity import checked_path, seal_run, verify_seals, write_new

SKILL = Path(__file__).resolve().parent.parent
NAME = "reverse-project-management"
LOCAL_SKILL = f".agents/skills/{NAME}"
PROJECT_CONFIG = "docs/agents/reverse-project-management.md"
START, END = "<!-- RPM:NAV:START -->", "<!-- RPM:NAV:END -->"
STATES = {"planned", "active", "blocked", "paused", "validated", "falsified", "superseded"}
RUN_STATES = {"planned", "running", "completed", "failed", "timed_out", "cancelled", "interrupted"}
TERMINAL_RUNS = RUN_STATES - {"planned", "running"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIERS = {"route": re.compile(r"R-[A-Za-z0-9_-]+\Z"),
               "target": re.compile(r"T-[A-Za-z0-9_-]+\Z"),
               "run": re.compile(r"RUN-[A-Za-z0-9_-]+\Z"),
               "condition": re.compile(r"C-[A-Za-z0-9_-]+\Z")}


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def save_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def local_file(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("empty project-relative file reference")
    if Path(relative).is_absolute() or PureWindowsPath(relative).drive:
        raise ValueError(f"expected project-relative path: {relative}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes project: {relative}")
    if not resolved.is_file():
        raise ValueError(f"missing file: {relative}")
    return resolved


def link(root, path):
    rel = path.relative_to(root).as_posix()
    label = rel.replace("|", "&#124;").replace("[", "&#91;").replace("]", "&#93;")
    return f"[{label}]({quote(rel, safe='/.-_~')})"


def inventory(root):
    lines = ["", "| 类别 | 权威记录 |", "|---|---|"]
    groups = [
        ("仓库配置", [root / PROJECT_CONFIG]),
        ("项目规则", [root / LOCAL_SKILL / "SKILL.md"]),
        ("目标", [root / "re/targets.json"]),
        ("项目验收/审计/争议", [root / "re/project.json"]),
        ("环境", sorted((root / "re/env").glob("*.json"))),
        ("共享条件", sorted((root / "re/conditions").glob("*.json"))),
        ("路线", sorted((root / "re/routes").glob("*.json"))),
        ("运行/证据", sorted((root / "re/runs").glob("*/run.json"))),
        ("封存基线", sorted((root / "re/seals").rglob("*.json"))),
        ("专题文档", sorted(p for p in (root / "re/docs").rglob("*") if p.is_file())),
        ("复用脚本", sorted(p for p in (root / "re/scripts").rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts)),
    ]
    for kind, paths in groups:
        for path in paths:
            if path.is_file():
                lines.append(f"| {kind} | {link(root, path)} |")
    lines.extend(["", "### 待复查与重验", ""])
    reviews = report_for_project(root)["pending_reviews"]
    if reviews:
        lines.extend(["| 条件/版本 | 路线（原状态保留） | 影响关系 | 复查进度 |", "|---|---|---|---|"])
        for item in reviews:
            condition = link(root, root / f"re/conditions/{item['condition_id']}.json")
            route = link(root, root / f"re/routes/{item['route_id']}.json")
            lines.append(f"| {condition} r{item['revision']} | {route} ({item['route_status']}) | "
                         f"{item['relation']} | {item['review_outcome']} |")
    else:
        lines.append("当前已登记条件没有待处理复查；未登记的关联仍需 agent 识别。")
    summary = management_summary(root)
    lines.extend(["", "### 项目验收与未闭合事项", ""])
    if summary["legacy"]:
        lines.append("缺少项目验收记录；接管时补建 re/project.json。")
    else:
        lines.append("验收待办：" + (", ".join(summary["acceptance_pending"]) or "无已登记待办；仍需完成检查"))
    lines.append("阶段关联审计：" + ("待执行或范围已变化（包含未关联的历史路线）" if summary["audit_pending"] else "已覆盖当前登记范围"))
    lines.append("实验恢复待办：" + (", ".join(summary["recovery_pending"]) or "无已登记待办"))
    for dispute in summary["open_disputes"]:
        severity = "阻止完成" if dispute["critical"] else "交接披露"
        lines.append(f"- {dispute['id']}：有争议；路线 {', '.join(dispute['route_ids'])}；{severity}，见 re/project.json。")
    for item in summary["dispute_impacts"]:
        lines.append(f"- 争议复查 {item['dispute_id']} → {item['route_id']}：{item['relation']}；历史状态 {item['route_status']} 保留，当前结论不可作为可靠前提。")
    lines.append("")
    return "\n".join(lines)


def index_parts(root):
    text = (root / "INDEX.md").read_text(encoding="utf-8-sig")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("INDEX requires exactly one navigation marker pair")
    prefix, rest = text.split(START)
    content, suffix = rest.split(END)
    return prefix, content, suffix


def refresh(root):
    root = root.resolve()
    checked_path(root, root / "INDEX.md")
    prefix, _, suffix = index_parts(root)
    value = prefix + START + inventory(root) + END + suffix
    # Replace only the mutable index, never an experiment artifact.
    handle, temporary = tempfile.mkstemp(prefix=".rpm-index-", dir=root)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        os.replace(temporary, root / "INDEX.md")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize(root):
    destination = root / LOCAL_SKILL
    config = root / PROJECT_CONFIG
    if root == SKILL.parent or root == SKILL or root.is_relative_to(SKILL):
        raise ValueError("initialize a concrete analysis repository, not the shared skill directory")
    if not destination.resolve().is_relative_to(root):
        raise ValueError("repository skill destination resolves outside project")
    if not config.resolve().is_relative_to(root):
        raise ValueError("repository config destination resolves outside project")
    for path in (root / "INDEX.md", root / "re", destination, config):
        checked_path(root, path)
        if os.path.lexists(path):
            raise ValueError(f"refusing initialization over existing path: {path}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"project root is not a directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    for directory in ("docs", "scripts", "routes", "runs", "env", "conditions"):
        (root / "re" / directory).mkdir(parents=True, exist_ok=True)
    write_new(root, root / "INDEX.md", (SKILL / "assets/INDEX.md").read_bytes())
    config.parent.mkdir(parents=True, exist_ok=True)
    write_new(root, config, (SKILL / "assets/project-management.md").read_bytes())
    save_new(root / "re/targets.json", {"schema_version": 1, "targets": []})
    write_new(root, root / "re/project.json", (SKILL / "assets/project.json").read_bytes())
    refresh(root)


def timestamp(value, context):
    if not isinstance(value, str):
        raise ValueError(f"{context}: timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{context}: timestamp requires timezone")
    return parsed


def require_text(record, keys, context):
    for key in keys:
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"{context}: missing {key}")


def identifier(value, kind):
    if not isinstance(value, str) or not IDENTIFIERS[kind].fullmatch(value):
        raise ValueError(f"invalid {kind} ID: {value}")
    return value


def string_list(record, key, context):
    value = record.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{context}: {key} must be a list of strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{context}: duplicate {key}")
    return value


def check_hash(value, context):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError(f"{context}: expected lowercase SHA256")


def validate(root, hashes, complete=False, allow_unsealed=False, check_index=True):
    if check_index:
        _, nav, _ = index_parts(root)
        if nav != inventory(root):
            raise ValueError("INDEX navigation stale; run index")
    manifest = load(root / "re/targets.json")
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("targets"), list):
        raise ValueError("targets.json: unsupported schema")
    targets = {}
    for target in manifest["targets"]:
        key = identifier(target.get("id"), "target")
        if key in targets:
            raise ValueError(f"duplicate target: {key}")
        require_text(target, ("path", "version", "platform", "arch", "source"), key)
        check_hash(target.get("sha256"), key)
        if hashes:
            path = Path(target["path"])
            if not path.is_absolute():
                path = root / path
            if digest(path) != target["sha256"]:
                raise ValueError(f"{key}: target hash mismatch")
        targets[key] = target

    routes = {}
    for path in sorted((root / "re/routes").glob("*.json")):
        route = load(path)
        key = identifier(route.get("id"), "route")
        if path.stem != key or key in routes or route.get("schema_version") != 1:
            raise ValueError(f"{path}: route identity/schema mismatch")
        if route.get("status") not in STATES:
            raise ValueError(f"{key}: invalid status")
        require_text(route, ("question", "hypothesis", "state_reason"), key)
        target_ids = string_list(route, "target_ids", key)
        if not target_ids or any(item not in targets for item in target_ids):
            raise ValueError(f"{key}: missing/unknown targets")
        for field in ("depends_on", "evidence"):
            string_list(route, field, key)
        require_text(route.get("experiment", {}), ("action", "expected", "falsifier"), key)
        require_text(route.get("budget", {}), ("limit", "stop_when"), key)
        if route["status"] in {"blocked", "paused"}:
            require_text(route, ("resume_when",), key)
        history = route.get("history")
        if not isinstance(history, list) or not history:
            raise ValueError(f"{key}: history required")
        previous, last_time = None, None
        for event in history:
            moment = timestamp(event.get("at"), key)
            if last_time and moment < last_time:
                raise ValueError(f"{key}: history time went backwards")
            if event.get("from") != previous or event.get("to") not in STATES:
                raise ValueError(f"{key}: broken history chain")
            require_text(event, ("reason",), key)
            string_list(event, "evidence", key)
            if previous in {"validated", "falsified", "superseded"}:
                if not event.get("prior_closure"):
                    raise ValueError(f"{key}: reclassification/reopen needs prior_closure")
            previous, last_time = event["to"], moment
        if previous != route["status"]:
            raise ValueError(f"{key}: history/status mismatch")
        routes[key] = route

    visiting, visited = set(), set()

    def visit(key):
        if key in visiting:
            raise ValueError(f"dependency cycle involving {key}")
        if key in visited:
            return
        visiting.add(key)
        for parent in routes[key]["depends_on"]:
            if parent not in routes:
                raise ValueError(f"{key}: unknown dependency {parent}")
            visit(parent)
            if routes[key]["status"] in {"active", "validated", "falsified"}:
                if routes[parent]["status"] != "validated":
                    raise ValueError(f"{key}: dependency {parent} not validated")
        visiting.remove(key)
        visited.add(key)

    for key in routes:
        visit(key)

    runs = {}
    for path in sorted((root / "re/runs").glob("*/run.json")):
        run = load(path)
        key = identifier(run.get("id"), "run")
        if path.parent.name != key or key in runs or run.get("schema_version") != 1:
            raise ValueError(f"{path}: run identity/schema mismatch")
        if run.get("status") not in RUN_STATES:
            raise ValueError(f"{key}: invalid run status")
        route = routes.get(run.get("route_id"))
        target = run.get("target", {})
        target_id = target.get("id")
        if not route or target_id not in route["target_ids"]:
            raise ValueError(f"{key}: unknown route or route/target mismatch")
        if target.get("sha256") != targets[target_id]["sha256"]:
            raise ValueError(f"{key}: target hash does not match manifest")
        if run["status"] != "planned":
            timestamp(run.get("started_at"), key)
            require_text(run, ("command", "cwd"), key)
        if run["status"] in TERMINAL_RUNS:
            end = timestamp(run.get("ended_at"), key)
            if end < timestamp(run["started_at"], key):
                raise ValueError(f"{key}: end precedes start")
            require_text(run, ("result",), key)
            if not isinstance(run.get("tools"), list) or not run["tools"]:
                raise ValueError(f"{key}: tools with versions required")
            for tool in run["tools"]:
                require_text(tool, ("name", "version"), key)
            environment = run.get("environment", {})
            snapshot = local_file(root, environment.get("snapshot"))
            check_hash(environment.get("snapshot_sha256"), f"{key}/environment")
            if hashes and digest(snapshot) != environment["snapshot_sha256"]:
                raise ValueError(f"{key}: environment snapshot hash mismatch")
            if not isinstance(run.get("artifacts"), list) or not run["artifacts"]:
                raise ValueError(f"{key}: terminal run needs retained artifacts")
            if run["status"] == "completed":
                accepted = run.get("accepted_exit_codes", [0])
                if (not isinstance(accepted, list) or not accepted or
                        any(type(code) is not int for code in accepted) or
                        type(run.get("exit_code")) is not int or run["exit_code"] not in accepted):
                    raise ValueError(f"{key}: completed run has unaccepted exit code")
        for field in ("scripts", "artifacts"):
            if not isinstance(run.get(field), list):
                raise ValueError(f"{key}: {field} must be a list")
            for item in run[field]:
                file = local_file(root, item.get("path"))
                check_hash(item.get("sha256"), f"{key}/{field}")
                if hashes and digest(file) != item["sha256"]:
                    raise ValueError(f"{key}: artifact/script hash mismatch: {item['path']}")
        runs[key] = run

    def evidence_refs(values, route, context, completed=False):
        for run_id in values:
            identifier(run_id, "run")
            if run_id not in runs or runs[run_id]["target"]["id"] not in route["target_ids"]:
                raise ValueError(f"{context}: missing or mismatched evidence {run_id}")
            if completed and runs[run_id]["status"] != "completed":
                raise ValueError(f"{context}: closure needs completed evidence {run_id}")

    for key, route in routes.items():
        evidence_refs(route["evidence"], route, key)
        for event in route["history"]:
            evidence_refs(event["evidence"], route, key)
        status, closure = route["status"], route.get("closure")
        if status in {"validated", "falsified"}:
            if not isinstance(closure, dict):
                raise ValueError(f"{key}: closure required for {status}")
            fields = ["summary", "scope"]
            if status == "falsified":
                fields += ["criterion", "coverage", "control", "limitations", "reopen_when"]
            require_text(closure, fields, f"{key}/closure")
            if "limitations" not in closure:
                raise ValueError(f"{key}: closure limitations required")
            refs = string_list(closure, "evidence", key)
            if not refs or any(item not in route["evidence"] for item in refs):
                raise ValueError(f"{key}: closure needs registered evidence")
            evidence_refs(refs, route, key, completed=True)
            if status == "falsified":
                for field in ("observation_refs", "control_refs"):
                    locators = closure.get(field)
                    if not isinstance(locators, list) or not locators:
                        raise ValueError(f"{key}: falsification needs observation/control references ({field})")
                    for locator in locators:
                        run_id = locator.get("run_id")
                        if run_id not in route["evidence"]:
                            raise ValueError(f"{key}: observation/control run not registered")
                        evidence_refs([run_id], route, key, completed=True)
                        observation = runs[run_id].get("observation", {})
                        require_text(observation, ("trigger", "window", "coverage", "control"), f"{key}/observation")
                        if observation.get("chain_status") != "passed":
                            raise ValueError(f"{key}: observation chain not passed")
                        if field == "observation_refs" and run_id not in refs:
                            raise ValueError(f"{key}: observation run not in closure evidence")
                        require_text(locator, ("path", "locator"), f"{key}/observation")
                        if locator["path"] not in {a["path"] for a in runs[run_id]["artifacts"]}:
                            raise ValueError(f"{key}: observation/control artifact not registered")
        if status == "superseded":
            if not isinstance(closure, dict):
                raise ValueError(f"{key}: superseded closure required")
            replacement = closure.get("replacement")
            if replacement == key or replacement not in routes:
                raise ValueError(f"{key}: unknown replacement route")
            require_text(closure, ("summary",), key)
    conditions, _ = read_records(root)
    for key, condition in conditions.items():
        identifier(key, "condition")
        if condition.get("schema_version") != 1:
            raise ValueError(f"{key}: unsupported condition schema")
        require_text(condition, ("statement", "scope"), key)
        target_ids = string_list(condition, "target_ids", key)
        if any(target_id not in targets for target_id in target_ids):
            raise ValueError(f"{key}: unknown condition target")
        revision = condition.get("revision")
        history = condition.get("history")
        if (type(revision) is not int or revision < 1 or not isinstance(history, list)
                or len(history) != revision):
            raise ValueError(f"{key}: condition revision/history mismatch")
        evidence = string_list(condition, "evidence", key)

        def condition_evidence(values, state):
            if state not in CONDITION_STATES:
                raise ValueError(f"{key}: invalid condition state")
            if state != "unknown" and not values:
                raise ValueError(f"{key}: known state needs condition evidence")
            for run_id in values:
                identifier(run_id, "run")
                run = runs.get(run_id)
                if not run or (target_ids and run["target"]["id"] not in target_ids):
                    raise ValueError(f"{key}: missing/mismatched condition evidence {run_id}")
                if state != "unknown" and run["status"] not in TERMINAL_RUNS:
                    raise ValueError(f"{key}: condition evidence has not finished")
                if state == "satisfied" and run["status"] != "completed":
                    raise ValueError(f"{key}: satisfied condition needs completed evidence")

        condition_evidence(evidence, condition.get("state"))
        last_time = None
        for expected, event in enumerate(history, 1):
            if type(event.get("revision")) is not int or event["revision"] != expected:
                raise ValueError(f"{key}: condition history revision gap")
            moment = timestamp(event.get("at"), key)
            if last_time and moment < last_time:
                raise ValueError(f"{key}: condition history time went backwards")
            require_text(event, ("reason",), key)
            condition_evidence(string_list(event, "evidence", key), event.get("state"))
            last_time = moment
        if condition.get("state") != history[-1].get("state"):
            raise ValueError(f"{key}: condition state/history mismatch")
        if evidence != history[-1].get("evidence"):
            raise ValueError(f"{key}: condition evidence/history mismatch")

    affected = {key: affected_routes(routes, key) for key in conditions}
    for key, route in routes.items():
        if "condition_ids" in route:
            for condition_id in string_list(route, "condition_ids", key):
                if condition_id not in conditions:
                    raise ValueError(f"{key}: unknown condition {condition_id}")
        reviews = route.get("condition_reviews", [])
        if not isinstance(reviews, list):
            raise ValueError(f"{key}: condition_reviews must be a list")
        last_time, last_revision = None, {}
        for review in reviews:
            condition_id = review.get("condition_id")
            if condition_id not in conditions or key not in affected[condition_id]:
                raise ValueError(f"{key}: review of unrelated/unknown condition {condition_id}")
            revision = review.get("revision")
            if (type(revision) is not int or not 1 <= revision <= conditions[condition_id]["revision"]
                    or revision < last_revision.get(condition_id, 0)):
                raise ValueError(f"{key}: invalid condition review revision")
            moment = timestamp(review.get("at"), key)
            condition_time = timestamp(conditions[condition_id]["history"][revision - 1]["at"], condition_id)
            if moment < condition_time or (last_time and moment < last_time):
                raise ValueError(f"{key}: invalid condition review time")
            outcome = review.get("outcome")
            if outcome not in REVIEW_OUTCOMES:
                raise ValueError(f"{key}: invalid condition review outcome")
            require_text(review, ("reason",), key)
            refs = string_list(review, "evidence", key)
            evidence_refs(refs, route, key, completed=outcome == "revalidated")
            if outcome in {"corrected", "revalidated"} and not refs:
                raise ValueError(f"{key}: resolved change needs review evidence")
            if outcome in {"deferred", "retest"}:
                require_text(review, ("next_step", "stop_when"), key)
            last_time, last_revision[condition_id] = moment, revision
    pending = impact_report(conditions, routes)["pending_reviews"]
    for path in (root / "re/env").glob("*.json"):
        snapshot = load(path)
        timestamp(snapshot.get("collected_at"), str(path))
        if not isinstance(snapshot.get("host"), dict) or not isinstance(snapshot.get("tools"), list):
            raise ValueError(f"{path}: host object/tools list required")
    management = validate_management(root, targets, routes, runs, pending, hashes, complete, conditions)
    verify_seals(root, targets, runs, allow_unsealed)
    return {"targets": len(targets), "routes": len(routes), "runs": len(runs),
            "conditions": len(conditions), "pending_reviews": len(pending), "hashes_verified": hashes,
            "audit_pending": management["audit_pending"],
            "open_disputes": len(management["open_disputes"]),
            "recovery_pending": len(management["recovery_pending"]),
            "dispute_impacts": len(management["dispute_impacts"]),
            "completion_checked": complete or (not management["legacy"] and load(root / "re/project.json")["status"] == "completed")}


def probe():
    names = ["git", "python", "py", "node", "npm", "rg", "7z", "java", "rea",
             "frida", "frida-ps", "hyperdbg-cli", "hyperdbg", "windbg", "cdb",
             "x64dbg", "x32dbg", "procmon", "procexp", "tshark", "mitmproxy",
             "gdb", "lldb", "strace", "jadx", "adb", "ilspycmd", "binwalk", "unblob"]
    tools = []
    for name in names:
        path = shutil.which(name)
        tools.append({"name": name, "path": path, "version": None,
                      "discovered": "pass" if path else "unknown",
                      "discovery_method": "PATH only",
                      "executable": "unknown", "session_ready": "unknown",
                      "target_ready": "unknown"})
    codex_base = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    configs = [codex_base / "config.toml", Path.home() / ".cursor/mcp.json",
               Path.home() / ".claude.json"]
    if os.environ.get("APPDATA"):
        configs.append(Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json")
    return {"schema_version": 1, "collected_at": now(),
            "host": {"system": platform.system(), "release": platform.release(),
                     "version": platform.version(), "machine": platform.machine(),
                     "python": sys.version, "python_executable": sys.executable,
                     "shell_hint": os.environ.get("SHELL") or os.environ.get("ComSpec"),
                     "privilege": "unknown", "virtualization": "unknown"},
            "tools": tools,
            "mcp_config_candidates": [{"path": str(p), "exists": p.is_file()} for p in configs],
            "limitations": "Discovery only; no tools executed, config contents read, or MCP connection verified.",
            "changes": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "index", "check", "impact", "audit-scope"):
        command = sub.add_parser(name)
        command.add_argument("root", type=Path)
        if name == "check":
            command.add_argument("--hashes", action="store_true")
            command.add_argument("--complete", action="store_true", help="require project completion evidence and closed obligations")
    command = sub.add_parser("probe")
    command.add_argument("--output", type=Path)
    command = sub.add_parser("seal", help="seal one finished run after checking its original evidence")
    command.add_argument("root", type=Path)
    command.add_argument("run_id")
    args = parser.parse_args()
    try:
        if args.command == "probe":
            snapshot = probe()
            if args.output:
                save_new(args.output, snapshot)
                print(f"Snapshot created: {args.output}")
            else:
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        else:
            root = args.root.resolve()
            if args.command == "init":
                initialize(root)
                print(f"Initialized: {root / 'INDEX.md'}; config: {root / PROJECT_CONFIG}; repository skill: {root / LOCAL_SKILL}")
                print("Next: adapt repository config and merge its pointer into existing AGENTS.md/CLAUDE.md.")
            elif args.command == "index":
                refresh(root)
                print(f"Index refreshed: {root / 'INDEX.md'}")
            elif args.command == "impact":
                print(json.dumps(report_for_project(root), ensure_ascii=False, indent=2))
            elif args.command == "audit-scope":
                print(json.dumps(audit_scope(root), ensure_ascii=False, indent=2))
            elif args.command == "seal":
                identifier(args.run_id, "run")
                validate(root, True, allow_unsealed=True, check_index=False)
                run = load(local_file(root, f"re/runs/{args.run_id}/run.json"))
                if run["status"] not in TERMINAL_RUNS:
                    raise ValueError("seal requires a finished run with retained execution facts")
                targets = load(root / "re/targets.json")["targets"]
                target = next(item for item in targets if item["id"] == run["target"]["id"])
                seal_run(root, target, run)
                print(f"Sealed {args.run_id}; preserve re/seals in reviewed version control; refresh INDEX.")
            else:
                print(json.dumps(validate(root, args.hashes, args.complete), ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
