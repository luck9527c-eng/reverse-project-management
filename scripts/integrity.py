"""Exclusive project writes and independently retained execution seals.

Seals are a trusted local baseline, not protection against an attacker who can
rewrite both the baseline and verifier. Keep them in reviewed version control.
"""
import hashlib
import json
import os
from pathlib import Path


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def checked_path(root, path):
    """Reject links/reparse points on every component before a managed write."""
    root, path = root.resolve(), Path(path).absolute()
    if not path.is_relative_to(root):
        raise ValueError(f"write path escapes project: {path}")
    current = root
    for component in path.relative_to(root).parts:
        current = current / component
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError(f"refusing linked project write path: {current}")
        if not current.resolve().is_relative_to(root):
            raise ValueError(f"write path resolves outside project: {current}")
    return path


def write_new(root, path, data):
    path = checked_path(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    checked_path(root, path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    handle = os.open(path, flags, 0o666)
    with os.fdopen(handle, "wb") as stream:
        stream.write(data)


def write_json_new(root, path, value):
    write_new(root, path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def target_identity(target):
    # Paths may change on handoff; identity and provenance must not.
    return {key: value for key, value in target.items() if key != "path"}


def execution_identity(run):
    # Recovery assessments are recorded after execution; execution facts stay sealed.
    return {key: value for key, value in run.items() if key != "state"}


def read_seal(root, path):
    checked_path(root, path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"invalid seal: {path}")
    return value


def verify_seals(root, targets, runs, allow_unsealed=False):
    target_dir, run_dir = root / "re/seals/targets", root / "re/seals/runs"
    # A retained baseline may not silently disappear along with its live record.
    for path in target_dir.glob("*.json"):
        seal = read_seal(root, path)
        key = path.stem
        if key not in targets or seal.get("identity") != target_identity(targets[key]):
            raise ValueError(f"{key}: sealed target identity changed or removed")
    for path in run_dir.glob("*.json"):
        seal = read_seal(root, path)
        key = path.stem
        if key not in runs or seal.get("execution_sha256") != canonical_hash(execution_identity(runs[key])):
            raise ValueError(f"{key}: sealed execution changed or removed; preserve it and create a correction run")
    for key, run in runs.items():
        if run["status"] in {"planned", "running"}:
            continue
        paths = (target_dir / f"{run['target']['id']}.json", run_dir / f"{key}.json")
        for path in paths:
            checked_path(root, path)
            if not path.is_file() and not allow_unsealed:
                raise ValueError(f"{key}: unsealed execution/target; verify the original acquisition then run seal")


def seal_run(root, target, run):
    target_path = root / f"re/seals/targets/{target['id']}.json"
    run_path = root / f"re/seals/runs/{run['id']}.json"
    checked_path(root, target_path)
    checked_path(root, run_path)
    if os.path.lexists(run_path):
        raise ValueError(f"{run['id']}: refusing to overwrite sealed execution")
    identity = target_identity(target)
    if os.path.lexists(target_path):
        if read_seal(root, target_path).get("identity") != identity:
            raise ValueError(f"{target['id']}: sealed target identity mismatch")
    else:
        write_json_new(root, target_path, {"schema_version": 1, "identity": identity})
    write_json_new(root, run_path, {"schema_version": 1, "run_id": run["id"],
                                   "execution_sha256": canonical_hash(execution_identity(run))})
