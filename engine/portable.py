"""Portable reviewed profiles without source papers or extracted paper prose."""

from __future__ import annotations

import json
import re
import stat
import tempfile
import zipfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from . import __version__
from .constants import MODULES
from .terminology import load_registry

SNAPSHOT = "portable-profile.json"
_PROFILE_FILES = {
    "source-manifest.json", "quality.json", "terminology.json", "source-catalogue.json",
    "en/integrated.md", "zh/integrated.md", "bilingual/cross-lingual.md", "bilingual/conflicts.md",
    *(f"{language}/modules/{module}.md" for language in ("en", "zh") for module in MODULES),
}
_REQUIRED_FILES = {f"profile/{name}" for name in _PROFILE_FILES - {"terminology.json", "source-catalogue.json"}}
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _json(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _metadata(data: bytes) -> dict:
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    parts = text.split("---", 2)
    if not text.startswith("---\n") or len(parts) != 3:
        raise ValueError("Missing profile or observation metadata")
    value = yaml.safe_load(parts[1])
    if not isinstance(value, dict):
        raise ValueError("Invalid profile or observation metadata")
    return value


def _allowed(name: str) -> bool:
    if not isinstance(name, str) or "\\" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(p in {".", ".."} for p in path.parts):
        return False
    if any(":" in p or p.rstrip(". ") != p or p.split(".")[0].casefold() in _RESERVED for p in path.parts):
        return False
    if name.startswith("profile/"):
        return name.removeprefix("profile/") in _PROFILE_FILES
    if name == "cache/section-maps.json":
        return True
    if re.fullmatch(r"cache/copy-fingerprints/[\w-]+\.json", name):
        return True
    return bool(re.fullmatch(r"cache/observations/(?:en|zh)/(?:" + "|".join(MODULES) + r")/[\w-]+\.md", name))


def _target(profile_dir: Path, name: str) -> Path:
    if not _allowed(name):
        raise ValueError(f"Unsupported profile asset path: {name}")
    prefix, relative = name.split("/", 1)
    root = profile_dir if prefix == "profile" else profile_dir.parent.parent / "cache" / profile_dir.name
    target = root.joinpath(*PurePosixPath(relative).parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Profile asset leaves its destination")
    return target


def _check_index(index: dict, payload: dict[str, bytes]) -> None:
    from .profiles import profile_slug

    if not isinstance(index, dict) or index.get("schema_version") != 1 or index.get("kind") != "paper-alchemist-reviewed-profile":
        raise ValueError("Unsupported portable profile")
    name = index.get("profile")
    if not isinstance(name, str) or profile_slug(name) != name:
        raise ValueError("Invalid portable profile name")
    files = index.get("files")
    if not isinstance(files, list) or any(not isinstance(row, dict) for row in files):
        raise ValueError("Portable profile needs a file inventory")
    names = [row.get("path") for row in files]
    if any(not _allowed(path) for path in names) or len(names) != len(set(path.casefold() for path in names)):
        raise ValueError("Invalid or colliding profile asset paths")
    if set(names) != set(payload) or not _REQUIRED_FILES <= set(names):
        raise ValueError("Portable profile inventory does not match its files")
    for row in files:
        data = payload[row["path"]]
        if len(data) != row.get("bytes") or sha256(data).hexdigest() != row.get("sha256"):
            raise ValueError(f"Profile asset checksum mismatch: {row['path']}")
        data.decode("utf-8")
    manifest = json.loads(payload["profile/source-manifest.json"])
    quality = json.loads(payload["profile/quality.json"])
    if not isinstance(manifest, dict) or not isinstance(quality, dict):
        raise ValueError("Invalid portable source manifest or quality record")
    if manifest.get("profile") != name or quality.get("profile") != name:
        raise ValueError("Portable profile identities differ")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or any(not isinstance(row, dict) for row in documents):
        raise ValueError("Invalid portable source inventory")
    included = {row["id"]: row for row in documents if row.get("included")}
    from .extractors import PDF_TEXT_ORDERS, normalize_pdf_order_review

    for document in included.values():
        order = document.get("pdf_text_order", "auto")
        if order not in PDF_TEXT_ORDERS or (order != "auto" and document.get("format") != "pdf"):
            raise ValueError("Invalid portable PDF text-order choice")
        review = document.get("pdf_text_order_review")
        if review:
            reviewed = normalize_pdf_order_review(review)
            if (reviewed["source"] != document.get("relative_path")
                    or reviewed["source_sha256"] != document.get("sha256")
                    or reviewed["pdf_text_order"] != order):
                raise ValueError("Portable PDF text-order review differs from its source")
        elif order != "auto":
            raise ValueError("Portable raw PDF order needs a source-bound review")
    observations = index.get("observations")
    if (not isinstance(observations, list) or not observations or not included
            or any(not isinstance(row, dict) for row in observations)):
        raise ValueError("Portable profile needs reviewed source observations")
    expected_paths = set()
    evidence = defaultdict(list)
    for row in observations:
        language, module, doc_id = row.get("language"), row.get("module"), row.get("document_id")
        if language not in {"en", "zh"} or module not in MODULES or doc_id not in included:
            raise ValueError("Invalid portable observation identity")
        path = f"cache/observations/{language}/{module}/{doc_id}.md"
        if row.get("path") != path or path not in payload or path in expected_paths:
            raise ValueError("Missing or duplicate portable observation")
        expected_paths.add(path)
        meta = _metadata(payload[path])
        document = included[doc_id]
        fields = ("document_id", "language", "module", "source", "source_sha256", "section_sha256", "content_mode")
        if (any(meta.get(key) != row.get(key) for key in fields)
                or meta.get("observation_status") != "complete"
                or meta.get("source") != document.get("relative_path")
                or meta.get("source_sha256") != document.get("sha256")
                or module not in document.get("recognized_modules", [])
                or not _HEX.fullmatch(str(meta.get("section_sha256", "")))
                or not _HEX.fullmatch(str(meta.get("source_sha256", "")))
                or "Pending Agent observation" in payload[path].decode("utf-8")):
            raise ValueError(f"Invalid reviewed snapshot binding: {path}")
        evidence[language, module].append(f"{row['source']}:{row['content_mode']}:{row['section_sha256']}")
    if {p for p in payload if p.startswith("cache/observations/")} != expected_paths:
        raise ValueError("Unlisted portable source observations")
    if {(row["id"], module) for row in included.values() for module in row["recognized_modules"]} != {(r["document_id"], r["module"]) for r in observations}:
        raise ValueError("Portable observations omit recognized source sections")
    for language in ("en", "zh"):
        for module in MODULES:
            entries = evidence[language, module]
            fingerprint = sha256("\n".join(sorted(entries)).encode("utf-8")).hexdigest()
            meta = _metadata(payload[f"profile/{language}/modules/{module}.md"])
            if (quality.get("module_samples", {}).get(language, {}).get(module) != len(entries)
                    or quality.get("module_fingerprints", {}).get(language, {}).get(module) != fingerprint
                    or meta.get("source_count") != len(entries)
                    or meta.get("synthesis_status") != "complete"
                    or meta.get("profile") != name or meta.get("language") != language or meta.get("module") != module
                    or (meta.get("evidence_fingerprint") is not None and meta["evidence_fingerprint"] != fingerprint)):
                raise ValueError(f"Portable synthesis differs from its reviewed evidence: {language}/{module}")
    if "profile/terminology.json" in payload:
        terms = json.loads(payload["profile/terminology.json"])
        catalogue = terms.get("source_catalogue")
        if catalogue is not None and (catalogue != "source-catalogue.json" or "profile/source-catalogue.json" not in payload):
            raise ValueError("Portable terminology catalogue is missing")
    from .copying import validate_fingerprint

    reviewed = {(row["document_id"], row["module"]): row["section_sha256"] for row in observations}
    for path, data in payload.items():
        if path.startswith("cache/copy-fingerprints/"):
            identifier = PurePosixPath(path).stem
            if identifier not in included:
                raise ValueError("Copy fingerprints refer to an excluded source")
            record = json.loads(data)
            validate_fingerprint(record, included[identifier])
            if any(reviewed.get((identifier, row["module"])) != row["section_sha256"] for row in record["sections"]):
                raise ValueError("Copy fingerprints differ from reviewed source sections")


def load_snapshot(profile_dir: Path) -> tuple[dict | None, list[str]]:
    """Verify the imported asset bytes; never imply a live PDF re-read."""
    marker = profile_dir / SNAPSHOT
    if not marker.is_file():
        return None, []
    try:
        index = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(index, dict) or not isinstance(index.get("files"), list):
            raise ValueError("Invalid portable file inventory")
        payload = {row["path"]: _target(profile_dir, row["path"]).read_bytes() for row in index["files"]}
        _check_index(index, payload)
        if index["profile"] != profile_dir.name:
            raise ValueError("Imported profile directory differs from the snapshot")
        return index, []
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, yaml.YAMLError) as exc:
        return None, [f"Invalid imported profile snapshot: {exc}"]


def export_profile(profile: str, workspace: Path, out: Path, registry: Path | None = None, *,
                   _include_additions: bool = True) -> dict:
    from .profiles import profile_slug, state_root, utc_now, validate_profile

    name = profile_slug(profile)
    validation = validate_profile(name, workspace, include_additions=_include_additions)
    if not validation["generation_ready"]:
        raise ValueError("Only a current, semantically complete integrated profile can be exported")
    if _include_additions:
        from .additions import registered_additions
        from .library_portable import export_library

        if any(row["active"] for row in registered_additions(name, workspace)):
            return export_library(name, workspace, out, registry)
    if out.exists():
        raise FileExistsError(f"Profile archive already exists: {out}")
    profile_dir = state_root(workspace) / "profiles" / name
    cache = state_root(workspace) / "cache" / name
    payload = {f"profile/{relative}": (profile_dir / relative).read_bytes() for relative in sorted(_PROFILE_FILES)
               if relative not in {"terminology.json", "source-catalogue.json"}}
    observations = []
    for language in ("en", "zh"):
        for module in MODULES:
            for path in sorted((cache / "observations" / language / module).glob("*.md")):
                data = path.read_bytes()
                meta = _metadata(data)
                relative = "cache/" + path.relative_to(cache).as_posix()
                payload[relative] = data
                observations.append({"path": relative, **{key: meta.get(key) for key in (
                    "document_id", "source", "language", "module", "source_sha256", "section_sha256", "content_mode")}})
    if (cache / "section-maps.json").is_file():
        payload["cache/section-maps.json"] = (cache / "section-maps.json").read_bytes()
    from .copying import profile_fingerprints

    payload.update(profile_fingerprints(name, workspace))
    registry = registry or (profile_dir / "terminology.json" if (profile_dir / "terminology.json").is_file() else None)
    registry_provenance = None
    if registry:
        terms = load_registry(registry)
        registry_provenance = {"sha256_literal_bytes": sha256(registry.read_bytes()).hexdigest()}
        if terms.get("source_catalogue"):
            catalogue = registry.parent / terms["source_catalogue"]
            data = catalogue.read_bytes()
            json.loads(data)
            payload["profile/source-catalogue.json"] = data
            registry_provenance["original_source_catalogue"] = terms["source_catalogue"]
            registry_provenance["catalogue_sha256_literal_bytes"] = sha256(data).hexdigest()
            terms["source_catalogue"] = "source-catalogue.json"
        payload["profile/terminology.json"] = _json(terms)
    index = dict(schema_version=1, kind="paper-alchemist-reviewed-profile", profile=name,
                 exported_at=utc_now(), producer_version=__version__, evidence_mode="exported-reviewed-snapshot",
                 raw_source_papers_included=False, extracted_source_prose_included=False,
                 observations=observations, registry_provenance=registry_provenance,
                 files=[dict(path=path, bytes=len(data), sha256=sha256(data).hexdigest()) for path, data in sorted(payload.items())],
                 limits=["Checksums bind the exported guidance and semantic observations; they do not re-read source papers or certify manuscript quality.",
                         "Live folder availability/changes must be checked separately. Updating re-extracts supplied papers and reuses only matching observations."])
    _check_index(index, payload)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("xb") as handle, zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(SNAPSHOT, _json(index))
        for path, data in sorted(payload.items()):
            archive.writestr(path, data)
    return {"profile": name, "archive": str(out), "archive_sha256": sha256(out.read_bytes()).hexdigest(),
            "files": len(payload), "reviewed_source_sections": len(observations),
            "evidence_mode": index["evidence_mode"], "raw_source_papers_included": False,
            "extracted_source_prose_included": False, "terminology_included": registry is not None}


def import_profile(archive: Path, workspace: Path, *, _extra_payload: dict[str, bytes] | None = None,
                   _extra_provenance: str | None = None) -> dict:
    from .profiles import state_root, validate_profile

    payload = {}
    try:
        with zipfile.ZipFile(archive) as bundle:
            from .library_portable import LIBRARY_SNAPSHOT, import_library

            if LIBRARY_SNAPSHOT in bundle.namelist():
                return import_library(archive, workspace)
            infos = bundle.infolist()
            names = [row.filename for row in infos]
            if (SNAPSHOT not in names or len(names) != len(set(name.casefold() for name in names))
                    or sum(row.file_size for row in infos) > 512 * 1024 * 1024):
                raise ValueError("Invalid portable archive inventory")
            for row in infos:
                mode = row.external_attr >> 16
                if (row.is_dir() or stat.S_ISLNK(mode) or row.file_size > 32 * 1024 * 1024
                        or (row.filename != SNAPSHOT and not _allowed(row.filename))):
                    raise ValueError(f"Unsupported portable archive member: {row.filename}")
                data = bundle.read(row)
                if row.filename == SNAPSHOT:
                    index = json.loads(data)
                else:
                    payload[row.filename] = data
    except (zipfile.BadZipFile, UnicodeError, KeyError, RuntimeError, NotImplementedError) as exc:
        raise ValueError(f"Invalid portable archive: {exc}") from exc
    try:
        _check_index(index, payload)
        if _extra_payload:
            if (any(not name.startswith("cache/copy-fingerprints/") or not _allowed(name) for name in _extra_payload)
                    or payload.keys() & _extra_payload.keys()):
                raise ValueError("Invalid or colliding bundled copying assets")
            payload.update(_extra_payload)
            index["copy_fingerprint_manifest_sha256"] = _extra_provenance
            index["files"] = [dict(path=name, bytes=len(data), sha256=sha256(data).hexdigest())
                              for name, data in sorted(payload.items())]
            _check_index(index, payload)
    except (KeyError, TypeError, AttributeError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid portable profile structure: {exc}") from exc
    name = index["profile"]
    state = state_root(workspace)
    profile_dir, cache = state / "profiles" / name, state / "cache" / name
    if profile_dir.exists() or cache.exists():
        raise FileExistsError(f"Profile or evidence cache already exists: {name}")
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="profile-import-", dir=state) as temporary:
        staging = Path(temporary).resolve()
        if not staging.is_relative_to(state.resolve()):
            raise ValueError("Profile staging leaves the workspace")
        staged_profile = staging / ".paper-alchemist" / "profiles" / name
        for path, data in payload.items():
            target = _target(staged_profile, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (staged_profile / SNAPSHOT).write_bytes(_json(index))
        validation = validate_profile(name, staging)
        if not validation["generation_ready"]:
            raise ValueError("Imported profile is incomplete: " + "; ".join(validation["errors"] + validation["incomplete_observations"]))
        if (staged_profile / "terminology.json").is_file():
            load_registry(staged_profile / "terminology.json")
        profile_dir.parent.mkdir(exist_ok=True)
        cache.parent.mkdir(exist_ok=True)
        staged_cache = staged_profile.parent.parent / "cache" / name
        if profile_dir.exists() or cache.exists():
            raise FileExistsError(f"Profile appeared during import: {name}")
        staged_cache.rename(cache)
        try:
            staged_profile.rename(profile_dir)
        except OSError:
            cache.rename(staged_cache)
            raise
    return {"profile": name, "profile_dir": str(profile_dir), "generation_ready": True,
            "archive_sha256": sha256(archive.read_bytes()).hexdigest(),
            "evidence_mode": "exported-reviewed-snapshot", "source_papers_reverified": False,
            "terminology_registry": str(profile_dir / "terminology.json") if (profile_dir / "terminology.json").is_file() else None,
            "notice": "Reviewed guidance is ready for use; source-folder checks and later source updates remain separate."}
