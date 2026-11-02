"""Share a reviewed base and its separately bound additions as one atomic library."""

from __future__ import annotations

import io
import json
import stat
import tempfile
import zipfile
from hashlib import sha256
from pathlib import Path

from .portable import SNAPSHOT, _check_index, _json

LIBRARY_SNAPSHOT = "portable-library.json"


def _portable_layer(data: bytes) -> tuple[bytes, dict]:
    """Remove machine-specific manifest origins without changing semantic bindings."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        index = json.loads(archive.read(SNAPSHOT))
        payload = {row["path"]: archive.read(row["path"]) for row in index["files"]}
    _check_index(index, payload)
    manifest = json.loads(payload["profile/source-manifest.json"])
    if manifest.get("source_kind") != "bundled-reviewed-snapshot":
        manifest["source"] = "reviewed://" + index["profile"]
        manifest["source_kind"] = "portable-reviewed-snapshot"
        manifest["source_origin"] = {
            "original_manifest_sha256": sha256(payload["profile/source-manifest.json"]).hexdigest(),
            "physical_source_paths_included": False,
        }
        for document in manifest["documents"]:
            document["path"] = document["relative_path"]
        payload["profile/source-manifest.json"] = _json(manifest)
        if "profile/source-catalogue.json" in payload:
            catalogue = json.loads(payload["profile/source-catalogue.json"])
            if "source_manifest_sha256" in catalogue:
                catalogue["original_source_manifest_sha256"] = catalogue.pop("source_manifest_sha256")
            catalogue["portable_source_manifest_sha256"] = sha256(payload["profile/source-manifest.json"]).hexdigest()
            payload["profile/source-catalogue.json"] = _json(catalogue)
            if "profile/terminology.json" in payload:
                terms = json.loads(payload["profile/terminology.json"])
                if "source_catalogue_sha256" in terms:
                    terms["source_catalogue_sha256"] = sha256(payload["profile/source-catalogue.json"]).hexdigest()
                    payload["profile/terminology.json"] = _json(terms)
    index["source_origin_redacted"] = True
    index["files"] = [dict(path=name, bytes=len(value), sha256=sha256(value).hexdigest())
                      for name, value in sorted(payload.items())]
    _check_index(index, payload)
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(SNAPSHOT, _json(index))
        for name, value in sorted(payload.items()):
            archive.writestr(name, value)
    return result.getvalue(), index


def export_library(profile: str, workspace: Path, out: Path, registry: Path | None = None) -> dict:
    from .additions import registered_additions
    from .portable import export_profile
    from .profiles import state_root, validate_profile

    if not validate_profile(profile, workspace)["generation_ready"]:
        raise ValueError("Only a current, semantically complete integrated library can be exported")
    if out.exists():
        raise FileExistsError(f"Profile archive already exists: {out}")
    additions = [row for row in registered_additions(profile, workspace) if row["active"]]
    names = [profile, *[row["profile"] for row in additions]]
    state = state_root(workspace)
    payload, rows = {}, []
    sections = 0
    with tempfile.TemporaryDirectory(prefix="library-export-", dir=state) as temporary:
        for name in names:
            target = Path(temporary) / (name + ".zip")
            export_profile(name, workspace, target, registry if name == profile else None, _include_additions=False)
            data, index = _portable_layer(target.read_bytes())
            path = f"profiles/{name}.zip"
            payload[path] = data
            rows.append(dict(profile=name, path=path, bytes=len(data), sha256=sha256(data).hexdigest()))
            sections += len(index["observations"])
    index = dict(schema_version=1, kind="paper-alchemist-reviewed-library", profile=profile, files=rows,
                 additions=[dict(profile=row["profile"], source="reviewed://" + row["profile"],
                                 source_kind="portable-reviewed-snapshot", active=True) for row in additions],
                 raw_source_papers_included=False, extracted_source_prose_included=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as handle, zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(LIBRARY_SNAPSHOT, _json(index))
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    return {"profile": profile, "archive": str(out), "archive_sha256": sha256(out.read_bytes()).hexdigest(),
            "profiles": names, "reviewed_source_sections": sections, "evidence_mode": "reviewed-base-and-additions",
            "raw_source_papers_included": False, "extracted_source_prose_included": False}


def import_library(archive: Path, workspace: Path) -> dict:
    from .portable import import_profile
    from .profiles import profile_slug, state_root, validate_profile

    try:
        with zipfile.ZipFile(archive) as bundle:
            infos = bundle.infolist()
            names = [row.filename for row in infos]
            if (len(names) != len(set(name.casefold() for name in names))
                    or sum(row.file_size for row in infos) > 512 * 1024 * 1024):
                raise ValueError("Invalid reviewed-library inventory")
            index = json.loads(bundle.read(LIBRARY_SNAPSHOT))
            if (not isinstance(index, dict) or index.get("schema_version") != 1
                    or index.get("kind") != "paper-alchemist-reviewed-library"):
                raise ValueError("Unsupported reviewed library")
            root, rows, additions = index.get("profile"), index.get("files"), index.get("additions")
            if (not isinstance(root, str) or profile_slug(root) != root or not isinstance(rows, list)
                    or not rows or not isinstance(additions, list)):
                raise ValueError("Invalid reviewed-library structure")
            members, profiles = [], []
            for row in rows:
                name = row.get("profile")
                if (not isinstance(name, str) or profile_slug(name) != name
                        or row.get("path") != f"profiles/{name}.zip"):
                    raise ValueError("Invalid reviewed-library profile path")
                profiles.append(name)
                members.append(row["path"])
            if (root not in profiles or len(profiles) != len(set(n.casefold() for n in profiles))
                    or set(names) != {LIBRARY_SNAPSHOT, *members}
                    or {row.get("profile") for row in additions} != set(profiles) - {root}
                    or len(additions) != len(profiles) - 1):
                raise ValueError("Reviewed-library layers do not match the inventory")
            for row in additions:
                if (row.get("active") is not True or row.get("source") != "reviewed://" + row["profile"]
                        or row.get("source_kind") != "portable-reviewed-snapshot"):
                    raise ValueError("Imported library cannot register a live source folder")
            for info in infos:
                if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16) or info.file_size > 128 * 1024 * 1024:
                    raise ValueError("Unsupported reviewed-library archive member")
            payload = {row["path"]: bundle.read(row["path"]) for row in rows}
            for row in rows:
                data = payload[row["path"]]
                if len(data) != row.get("bytes") or sha256(data).hexdigest() != row.get("sha256"):
                    raise ValueError("Reviewed-library checksum mismatch")
    except (zipfile.BadZipFile, KeyError, TypeError, AttributeError, UnicodeError, RuntimeError,
            NotImplementedError) as exc:
        raise ValueError(f"Invalid reviewed library: {exc}") from exc
    state = state_root(workspace)
    descriptor = state / "source-additions" / (root + ".json")
    destinations = [state / kind / name for name in profiles for kind in ("profiles", "cache")]
    if descriptor.exists() or any(path.exists() for path in destinations):
        raise FileExistsError("Reviewed-library state already exists; existing evidence is preserved")
    state.mkdir(parents=True, exist_ok=True)
    moved = []
    with tempfile.TemporaryDirectory(prefix="library-import-", dir=state) as temporary:
        staging = Path(temporary)
        expanded_bytes = 0
        for row in rows:
            nested = staging / (row["profile"] + ".zip")
            nested.write_bytes(payload[row["path"]])
            with zipfile.ZipFile(nested) as inner:
                if LIBRARY_SNAPSHOT in inner.namelist():
                    raise ValueError("Nested reviewed libraries are unsupported")
                expanded_bytes += sum(info.file_size for info in inner.infolist())
                if expanded_bytes > 512 * 1024 * 1024:
                    raise ValueError("Reviewed-library expanded files exceed the size limit")
            imported = import_profile(nested, staging)
            if imported["profile"] != row["profile"]:
                raise ValueError("Nested profile identity differs from the reviewed-library inventory")
        staged_state = state_root(staging)
        staged_descriptor = staged_state / "source-additions" / descriptor.name
        staged_descriptor.parent.mkdir()
        staged_descriptor.write_bytes(_json(dict(schema_version=1, profile=root, layers=additions)))
        validation = validate_profile(root, staging)
        if not validation["generation_ready"]:
            raise ValueError("Imported reviewed-library evidence is incomplete")
        hashes = set()
        for name in profiles:
            manifest = json.loads((staged_state / "profiles" / name / "source-manifest.json").read_text())
            current = {row["sha256"] for row in manifest["documents"] if row.get("included")}
            if hashes & current:
                raise ValueError("Reviewed-library profiles contain duplicate source evidence")
            hashes.update(current)
        pairs = [(staged_state / kind / name, state / kind / name)
                 for name in profiles for kind in ("cache", "profiles")]
        pairs.append((staged_descriptor, descriptor))
        active_created = False
        active = state / "active-profile.json"
        try:
            for source, destination in pairs:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise FileExistsError("Reviewed-library state appeared during import")
                source.rename(destination)
                moved.append((source, destination))
            if not active.exists():
                with active.open("x", encoding="utf-8") as handle:
                    active_created = True
                    handle.write(_json({"profile": root}).decode())
        except OSError:
            if active_created:
                active.unlink(missing_ok=True)
            for source, destination in reversed(moved):
                destination.rename(source)
            raise
    return {"profile": root, "profiles": profiles, "generation_ready": True,
            "archive_sha256": sha256(archive.read_bytes()).hexdigest(),
            "evidence_mode": "reviewed-base-and-additions", "source_papers_reverified": False,
            "source_count": len(hashes),
            "notice": "The reviewed base and added-paper guidance are ready. Rebind an added folder explicitly to check later source changes."}
