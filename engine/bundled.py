"""Provision included reviewed guidance without reference papers or a model API."""

from __future__ import annotations

import json
import os
import time
import zipfile
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Iterator

from .installer import find_skill_source

BUILTIN_PROFILE = "jin-kao-hao-production-v1"


def reviewed_copy_upgrade(document: dict) -> dict | None:
    """Offer matching reviewed copy evidence without rewriting an older profile."""
    from .copying import validate_fingerprint

    root = find_skill_source() / "assets" / "corpus"
    metadata = root / "builtin.json"
    if not metadata.is_file():
        return None
    info = json.loads(metadata.read_text(encoding="utf-8"))
    if info.get("copy_fingerprint_manifest") != "copy-index.json":
        return None
    index_data = (root / "copy-index.json").read_bytes()
    if sha256(index_data).hexdigest() != info.get("copy_fingerprint_manifest_sha256"):
        raise ValueError("Included copying manifest checksum mismatch")
    name = "copy-fingerprints/" + document["id"] + ".json"
    rows = [row for row in json.loads(index_data)["files"] if row.get("path") == name]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("Duplicate included copying upgrade")
    data = (root / name).read_bytes()
    if len(data) != rows[0]["bytes"] or sha256(data).hexdigest() != rows[0]["sha256"]:
        raise ValueError("Included copying upgrade checksum mismatch")
    record = json.loads(data)
    if not record.get("decoded_variants"):
        return None
    if any(record.get(key) != document.get(key) for key in ("id", "relative_path", "sha256")):
        return None
    if {row.get("module") for row in record["sections"]} != set(document.get("recognized_modules", [])):
        return None
    validate_fingerprint(record, document)
    return record


def _copying_assets(info: dict, archive: Path) -> tuple[dict[str, bytes], str | None]:
    name = info.get("copy_fingerprint_manifest")
    if name is None:
        return {}, None
    if name != "copy-index.json":
        raise ValueError("Invalid included copying manifest path")
    data = (archive.parent / name).read_bytes()
    digest = sha256(data).hexdigest()
    if digest != info.get("copy_fingerprint_manifest_sha256"):
        raise ValueError("Included copying manifest checksum mismatch")
    index = json.loads(data)
    if (index.get("schema_version") != 1 or index.get("profile") != BUILTIN_PROFILE
            or index.get("source_papers") != info["source_count"]
            or index.get("source_sections") != info["reviewed_source_sections"]):
        raise ValueError("Included copying scope differs from the reviewed corpus")
    payload = {}
    for row in index["files"]:
        name = row.get("path")
        if (not isinstance(name, str) or Path(name).parent.as_posix() != "copy-fingerprints"
                or "\\" in name or ":" in name or not name.endswith(".json")):
            raise ValueError("Invalid included copying asset path")
        value = (archive.parent / name).read_bytes()
        if len(value) != row.get("bytes") or sha256(value).hexdigest() != row.get("sha256"):
            raise ValueError("Included copying asset checksum mismatch")
        payload["cache/" + name] = value
    if len(payload) != info["source_count"]:
        raise ValueError("Included copying inventory has missing or duplicate sources")
    return payload, digest


def builtin_assets() -> tuple[dict, Path]:
    root = find_skill_source() / "assets" / "corpus"
    if not (root / "builtin.json").is_file():
        raise ValueError(
            "This edition contains no distilled paper library. "
            "Distill your own paper folder or import a completed profile before writing."
        )
    manifest = json.loads((root / "builtin.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("kind") != "paper-alchemist-bundled-corpus"
            or manifest.get("profile") != BUILTIN_PROFILE):
        raise ValueError("Invalid included-corpus manifest")
    name = manifest.get("archive")
    if (not isinstance(name, str) or Path(name).name != name or "\\" in name
            or ":" in name or not name.endswith(".zip")):
        raise ValueError("Invalid included-corpus archive path")
    archive = root / name
    if sha256(archive.read_bytes()).hexdigest() != manifest.get("archive_sha256"):
        raise ValueError("Included-corpus archive checksum mismatch")
    with zipfile.ZipFile(archive) as bundle:
        index = json.loads(bundle.read("portable-profile.json"))
        sources = json.loads(bundle.read("profile/source-manifest.json"))
        terms = json.loads(bundle.read("profile/terminology.json"))
    if (index.get("profile") != BUILTIN_PROFILE or sources.get("source_kind") != "bundled-reviewed-snapshot"
            or len(sources.get("documents", [])) != manifest.get("source_count")
            or len(index.get("observations", [])) != manifest.get("reviewed_source_sections")
            or len(terms.get("entries", [])) != manifest.get("model_entries")):
        raise ValueError("Included-corpus metadata differs from its reviewed archive")
    return manifest, archive


@contextmanager
def _provision_lock(state: Path) -> Iterator[None]:
    state.mkdir(parents=True, exist_ok=True)
    path = state / "included-corpus.lock"
    deadline = time.monotonic() + 40
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("Included guidance is being provisioned; retry after that operation finishes") from None
            time.sleep(0.1)
    try:
        yield
    finally:
        path.unlink()


def ensure_builtin_profile(workspace: Path) -> dict:
    from .portable import import_profile, load_snapshot
    from .profiles import state_root

    info, archive = builtin_assets()
    state = state_root(workspace)
    directory = state / "profiles" / BUILTIN_PROFILE
    cache = state / "cache" / BUILTIN_PROFILE
    imported = False
    with _provision_lock(state):
        if directory.exists() or cache.exists():
            snapshot, errors = load_snapshot(directory)
            if errors or snapshot is None:
                raise ValueError("Existing profile or evidence is preserved; select it explicitly or use a new workspace")
            manifest = json.loads((directory / "source-manifest.json").read_text(encoding="utf-8"))
            if (manifest.get("source_kind") != "bundled-reviewed-snapshot"
                    or snapshot.get("bundle_source_commit") != info["source_commit"]):
                raise ValueError("A different existing profile is preserved; select it explicitly")
        else:
            extra, provenance = _copying_assets(info, archive)
            import_profile(archive, workspace, _extra_payload=extra, _extra_provenance=provenance)
            imported = True
        marker = directory / "included-corpus.json"
        if not marker.exists():
            marker.write_text(json.dumps({"schema_version": 1, "profile": BUILTIN_PROFILE,
                                         "archive_sha256": info["archive_sha256"],
                                         "source_commit": info["source_commit"]}, indent=2) + "\n", encoding="utf-8")
    return {"profile": BUILTIN_PROFILE, "profile_dir": str(directory), "newly_imported": imported,
            "source_count": info["source_count"], "evidence_mode": "exported-reviewed-snapshot"}


def select_generation_profile(profile: str | None, workspace: Path) -> str:
    from .profiles import profile_slug, state_root

    if profile is not None:
        return profile_slug(profile)
    state = state_root(workspace)
    active = state / "active-profile.json"
    if active.is_file():
        value = json.loads(active.read_text(encoding="utf-8"))
        name = value.get("profile") if isinstance(value, dict) else None
        if not isinstance(name, str) or profile_slug(name) != name:
            raise ValueError("Invalid active profile selection; choose a profile explicitly")
        return name
    if (state / "included-corpus.lock").exists():
        return ensure_builtin_profile(workspace)["profile"]
    candidates = sorted(path.parent.name for path in (state / "profiles").glob("*/source-manifest.json"))
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise ValueError("Several existing profiles are preserved; choose one explicitly")
    return ensure_builtin_profile(workspace)["profile"]
