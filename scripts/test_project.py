"""Behavioral checks for record integrity; uses only temporary projects."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("project.py")
ASSETS = SCRIPT.parent.parent / "assets"


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8")

    def init(self):
        result = self.cli("init", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def write_json(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def fixture(self):
        self.init()
        data = b"fixture, not an executable"
        sample = self.root / "sample.bin"
        sample.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        self.write_json("re/targets.json", {"schema_version": 1, "targets": [
            {"id": "T-001", "path": "sample.bin", "sha256": sha,
             "version": "test", "platform": "test", "arch": "test", "source": "fixture"}]})
        route = json.loads((ASSETS / "route.json").read_text(encoding="utf-8"))
        route.update(question="Does test output exist?", hypothesis="It exists",
                     target_ids=["T-001"], state_reason="Fixture created")
        route["experiment"] = {"action": "write fixture", "expected": "fixture output",
                               "falsifier": "contradicting fixture"}
        route["budget"] = {"limit": "one run", "stop_when": "after fixture"}
        route["history"][0].update(at="2026-10-21T09:00:00Z", reason="Fixture created")
        self.write_json("re/routes/R-001.json", route)
        return route, sha

    def check(self, *args):
        self.assertEqual(self.cli("index", self.root).returncode, 0)
        return self.cli("check", self.root, *args)

    def test_init_is_valid_and_refuses_overwrite(self):
        self.init()
        before = (self.root / "INDEX.md").read_bytes()
        self.assertEqual(self.cli("check", self.root).returncode, 0)
        self.assertNotEqual(self.cli("init", self.root).returncode, 0)
        self.assertEqual((self.root / "INDEX.md").read_bytes(), before)

    def test_project_copy_is_independent_of_original(self):
        original = (ASSETS.parent / "SKILL.md").read_bytes()
        self.init()
        local = self.root / ".agents/skills/reverse-project-management"
        self.assertEqual((local / "SKILL.md").read_bytes(), original)
        (local / "SKILL.md").write_text("Project-specific rules", encoding="utf-8")
        self.assertEqual((ASSETS.parent / "SKILL.md").read_bytes(), original)
        result = subprocess.run([sys.executable, str(local / "scripts/project.py"), "check", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_initialization_from_checkout_excludes_git_metadata(self):
        checkout = Path(self.temp.name) / "checkout" / "reverse-project-management"
        shutil.copytree(ASSETS.parent, checkout, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        (checkout / ".git").mkdir()
        (checkout / ".git/config").write_text("private checkout configuration", encoding="utf-8")
        result = subprocess.run([sys.executable, str(checkout / "scripts/project.py"), "init", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        local = self.root / ".agents/skills/reverse-project-management"
        self.assertTrue((local / "SKILL.md").is_file())
        self.assertFalse((local / ".git").exists())

    def test_init_creates_repository_config_without_editing_agent_instructions(self):
        self.root.mkdir(parents=True)
        original = b"# Existing agent rules\n\nKeep these decisions.\n"
        (self.root / "CLAUDE.md").write_bytes(original)
        self.init()
        config = self.root / "docs/agents/reverse-project-management.md"
        self.assertTrue(config.is_file())
        self.assertIn("docs/agents/reverse-project-management.md",
                      (self.root / "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), original)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_existing_repository_config_is_preserved_before_initialization(self):
        path = self.root / "docs/agents/reverse-project-management.md"
        path.parent.mkdir(parents=True)
        path.write_text("Existing project policy", encoding="utf-8")
        self.assertNotEqual(self.cli("init", self.root).returncode, 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "Existing project policy")
        self.assertFalse((self.root / "re").exists())
        self.assertFalse((self.root / ".agents/skills/reverse-project-management").exists())

    def test_index_keeps_notes_and_includes_new_document(self):
        self.init()
        index = self.root / "INDEX.md"
        index.write_text("Human decision: keep this\n" + index.read_text(encoding="utf-8"), encoding="utf-8")
        (self.root / "re/docs/a b.md").write_text("Evidence", encoding="utf-8")
        self.assertNotEqual(self.cli("check", self.root).returncode, 0)
        self.assertEqual(self.cli("index", self.root).returncode, 0)
        self.assertTrue(index.read_text(encoding="utf-8").startswith("Human decision: keep this\n"))
        self.assertIn("re/docs/a%20b.md", index.read_text(encoding="utf-8"))

    def test_target_hash_mutation_is_detected(self):
        self.fixture()
        self.assertEqual(self.check("--hashes").returncode, 0)
        (self.root / "sample.bin").write_bytes(b"changed")
        result = self.check("--hashes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("hash mismatch", result.stderr)

    def test_falsified_without_evidence_is_rejected(self):
        route, _ = self.fixture()
        route["status"] = "falsified"
        route["history"].append({"at": "2026-10-21T09:01:00Z", "from": "planned",
                                 "to": "falsified", "reason": "no output", "evidence": []})
        self.write_json("re/routes/R-001.json", route)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("closure", result.stderr)

    def test_dependency_cycle_is_rejected(self):
        route, _ = self.fixture()
        route["depends_on"] = ["R-002"]
        self.write_json("re/routes/R-001.json", route)
        route["id"] = "R-002"
        route["depends_on"] = ["R-001"]
        self.write_json("re/routes/R-002.json", route)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cycle", result.stderr)

    def test_run_identity_and_artifact_integrity(self):
        route, sha = self.fixture()
        output = self.root / "re/runs/RUN-test/raw/out.txt"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"observed")
        env = "re/env/ENV-test.json"
        self.write_json(env, {"collected_at": "2026-10-21T09:00:00Z", "host": {}, "tools": []})
        run = json.loads((ASSETS / "run.json").read_text(encoding="utf-8"))
        run.update(id="RUN-test", status="completed", command="fixture-command",
                   started_at="2026-10-21T09:00:00Z", ended_at="2026-10-21T09:01:00Z",
                   tools=[{"name": "fixture", "version": "1"}], result="observed",
                   exit_code=0, target={"id": "T-001", "sha256": sha})
        run["environment"]["snapshot"] = env
        run["observation"] = dict.fromkeys(["trigger", "window", "coverage", "control"], "fixture")
        run["artifacts"] = [{"path": "re/runs/RUN-test/raw/out.txt",
                             "sha256": hashlib.sha256(b"observed").hexdigest()}]
        self.finish_metadata(run)
        route["evidence"] = ["RUN-test"]
        self.write_json("re/routes/R-001.json", route)
        self.write_json("re/runs/RUN-test/run.json", run)
        self.seal(run["id"])
        self.assertEqual(self.check("--hashes").returncode, 0)
        output.write_bytes(b"overwritten")
        self.assertNotEqual(self.check("--hashes").returncode, 0)
        run["target"]["sha256"] = "0" * 64
        self.write_json("re/runs/RUN-test/run.json", run)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("target hash", result.stderr)

    def test_path_escape_is_rejected(self):
        route, _ = self.fixture()
        route["evidence"] = ["../../outside"]
        self.write_json("re/routes/R-001.json", route)
        self.assertNotEqual(self.check().returncode, 0)

    def test_probe_never_overwrites_snapshot(self):
        self.root.mkdir()
        path = self.root / "ENV.json"
        result = self.cli("probe", "--output", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(value["host"])
        self.assertTrue(value["collected_at"])
        before = path.read_bytes()
        self.assertNotEqual(self.cli("probe", "--output", path).returncode, 0)
        self.assertEqual(path.read_bytes(), before)

    def add_run(self, route_id, sha, run_id="RUN-shared", sealed=True):
        output = self.root / f"re/runs/{run_id}/raw/out.txt"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"new evidence")
        env = "re/env/ENV-shared.json"
        self.write_json(env, {"collected_at": "2026-10-21T09:00:00Z", "host": {}, "tools": []})
        run = json.loads((ASSETS / "run.json").read_text(encoding="utf-8"))
        run.update(id=run_id, route_id=route_id, status="completed", command="fixture-command",
                   started_at="2026-10-21T09:00:00Z", ended_at="2026-10-21T09:01:00Z",
                   tools=[{"name": "fixture", "version": "1"}], result="new evidence",
                   exit_code=0, target={"id": "T-001", "sha256": sha})
        run["environment"]["snapshot"] = env
        run["artifacts"] = [{"path": output.relative_to(self.root).as_posix(),
                             "sha256": hashlib.sha256(b"new evidence").hexdigest()}]
        self.finish_metadata(run)
        self.write_json(f"re/runs/{run_id}/run.json", run)
        if sealed:
            self.seal(run_id)
        return run_id

    def seal(self, run_id):
        result = self.cli("seal", self.root, run_id)
        self.assertEqual(result.returncode, 0, result.stderr)

    def finish_metadata(self, run):
        run["provenance"]["note"] = "Independent fixture acquisition"
        run["provenance"].update(capture_id=f"CAP-{run['id']}", captured_at=run["started_at"],
                                 raw_artifacts=[a["path"] for a in run["artifacts"]])
        run["environment"]["snapshot_sha256"] = hashlib.sha256(
            (self.root / run["environment"]["snapshot"]).read_bytes()).hexdigest()
        run["observation"] = dict.fromkeys(["trigger", "window", "coverage", "control"], "fixture")
        run["observation"]["chain_status"] = "passed"
        run["state"] = {"initial": "clean fixture", "expected_effects": "new files only",
                        "restore_plan": "none required", "status": "not_needed",
                        "observed_effects": "retained files only", "verification": "no process or global changes",
                        "recovery": None}

    def condition_fixture(self):
        route, sha = self.fixture()
        for number, dependencies in [(1, []), (2, ["R-001"]), (3, ["R-002"]), (4, [])]:
            item = json.loads(json.dumps(route))
            item.update(id=f"R-{number:03}", depends_on=dependencies,
                        condition_ids=["C-001"] if number == 1 else [], condition_reviews=[])
            self.write_json(f"re/routes/{item['id']}.json", item)
        condition = {"schema_version": 1, "id": "C-001", "statement": "Runtime data is observable",
                     "scope": "T-001 fixture only", "target_ids": ["T-001"], "revision": 1,
                     "state": "unknown", "evidence": [], "history": [
                         {"revision": 1, "at": "2026-10-21T09:00:00Z", "state": "unknown",
                          "reason": "Capture capability unknown", "evidence": []}]}
        self.write_json("re/conditions/C-001.json", condition)
        return condition, sha

    def review(self, revision=1, outcome="unchanged"):
        return {"condition_id": "C-001", "revision": revision, "at": "2026-10-21T09:02:00Z",
                "outcome": outcome, "reason": "Reviewed scope and observation chain", "evidence": [],
                "next_step": "Run the declared minimal control if scheduled", "stop_when": "One attempt"}

    def management(self):
        return json.loads((self.root / "re/project.json").read_text(encoding="utf-8"))

    def save_management(self, value):
        self.write_json("re/project.json", value)

    def test_completion_requires_acceptance_and_does_not_equal_structural_check(self):
        self.init()
        self.assertEqual(self.check().returncode, 0)
        result = self.cli("check", self.root, "--complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("acceptance", result.stderr)

    def test_audit_detects_new_scope_and_includes_unlinked_historical_routes(self):
        self.fixture()
        report = json.loads(self.cli("audit-scope", self.root).stdout)
        self.assertIn("re/routes/R-001.json", report["snapshot"])
        value = self.management()
        value["audits"] = [{"at": "2026-10-21T10:00:00Z", "trigger": "handoff",
                            "snapshot": report["snapshot"], "route_reviews": [
                                {"route_id": "R-001", "outcome": "no_change", "reason": "Checked old blockers against all discoveries"}]}]
        self.save_management(value)
        self.assertFalse(json.loads(self.check().stdout)["audit_pending"])
        (self.root / "re/docs/discovery.md").write_text("New capability", encoding="utf-8")
        self.assertTrue(json.loads(self.check().stdout)["audit_pending"])

    def test_open_conflict_is_visible_without_rewriting_route_status(self):
        route, sha = self.fixture()
        first = self.add_run("R-001", sha, "RUN-support")
        second = self.add_run("R-001", sha, "RUN-counter")
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Output interpretation", "scope": "T-001",
                               "route_ids": ["R-001"], "supporting": [first], "contradicting": [second],
                               "critical": True, "status": "open", "resolution": None}]
        self.save_management(value)
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["open_disputes"], 1)
        self.assertIn("D-001", (self.root / "INDEX.md").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.root / "re/routes/R-001.json").read_text())["status"], route["status"])

    def test_interruption_retains_pending_recovery_and_rejects_premature_restoration(self):
        _, sha = self.fixture()
        run_id = self.add_run("R-001", sha, sealed=False)
        path = f"re/runs/{run_id}/run.json"
        run = json.loads((self.root / path).read_text())
        run["status"] = "interrupted"
        run["state"] = {"initial": "clean snapshot", "expected_effects": "session and process",
                        "restore_plan": "stop owned process then compare state", "status": "pending",
                        "observed_effects": "unknown after disconnect", "verification": "",
                        "recovery": {"at": "2026-10-21T10:00:00Z", "assessment": "Process status unknown",
                                     "next_step": "Inspect owned session without rerunning"}}
        self.write_json(path, run)
        self.seal(run_id)
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["recovery_pending"], 1)
        run["state"]["status"] = "restored"
        self.write_json(path, run)
        self.assertIn("verification", self.check().stderr)

    def test_two_exports_of_one_capture_do_not_satisfy_independent_evidence(self):
        _, sha = self.fixture()
        original = self.add_run("R-001", sha, "RUN-capture")
        exports = [self.add_run("R-001", sha, name, sealed=False) for name in ("RUN-export-a", "RUN-export-b")]
        for run_id in exports:
            path = f"re/runs/{run_id}/run.json"
            run = json.loads((self.root / path).read_text())
            run["provenance"] = {"kind": "derived", "source_runs": [original], "note": "Same raw capture"}
            self.write_json(path, run)
            self.seal(run_id)
        value = self.management()
        value.update(goal="Deliver observation", scope="T-001")
        value["acceptance"] = [{"id": "A-001", "requirement": "Independent corroboration", "target_ids": ["T-001"],
                                "status": "met", "evidence": exports, "deliverables": [], "reason": "Two exports",
                                "min_independent_sources": 2}]
        self.save_management(value)
        self.assertIn("independent", self.check().stderr)

    def complete_fixture(self):
        route, sha = self.fixture()
        run_id = self.add_run("R-001", sha)
        route.update(status="validated", evidence=[run_id], closure={
            "summary": "Fixture observation confirmed", "scope": "T-001", "limitations": "Fixture only", "evidence": [run_id]})
        route["history"].append({"at": "2026-10-21T09:02:00Z", "from": "planned", "to": "validated",
                                 "reason": "Fixture evidence matches criterion", "evidence": [run_id]})
        self.write_json("re/routes/R-001.json", route)
        value = self.management()
        value.update(goal="Fixture delivery", scope="T-001 fixture only", completion={
            "limitations": "Only a synthetic fixture", "handoff": "Retain output; no further experiment planned"})
        value["acceptance"] = [{"id": "A-001", "requirement": "Fixture observation", "target_ids": ["T-001"],
                                "status": "met", "evidence": [run_id], "deliverables": [], "reason": "Compared observation"}]
        self.save_management(value)
        self.audit_current_scope()
        return run_id

    def audit_current_scope(self):
        snapshot = json.loads(self.cli("audit-scope", self.root).stdout)["snapshot"]
        value = self.management()
        value["audits"].append({"at": "2026-10-21T10:00:00Z", "trigger": "completion",
                                "snapshot": snapshot, "route_reviews": [
                                    {"route_id": path.stem, "outcome": "no_change", "reason": "Reviewed all new discovery scope"}
                                    for path in sorted((self.root / "re/routes").glob("*.json"))]})
        self.save_management(value)

    def test_completion_passes_only_when_current_obligations_close(self):
        self.complete_fixture()
        result = self.check("--hashes", "--complete")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["completion_checked"])
        value = self.management()
        value["status"] = "completed"
        self.save_management(value)
        self.assertEqual(self.check().returncode, 0)
        (self.root / "re/docs/new-evidence.md").write_text("Later evidence changes scope", encoding="utf-8")
        self.assertIn("audit", self.check().stderr)

    def test_critical_dispute_blocks_completion_even_after_audit(self):
        run_id = self.complete_fixture()
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Same output has contrary interpretations", "scope": "T-001",
                               "route_ids": ["R-001"], "supporting": [run_id], "contradicting": [run_id],
                               "critical": True, "status": "open", "resolution": None}]
        self.save_management(value)
        self.audit_current_scope()
        self.assertIn("disput", self.check("--complete").stderr)

    def test_provenance_cycle_is_rejected(self):
        _, sha = self.fixture()
        for run_id, parent in [("RUN-a", "RUN-b"), ("RUN-b", "RUN-a")]:
            self.add_run("R-001", sha, run_id, sealed=False)
            path = f"re/runs/{run_id}/run.json"
            run = json.loads((self.root / path).read_text())
            run["provenance"] = {"kind": "derived", "source_runs": [parent], "note": "Invalid cyclic derivation"}
            self.write_json(path, run)
        self.assertIn("cycle", self.check().stderr)

    def test_linked_audit_cannot_claim_an_unregistered_condition(self):
        self.fixture()
        self.audit_current_scope()
        value = self.management()
        value["audits"][-1]["route_reviews"][0].update(outcome="linked", condition_ids=["C-missing"])
        self.save_management(value)
        self.assertIn("condition_ids", self.check().stderr)

    def test_p1_init_rejects_dangling_index_before_any_write(self):
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside.md"
        try:
            os.symlink(outside, self.root / "INDEX.md")
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")
        result = self.cli("init", self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(outside.exists())
        self.assertFalse((self.root / "re").exists())
        self.assertFalse((self.root / ".agents").exists())

    def test_p1_completed_run_requires_explicit_seal(self):
        _, sha = self.fixture()
        self.add_run("R-001", sha)
        # Remove only the test-created seal if the new fixture sealed it.
        seal = self.root / "re/seals/runs/RUN-shared.json"
        if seal.exists():
            seal.unlink()
        self.assertIn("unsealed", self.check("--hashes").stderr)

    def test_p1_index_write_accepts_project_root_path_alias(self):
        from project import refresh
        self.init()
        # Windows tempfile paths may use ADMINI~1 while resolve() uses the long name.
        refresh(self.root)
        self.assertEqual(self.cli("check", self.root).returncode, 0)

    def test_p1_init_rejects_linked_config_ancestor_before_any_write(self):
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside-docs"
        outside.mkdir()
        try:
            os.symlink(outside, self.root / "docs", target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")
        result = self.cli("init", self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / "re").exists())
        self.assertFalse((self.root / ".agents").exists())

    def test_p1_environment_hash_cannot_be_replaced_with_changed_bytes(self):
        self.complete_fixture()
        environment = self.root / "re/env/ENV-shared.json"
        value = json.loads(environment.read_text())
        value["host"]["changed"] = True
        self.write_json("re/env/ENV-shared.json", value)
        path = "re/runs/RUN-shared/run.json"
        run = json.loads((self.root / path).read_text())
        run["environment"]["snapshot_sha256"] = hashlib.sha256(environment.read_bytes()).hexdigest()
        self.write_json(path, run)
        self.assertIn("sealed execution", self.check("--hashes").stderr)

    def test_p1_legacy_capture_metadata_does_not_count_as_independent(self):
        _, sha = self.fixture()
        run_id = self.add_run("R-001", sha, sealed=False)
        path = f"re/runs/{run_id}/run.json"
        run = json.loads((self.root / path).read_text())
        run["provenance"] = {"kind": "acquisition", "source_runs": [], "note": "Legacy source unknown"}
        self.write_json(path, run)
        self.seal(run_id)
        self.assertEqual(self.check("--hashes").returncode, 0)
        self.acceptance([run_id])
        self.assertIn("independent", self.check("--hashes").stderr)

    def test_p1_old_evidence_cannot_rebind_to_new_target(self):
        self.complete_fixture()
        data = b"changed target without another acquisition"
        (self.root / "sample.bin").write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        targets = json.loads((self.root / "re/targets.json").read_text())
        targets["targets"][0]["sha256"] = sha
        self.write_json("re/targets.json", targets)
        path = "re/runs/RUN-shared/run.json"
        run = json.loads((self.root / path).read_text())
        run["target"]["sha256"] = sha
        self.write_json(path, run)
        self.audit_current_scope()
        self.assertIn("sealed", self.check("--hashes", "--complete").stderr)

    def test_p1_rewritten_environment_is_detected(self):
        self.complete_fixture()
        self.write_json("re/env/ENV-shared.json", {"collected_at": "2026-10-21T09:00:00Z",
                                                   "host": {"changed": True}, "tools": []})
        self.audit_current_scope()
        self.assertIn("environment", self.check("--hashes", "--complete").stderr)

    def test_p1_same_raw_file_is_not_two_independent_acquisitions(self):
        _, sha = self.fixture()
        self.add_run("R-001", sha, "RUN-first")
        self.add_run("R-001", sha, "RUN-second")
        first = json.loads((self.root / "re/runs/RUN-first/run.json").read_text())
        path = "re/runs/RUN-second/run.json"
        second = json.loads((self.root / path).read_text())
        second["artifacts"] = first["artifacts"]
        second["provenance"]["raw_artifacts"] = [first["artifacts"][0]["path"]]
        self.write_json(path, second)
        value = self.management()
        value["acceptance"] = [{"id": "A-001", "requirement": "Two independent acquisitions", "target_ids": ["T-001"],
                                "status": "met", "evidence": ["RUN-first", "RUN-second"], "deliverables": [],
                                "reason": "Two imports", "min_independent_sources": 2}]
        self.save_management(value)
        # Check provenance before seal integrity to prove independence itself is enforced.
        self.assertIn("independent", self.check("--hashes").stderr)

    def test_p1_acceptance_covers_every_declared_target(self):
        self.complete_fixture()
        targets = json.loads((self.root / "re/targets.json").read_text())
        targets["targets"].append(dict(targets["targets"][0], id="T-002"))
        self.write_json("re/targets.json", targets)
        value = self.management()
        value["acceptance"][0]["target_ids"] = ["T-001", "T-002"]
        self.save_management(value)
        self.audit_current_scope()
        self.assertIn("coverage", self.check("--hashes", "--complete").stderr)

    def test_p1_noncritical_flag_cannot_hide_acceptance_dispute(self):
        run_id = self.complete_fixture()
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Acceptance evidence contradicted", "scope": "T-001",
                               "route_ids": ["R-001"], "acceptance_ids": ["A-001"],
                               "supporting": [run_id], "contradicting": [run_id],
                               "critical": False, "status": "open", "resolution": None}]
        self.save_management(value)
        self.audit_current_scope()
        self.assertIn("disput", self.check("--hashes", "--complete").stderr)

    def test_p1_disputed_parent_cannot_support_active_dependency(self):
        run_id = self.complete_fixture()
        child = json.loads((self.root / "re/routes/R-001.json").read_text())
        child.update(id="R-child", status="active", depends_on=["R-001"], evidence=[], closure=None)
        child["history"] = [{"at": "2026-10-21T09:03:00Z", "from": None, "to": "active",
                             "reason": "Depends on disputed result", "evidence": []}]
        self.write_json("re/routes/R-child.json", child)
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Parent has contrary evidence", "scope": "T-001",
                               "route_ids": ["R-001"], "supporting": [run_id], "contradicting": [run_id],
                               "critical": True, "status": "open", "resolution": None}]
        self.save_management(value)
        self.assertIn("disput", self.check("--hashes").stderr)
        report = json.loads(self.cli("impact", self.root).stdout)
        self.assertEqual({x["route_id"] for x in report["dispute_impacts"]}, {"R-001", "R-child"})

    def test_p1_falsification_requires_observation_and_control_references(self):
        self.complete_fixture()
        path = "re/routes/R-001.json"
        route = json.loads((self.root / path).read_text())
        route["status"] = route["history"][-1]["to"] = "falsified"
        route["closure"].update(criterion="criterion", coverage="claimed coverage", control="claimed control",
                                 reopen_when="new evidence")
        self.write_json(path, route)
        self.assertIn("observation", self.check("--hashes").stderr)

    def acceptance(self, evidence, targets=None, minimum=1):
        value = self.management()
        value["acceptance"] = [{"id": "A-001", "requirement": "Fixture target coverage", "target_ids": targets or ["T-001"],
                                "status": "met", "evidence": evidence, "deliverables": [], "reason": "Observed fixture",
                                "min_independent_sources": minimum}]
        self.save_management(value)

    def test_p1_hardlinked_raw_file_is_one_acquisition(self):
        _, sha = self.fixture()
        self.add_run("R-001", sha, "RUN-first")
        self.add_run("R-001", sha, "RUN-second", sealed=False)
        first = self.root / "re/runs/RUN-first/raw/out.txt"
        second = self.root / "re/runs/RUN-second/raw/out.txt"
        second.unlink()
        try:
            os.link(first, second)
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        self.seal("RUN-second")
        self.acceptance(["RUN-first", "RUN-second"], minimum=2)
        self.assertIn("independent", self.check("--hashes").stderr)

    def test_p1_equal_bytes_from_separate_captures_can_be_independent(self):
        _, sha = self.fixture()
        self.add_run("R-001", sha, "RUN-first")
        self.add_run("R-001", sha, "RUN-second")
        self.acceptance(["RUN-first", "RUN-second"], minimum=2)
        self.assertEqual(self.check("--hashes").returncode, 0)

    def test_p1_target_coverage_and_independence_are_both_per_target(self):
        route, sha = self.fixture()
        targets = json.loads((self.root / "re/targets.json").read_text())
        targets["targets"].append(dict(targets["targets"][0], id="T-002"))
        self.write_json("re/targets.json", targets)
        route["target_ids"].append("T-002")
        self.write_json("re/routes/R-001.json", route)
        for name, target in [("RUN-a", "T-001"), ("RUN-b", "T-001"), ("RUN-c", "T-002"), ("RUN-d", "T-002")]:
            self.add_run("R-001", sha, name, sealed=False)
            path = f"re/runs/{name}/run.json"
            run = json.loads((self.root / path).read_text())
            run["target"]["id"] = target
            self.write_json(path, run)
            self.seal(name)
        self.acceptance(["RUN-a", "RUN-b", "RUN-c"], ["T-001", "T-002"], 2)
        self.assertIn("independent evidence for target T-002", self.check("--hashes").stderr)
        self.acceptance(["RUN-a", "RUN-b", "RUN-c", "RUN-d"], ["T-001", "T-002"], 2)
        self.assertEqual(self.check("--hashes").returncode, 0)

    def test_p1_seal_cannot_be_replaced_and_execution_changes_are_detected(self):
        self.complete_fixture()
        self.assertIn("overwrite", self.cli("seal", self.root, "RUN-shared").stderr)
        path = "re/runs/RUN-shared/run.json"
        run = json.loads((self.root / path).read_text())
        run["command"] = "different command not executed"
        self.write_json(path, run)
        self.assertIn("sealed execution", self.check().stderr)
        self.assertIn("sealed execution", self.cli("seal", self.root, "RUN-shared").stderr)

    def test_p1_recovery_can_be_updated_without_rewriting_execution(self):
        self.complete_fixture()
        path = "re/runs/RUN-shared/run.json"
        run = json.loads((self.root / path).read_text())
        run["state"].update(status="pending", verification="", observed_effects="A retained fixture marker needs review")
        self.write_json(path, run)
        result = self.check("--hashes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["recovery_pending"], 1)

    def test_p1_dispute_propagates_through_shared_condition(self):
        condition, sha = self.condition_fixture()
        run_id = self.add_run("R-004", sha)
        condition.update(state="satisfied", evidence=[run_id])
        condition["history"][0].update(state="satisfied", evidence=[run_id])
        self.write_json("re/conditions/C-001.json", condition)
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Capture condition contradicted", "scope": "T-001",
                               "route_ids": ["R-004"], "supporting": [run_id], "contradicting": [run_id],
                               "critical": False, "status": "open", "resolution": None}]
        self.save_management(value)
        report = json.loads(self.cli("impact", self.root).stdout)
        self.assertEqual({x["route_id"] for x in report["dispute_impacts"]}, {"R-001", "R-002", "R-003", "R-004"})

    def test_p1_disputed_source_blocks_derived_acceptance(self):
        _, sha = self.fixture()
        first = self.add_run("R-001", sha, "RUN-first")
        derived = self.add_run("R-001", sha, "RUN-derived", sealed=False)
        path = f"re/runs/{derived}/run.json"
        run = json.loads((self.root / path).read_text())
        run["provenance"] = {"kind": "derived", "source_runs": [first], "note": "Export of disputed source"}
        self.write_json(path, run)
        self.seal(derived)
        self.acceptance([derived])
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Source contradicted", "scope": "T-001",
                               "route_ids": ["R-001"], "supporting": [first], "contradicting": [first],
                               "critical": False, "status": "open", "resolution": None}]
        self.save_management(value)
        self.assertIn("disput", self.check("--hashes").stderr)

    def test_p1_valid_falsification_needs_locatable_chain(self):
        run_id = self.complete_fixture()
        route = json.loads((self.root / "re/routes/R-001.json").read_text())
        route["status"] = route["history"][-1]["to"] = "falsified"
        locator = {"run_id": run_id, "path": f"re/runs/{run_id}/raw/out.txt", "locator": "line 1"}
        route["closure"].update(criterion="fixture criterion", coverage="fixture window", control="fixture control",
                                 reopen_when="new evidence", observation_refs=[locator], control_refs=[dict(locator)])
        self.write_json("re/routes/R-001.json", route)
        self.assertEqual(self.check("--hashes").returncode, 0)
        route["closure"]["control_refs"][0]["path"] = "unregistered.txt"
        self.write_json("re/routes/R-001.json", route)
        self.assertIn("artifact not registered", self.check("--hashes").stderr)

    def test_p1_failed_observation_chain_cannot_support_falsification(self):
        route, sha = self.fixture()
        run_id = self.add_run("R-001", sha, sealed=False)
        path = f"re/runs/{run_id}/run.json"
        run = json.loads((self.root / path).read_text())
        run["observation"]["chain_status"] = "failed"
        self.write_json(path, run)
        self.seal(run_id)
        locator = {"run_id": run_id, "path": f"re/runs/{run_id}/raw/out.txt", "locator": "line 1"}
        route.update(status="falsified", evidence=[run_id])
        route["history"].append({"at": "2026-10-21T09:02:00Z", "from": "planned", "to": "falsified",
                                 "reason": "Claimed negative observation", "evidence": [run_id]})
        route["closure"] = dict.fromkeys(["summary", "scope", "criterion", "coverage", "control", "limitations", "reopen_when"], "Fixture claim")
        route["closure"].update(evidence=[run_id], observation_refs=[locator], control_refs=[dict(locator)])
        self.write_json("re/routes/R-001.json", route)
        self.assertIn("observation chain not passed", self.check("--hashes").stderr)

    def test_p1_resolved_dispute_retains_history_and_clears_impact(self):
        run_id = self.complete_fixture()
        value = self.management()
        value["disputes"] = [{"id": "D-001", "claim": "Synthetic contradictory interpretations", "scope": "T-001",
                               "route_ids": ["R-001"], "supporting": [run_id], "contradicting": [run_id],
                               "critical": False, "status": "resolved",
                               "resolution": {"at": "2026-10-21T09:04:00Z", "reason": "Fixture scope comparison resolved interpretation",
                                              "outcome": "Different scopes explained", "evidence": [run_id]}}]
        self.save_management(value)
        self.assertEqual(json.loads(self.cli("impact", self.root).stdout)["dispute_impacts"], [])
        self.assertEqual(self.check("--hashes").returncode, 0)
        self.assertEqual(self.management()["disputes"][0]["status"], "resolved")

    def test_impact_finds_direct_and_transitive_routes_without_changing_them(self):
        self.condition_fixture()
        before = {p.name: p.read_bytes() for p in (self.root / "re/routes").glob("*.json")}
        result = self.cli("impact", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        pending = json.loads(result.stdout)["pending_reviews"]
        self.assertEqual({item["route_id"] for item in pending}, {"R-001", "R-002", "R-003"})
        self.assertEqual(next(item for item in pending if item["route_id"] == "R-001")["relation"], "direct")
        self.assertEqual(next(item for item in pending if item["route_id"] == "R-003")["relation"], "downstream")
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "re/routes").glob("*.json")})
        self.assertEqual(self.check().returncode, 0)
        self.assertIn("待复查与重验", (self.root / "INDEX.md").read_text(encoding="utf-8"))

    def test_new_condition_revision_reopens_review_even_when_state_is_unchanged(self):
        condition, _ = self.condition_fixture()
        for path in (self.root / "re/routes").glob("*.json"):
            route = json.loads(path.read_text(encoding="utf-8"))
            if route["id"] != "R-004":
                route["condition_reviews"] = [self.review()]
                self.write_json(path.relative_to(self.root), route)
        self.assertEqual(json.loads(self.cli("impact", self.root).stdout)["pending_reviews"], [])
        condition["revision"] = 2
        condition["history"].append({"revision": 2, "at": "2026-10-21T09:03:00Z", "state": "unknown",
                                     "reason": "New contradictory evidence needs assessment", "evidence": []})
        self.write_json("re/conditions/C-001.json", condition)
        pending = json.loads(self.cli("impact", self.root).stdout)["pending_reviews"]
        self.assertEqual(len(pending), 3)
        self.assertTrue(all(item["revision"] == 2 for item in pending))

    def test_deferred_and_retest_reviews_stay_visible_until_resolved(self):
        self.condition_fixture()
        path = "re/routes/R-001.json"
        route = json.loads((self.root / path).read_text(encoding="utf-8"))
        for outcome in ("deferred", "retest", "unchanged"):
            route["condition_reviews"].append(self.review(outcome=outcome))
            self.write_json(path, route)
            pending = json.loads(self.cli("impact", self.root).stdout)["pending_reviews"]
            self.assertEqual("R-001" in {item["route_id"] for item in pending}, outcome != "unchanged")

    def test_condition_provenance_and_future_review_are_validated(self):
        condition, _ = self.condition_fixture()
        condition["state"] = condition["history"][0]["state"] = "satisfied"
        self.write_json("re/conditions/C-001.json", condition)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("condition evidence", result.stderr)
        condition["state"] = condition["history"][0]["state"] = "unknown"
        self.write_json("re/conditions/C-001.json", condition)
        path = "re/routes/R-001.json"
        route = json.loads((self.root / path).read_text(encoding="utf-8"))
        route["condition_reviews"] = [self.review(revision=99)]
        self.write_json(path, route)
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("revision", result.stderr)

    def test_b_evidence_can_trigger_a_review_without_erasing_its_falsification(self):
        condition, sha = self.condition_fixture()
        historical = self.add_run("R-001", sha, "RUN-old-a")
        discovered = self.add_run("R-004", sha, "RUN-new-b")
        path = "re/routes/R-001.json"
        route = json.loads((self.root / path).read_text(encoding="utf-8"))
        route.update(status="falsified", evidence=[historical, discovered])
        route["closure"] = {"summary": "Old scoped observation refuted hypothesis", "scope": "old setup",
                            "criterion": "declared criterion", "coverage": "old window",
                            "control": "old control", "limitations": "old setup only",
                            "reopen_when": "new capture capability", "evidence": [historical]}
        route["closure"].update(observation_refs=[{"run_id": historical, "path": f"re/runs/{historical}/raw/out.txt", "locator": "line 1"}],
                                 control_refs=[{"run_id": historical, "path": f"re/runs/{historical}/raw/out.txt", "locator": "line 1: synthetic control"}])
        route["history"].append({"at": "2026-10-21T09:02:00Z", "from": "planned", "to": "falsified",
                                 "reason": "Old controlled observation", "evidence": [historical]})
        self.write_json(path, route)
        condition.update(state="satisfied", evidence=[discovered], revision=2)
        condition["history"].append({"revision": 2, "at": "2026-10-21T09:03:00Z", "state": "satisfied",
                                     "reason": "B obtained the observation capability", "evidence": [discovered]})
        self.write_json("re/conditions/C-001.json", condition)
        original_closure = route["closure"]
        result = self.check("--hashes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["pending_reviews"], 3)
        after = json.loads((self.root / path).read_text(encoding="utf-8"))
        self.assertEqual(after["status"], "falsified")
        self.assertEqual(after["closure"], original_closure)


if __name__ == "__main__":
    unittest.main()
