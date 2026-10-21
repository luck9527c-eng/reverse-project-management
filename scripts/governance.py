"""Project acceptance, audit coverage, evidence lineage and recovery integrity.

These checks validate recorded declarations, never infer semantic truth from logs.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath


def read(path):
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(part)
    return value.hexdigest()


def text(record, *fields):
    for field in fields:
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"management: missing {field}")


def moment(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("management: timestamp needs timezone")
    return parsed


def refs(record, field, known):
    values = record.get(field)
    if (not isinstance(values, list) or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values)) or any(v not in known for v in values)):
        raise ValueError(f"management: invalid {field} references")
    return values


def audit_scope(root):
    """Snapshot every historical route, not only the existing dependency graph."""
    paths = {root / "re/targets.json", root / "docs/agents/reverse-project-management.md"}
    for folder in ("routes", "conditions", "env", "docs", "scripts"):
        paths.update(p for p in (root / "re" / folder).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts)
    paths.update((root / "re/runs").glob("*/run.json"))
    snapshot = {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths) if p.is_file()}
    path = root / "re/project.json"
    if path.is_file():
        record = read(path)
        # Exclude audits themselves so recording an audit cannot invalidate itself.
        scope = {k: record.get(k) for k in ("goal", "scope", "acceptance", "disputes")}
        snapshot["re/project.json#scope"] = hashlib.sha256(
            json.dumps(scope, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"snapshot": snapshot}


def management_summary(root):
    path = root / "re/project.json"
    runs = [read(p) for p in sorted((root / "re/runs").glob("*/run.json"))]
    recovery = [r["id"] for r in runs if r.get("status") in {"running", "interrupted"}
                and r.get("state", {}).get("status") not in {"restored", "not_needed"}
                or r.get("state", {}).get("status") == "pending"]
    if not path.is_file():
        return {"legacy": True, "audit_pending": True, "acceptance_pending": [],
                "open_disputes": [], "recovery_pending": recovery}
    value = read(path)
    audits = value.get("audits", [])
    audit = audits[-1] if audits else {}
    routes = {read(p)["id"] for p in (root / "re/routes").glob("*.json")}
    reviews = audit.get("route_reviews", [])
    pending = (audit.get("snapshot") != audit_scope(root)["snapshot"]
               or {r.get("route_id") for r in reviews} != routes
               or any(r.get("outcome") == "follow_up" for r in reviews))
    return {"legacy": False, "audit_pending": pending,
            "acceptance_pending": [a["id"] for a in value.get("acceptance", []) if a.get("status") != "met"],
            "open_disputes": [d for d in value.get("disputes", []) if d.get("status") == "open"],
            "recovery_pending": recovery}


def validate_management(root, targets, routes, runs, pending_reviews, hashes=False, complete=False):
    # Roots are acquisition events, not file formats or exports. Missing legacy
    # provenance stays structurally readable but cannot count toward acceptance.
    roots, visiting = {}, set()

    def source_roots(key):
        if key in visiting:
            raise ValueError(f"{key}: evidence provenance cycle")
        if key in roots:
            return roots[key]
        visiting.add(key)
        run = runs[key]
        provenance = run.get("provenance")
        result = set()
        if provenance is not None:
            kind = provenance.get("kind")
            sources = refs(provenance, "source_runs", runs)
            if kind not in {"acquisition", "derived"} or (kind == "derived") != bool(sources):
                raise ValueError(f"{key}: invalid provenance kind/source_runs")
            text(provenance, "note")
            if kind == "acquisition":
                result = {key}
            for parent in sources:
                if runs[parent]["target"] != run["target"] or runs[parent]["status"] != "completed":
                    raise ValueError(f"{key}: invalid provenance source scope/status")
                result.update(source_roots(parent))
        visiting.remove(key)
        roots[key] = result
        return result

    for key, run in runs.items():
        source_roots(key)
        state = run.get("state")
        if state is None:
            if run["status"] == "interrupted":
                raise ValueError(f"{key}: interrupted run needs recovery state")
            continue
        status = state.get("status")
        if status not in {"not_started", "pending", "restored", "not_needed"}:
            raise ValueError(f"{key}: invalid restoration status")
        if run["status"] != "planned":
            text(state, "initial", "expected_effects", "restore_plan")
            if status == "not_started":
                raise ValueError(f"{key}: started run cannot have not_started restoration")
        if status in {"restored", "not_needed"}:
            text(state, "observed_effects", "verification")
            if run["status"] in {"planned", "running"}:
                raise ValueError(f"{key}: live/unstarted run cannot be restored")
        if run["status"] == "interrupted":
            recovery = state.get("recovery") or {}
            moment(recovery.get("at"))
            text(recovery, "assessment", "next_step")

    path = root / "re/project.json"
    if not path.is_file():
        if complete:
            raise ValueError("completion: acceptance project record missing; migrate legacy project")
        return management_summary(root)
    project = read(path)
    if project.get("schema_version") != 1 or project.get("status") not in {"active", "completed"}:
        raise ValueError("project.json: invalid schema/status")
    for field in ("acceptance", "audits", "disputes"):
        if not isinstance(project.get(field), list):
            raise ValueError(f"project.json: {field} must be a list")

    def evidence(record, field, allowed_targets, completed=True):
        values = refs(record, field, runs)
        for key in values:
            if runs[key]["target"]["id"] not in allowed_targets:
                raise ValueError(f"{key}: management evidence target mismatch")
            if runs[key]["status"] in {"planned", "running"} or (completed and runs[key]["status"] != "completed"):
                raise ValueError(f"{key}: management evidence not finished/usable")
        return values

    seen = set()
    for item in project["acceptance"]:
        key = item.get("id")
        if not isinstance(key, str) or not key.startswith("A-") or key in seen:
            raise ValueError("project.json: invalid/duplicate acceptance ID")
        seen.add(key)
        text(item, "requirement")
        target_ids = refs(item, "target_ids", targets)
        if not target_ids or item.get("status") not in {"pending", "met"}:
            raise ValueError(f"{key}: invalid acceptance targets/status")
        values = evidence(item, "evidence", target_ids)
        minimum = item.get("min_independent_sources", 1)
        if type(minimum) is not int or minimum < 1:
            raise ValueError(f"{key}: invalid independent source minimum")
        deliverables = item.get("deliverables")
        if not isinstance(deliverables, list):
            raise ValueError(f"{key}: deliverables must be a list")
        for artifact in deliverables:
            relative = artifact.get("path")
            if not isinstance(relative, str) or Path(relative).is_absolute() or PureWindowsPath(relative).drive:
                raise ValueError(f"{key}: invalid deliverable path")
            file = (root / relative).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                raise ValueError(f"{key}: missing/escaping deliverable")
            expected = artifact.get("sha256")
            if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
                raise ValueError(f"{key}: deliverable needs lowercase SHA256")
            if hashes and sha(file) != expected:
                raise ValueError(f"{key}: deliverable hash mismatch")
        if item["status"] == "met":
            text(item, "reason")
            if not values or len(set().union(*(roots[v] for v in values))) < minimum:
                raise ValueError(f"{key}: insufficient independent evidence sources")

    seen = set()
    for dispute in project["disputes"]:
        key = dispute.get("id")
        if not isinstance(key, str) or not key.startswith("D-") or key in seen:
            raise ValueError("project.json: invalid/duplicate dispute ID")
        seen.add(key)
        text(dispute, "claim", "scope")
        associated = refs(dispute, "route_ids", routes)
        allowed = {t for r in associated for t in routes[r]["target_ids"]}
        if not associated or type(dispute.get("critical")) is not bool:
            raise ValueError(f"{key}: dispute needs routes and critical flag")
        for side in ("supporting", "contradicting"):
            if not evidence(dispute, side, allowed, completed=False):
                raise ValueError(f"{key}: both dispute evidence sides required")
        if dispute.get("status") not in {"open", "resolved"}:
            raise ValueError(f"{key}: invalid dispute status")
        if dispute["status"] == "resolved":
            resolution = dispute.get("resolution") or {}
            moment(resolution.get("at"))
            text(resolution, "reason", "outcome")
            if not evidence(resolution, "evidence", allowed):
                raise ValueError(f"{key}: resolution evidence required")

    last = None
    for audit in project["audits"]:
        when = moment(audit.get("at"))
        if last and when < last:
            raise ValueError("audit: time went backwards")
        last = when
        text(audit, "trigger")
        if not isinstance(audit.get("snapshot"), dict) or not isinstance(audit.get("route_reviews"), list):
            raise ValueError("audit: snapshot and route_reviews required")
        reviewed = set()
        for review in audit["route_reviews"]:
            key = review.get("route_id")
            if key not in routes or key in reviewed:
                raise ValueError("audit: invalid/duplicate route review")
            reviewed.add(key)
            text(review, "reason")
            if review.get("outcome") not in {"no_change", "linked", "follow_up"}:
                raise ValueError("audit: invalid review outcome")
            if review["outcome"] == "follow_up":
                text(review, "next_step", "stop_when")
            if review["outcome"] == "linked":
                linked = refs(review, "condition_ids", routes[key].get("condition_ids", []))
                if not linked:
                    raise ValueError("audit: linked review needs registered condition_ids")
    summary = management_summary(root)
    if complete or project["status"] == "completed":
        if not project["acceptance"] or summary["acceptance_pending"]:
            raise ValueError("completion: acceptance criteria missing or unmet")
        text(project, "goal", "scope")
        if summary["audit_pending"] or pending_reviews:
            raise ValueError("completion: association audit/reviews pending")
        if any(d["critical"] for d in summary["open_disputes"]):
            raise ValueError("completion: critical evidence dispute open")
        if summary["recovery_pending"] or any(r["status"] == "running" for r in runs.values()):
            raise ValueError("completion: experiment recovery pending")
        if any(route["status"] == "active" for route in routes.values()):
            raise ValueError("completion: active route needs closure or explicit pause/disposition")
        if any("state" not in r for r in runs.values() if r["status"] != "planned"):
            raise ValueError("completion: legacy experiment state unassessed")
        text(project.get("completion", {}), "limitations", "handoff")
    return summary
