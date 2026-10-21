"""Derive pending condition reviews without changing routes or their conclusions."""
from collections import deque
import json

CONDITION_STATES = {"unknown", "satisfied", "unsatisfied"}
REVIEW_OUTCOMES = {"unchanged", "retest", "deferred", "corrected", "revalidated"}
RESOLVED_OUTCOMES = {"unchanged", "corrected", "revalidated"}


def read_records(root):
    records = []
    for directory in ("conditions", "routes"):
        values = {}
        for path in sorted((root / "re" / directory).glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict) or value.get("id") != path.stem:
                raise ValueError(f"{path}: record identity mismatch")
            values[value["id"]] = value
        records.append(values)
    return records


def affected_routes(routes, condition_id):
    """Return direct consumers plus every transitive downstream route, including closed ones."""
    downstream, direct = {}, set()
    for route_id, route in routes.items():
        if condition_id in route.get("condition_ids", []):
            direct.add(route_id)
        for dependency in route.get("depends_on", []):
            downstream.setdefault(dependency, set()).add(route_id)
    pending = deque((route_id, [route_id]) for route_id in sorted(direct))
    paths = {}
    while pending:
        route_id, path = pending.popleft()
        if route_id in paths:
            continue
        paths[route_id] = path
        for child in sorted(downstream.get(route_id, [])):
            pending.append((child, path + [child]))
    return {key: {"relation": "direct" if key in direct else "downstream", "via": value}
            for key, value in paths.items()}


def impact_report(conditions, routes):
    for route_id, route in routes.items():
        for condition_id in route.get("condition_ids", []):
            if condition_id not in conditions:
                raise ValueError(f"{route_id}: unknown condition {condition_id}")
    pending = []
    for condition_id, condition in sorted(conditions.items()):
        revision = condition.get("revision")
        if type(revision) is not int or revision < 1:
            raise ValueError(f"{condition_id}: positive revision required")
        for route_id, relationship in sorted(affected_routes(routes, condition_id).items()):
            route = routes[route_id]
            reviews = [item for item in route.get("condition_reviews", [])
                       if item.get("condition_id") == condition_id]
            current = [item for item in reviews if item.get("revision") == revision]
            latest = current[-1] if current else None
            if latest and latest.get("outcome") in RESOLVED_OUTCOMES:
                continue
            pending.append({"condition_id": condition_id, "revision": revision,
                            "condition_state": condition.get("state"), "route_id": route_id,
                            "route_status": route.get("status"), **relationship,
                            "last_reviewed_revision": reviews[-1].get("revision") if reviews else None,
                            "review_outcome": latest.get("outcome") if latest else "unreviewed",
                            "trigger_evidence": condition.get("evidence", []),
                            "next_step": latest.get("next_step") if latest else "Assess scope and define the minimal retest"})
    return {"pending_reviews": pending}


def report_for_project(root):
    conditions, routes = read_records(root)
    report = impact_report(conditions, routes)
    path = root / "re/project.json"
    project = json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}
    runs = {path.parent.name: json.loads(path.read_text(encoding="utf-8-sig"))
            for path in (root / "re/runs").glob("*/run.json")}
    report["dispute_impacts"] = dispute_impacts(project, routes, conditions, runs)
    return report


def evidence_lineage(values, runs):
    pending, sources = list(values), set()
    while pending:
        key = pending.pop()
        if ("run", key) in sources:
            continue
        sources.add(("run", key))
        provenance = runs.get(key, {}).get("provenance") or {}
        if provenance.get("capture_id"):
            sources.add(("capture", provenance["capture_id"]))
        sources.update(("raw", path) for path in provenance.get("raw_artifacts", []))
        pending.extend(provenance.get("source_runs", []))
    return sources


def dispute_impacts(project, routes, conditions=None, runs=None):
    """Open disputes affect current usability without erasing historical status."""
    result = []
    conditions, runs = conditions or {}, runs or {}
    for dispute in project.get("disputes", []):
        if dispute.get("status") != "open":
            continue
        direct = set(dispute.get("route_ids", []))
        evidence = evidence_lineage(dispute.get("supporting", []) + dispute.get("contradicting", []), runs)
        condition_ids = {key for key, condition in conditions.items()
                         if evidence.intersection(evidence_lineage(condition.get("evidence", []), runs))}
        direct.update(key for key, route in routes.items()
                      if evidence.intersection(evidence_lineage(route.get("evidence", []), runs))
                      or condition_ids.intersection(route.get("condition_ids", [])))
        pending = deque((key, [key]) for key in sorted(direct))
        seen = set()
        while pending:
            key, via = pending.popleft()
            if key in seen or key not in routes:
                continue
            seen.add(key)
            result.append({"dispute_id": dispute.get("id"), "route_id": key,
                           "route_status": routes[key].get("status"), "via": via,
                           "relation": "direct" if key in direct else "downstream"})
            for child, route in sorted(routes.items()):
                if key in route.get("depends_on", []):
                    pending.append((child, via + [child]))
    return result
