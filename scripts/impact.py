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
    return impact_report(*read_records(root))
