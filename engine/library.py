"""Read-only paper inventory, content change detection and semantic review queues."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from .constants import MODULES
from .extractors import discover_papers, file_sha256
from .language import detect_language


def compare_documents(previous: list[dict], current: list[dict]) -> dict[str, Any]:
    before = {row["relative_path"]: row["sha256"] for row in previous}
    after = {row["relative_path"]: row["sha256"] for row in current}
    added, removed = set(after) - set(before), set(before) - set(after)
    renamed = []
    for digest in sorted(set(before.values()) & set(after.values())):
        old = sorted(name for name in removed if before[name] == digest)
        new = sorted(name for name in added if after[name] == digest)
        if len(old) == len(new) == 1:
            renamed.append({"from": old[0], "to": new[0], "sha256": digest})
            removed.remove(old[0])
            added.remove(new[0])
    by_hash: dict[str, list[str]] = defaultdict(list)
    for name, digest in after.items():
        by_hash[digest].append(name)
    result = {
        "added": sorted(added), "removed": sorted(removed), "renamed": renamed,
        "modified": sorted(name for name in before.keys() & after.keys() if before[name] != after[name]),
        "unchanged": sorted(name for name in before.keys() & after.keys() if before[name] == after[name]),
        "exact_duplicate_groups": [sorted(names) for names in by_hash.values() if len(names) > 1],
    }
    result["has_changes"] = any(result[key] for key in ("added", "removed", "renamed", "modified"))
    return result


def _profile(profile: str, workspace: Path) -> tuple[Path, Path, dict]:
    from .profiles import profile_slug, state_root

    name = profile_slug(profile)
    state = state_root(workspace)
    directory = state / "profiles" / name
    manifest = json.loads((directory / "source-manifest.json").read_text(encoding="utf-8"))
    return directory, state / "cache" / name, manifest


def scan_corpus(profile: str, workspace: Path, source: Path | None = None, *, _include_additions: bool = True) -> dict:
    if _include_additions:
        from .additions import compose_scan, registered_additions

        if registered_additions(profile, workspace):
            return compose_scan(profile, workspace, scan_corpus(profile, workspace, source, _include_additions=False))
    directory, _, manifest = _profile(profile, workspace)
    if source is None and manifest.get("source_kind") in {"bundled-reviewed-snapshot", "portable-reviewed-snapshot"}:
        from .portable import load_snapshot

        snapshot, errors = load_snapshot(directory)
        if errors or snapshot is None:
            raise ValueError("Included reviewed snapshot is invalid: " + "; ".join(errors))
        rows = [{"relative_path": d["relative_path"], "sha256": d["sha256"]} for d in manifest["documents"]]
        return {"profile": manifest["profile"], "source": manifest["source"], "read_only": True,
                "selection_limited": False, "source_available": False,
                "evidence_mode": "exported-reviewed-snapshot", "source_papers_reverified": False,
                "changes": compare_documents(rows, rows), "current_documents": rows,
                "outside_selection_count": 0,
                "notice": "Included reviewed guidance is ready; original PDFs are not needed. Additional local folders are checked separately."}
    root = (source or Path(manifest["source"])).resolve()
    selected = manifest.get("selected_sources")
    result = {"profile": manifest["profile"], "source": str(root), "read_only": True,
              "selection_limited": selected is not None, "source_available": root.is_dir()}
    if not root.is_dir():
        return {**result, "changes": None, "current_documents": [],
                "notice": "Source folder is unavailable; cached papers are not treated as deleted."}
    files = discover_papers(root)
    selected_set = set(selected) if selected is not None else None
    selected_files = [path for path in files if selected_set is None or path.relative_to(root).as_posix() in selected_set]
    rows = [{"relative_path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)}
            for path in selected_files]
    return {**result, "changes": compare_documents(manifest["documents"], rows),
            "current_documents": rows, "outside_selection_count": len(files) - len(selected_files),
            "notice": "Scanning checks file content; it neither extracts papers nor performs semantic distillation."}


def _metadata(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if not text.startswith("---\n") or len(parts) != 3:
        raise ValueError("Invalid observation metadata")
    value = yaml.safe_load(parts[1])
    if not isinstance(value, dict):
        raise ValueError("Invalid observation metadata")
    return value


def _observations(directory: Path, cache: Path, doc: dict, language_mode: str = "auto",
                  snapshot: dict | None = None) -> list[dict]:
    result = []
    frozen = {(r["document_id"], r["module"]): r for r in snapshot["observations"]} if snapshot else {}
    for module in doc["recognized_modules"] if doc["included"] else []:
        section = cache / "documents" / doc["id"] / "sections" / f"{module}.txt"
        section_text = section.read_text(encoding="utf-8") if section.is_file() else ""
        expected_language = language_mode if language_mode in {"en", "zh"} else detect_language(section_text)
        if expected_language not in {"en", "zh"}:
            expected_language = doc["language"]
        recorded = frozen.get((doc["id"], module))
        if recorded:
            expected_language = recorded["language"]
        for language in (expected_language,):
            path = cache / "observations" / language / module / f"{doc['id']}.md"
            metadata, status, digest = {}, "invalid", None
            try:
                digest = (sha256(section_text.encode()).hexdigest() if section.is_file()
                          else recorded["section_sha256"] if recorded else None)
                if not path.is_file():
                    status = "missing"
                    raise FileNotFoundError(path)
                metadata = _metadata(path)
                bound = (metadata.get("source_sha256") == doc["sha256"]
                         and metadata.get("section_sha256") == digest
                         and metadata.get("document_id") == doc["id"]
                         and metadata.get("source") == doc["relative_path"]
                         and metadata.get("language") == language and metadata.get("module") == module)
                status = metadata.get("observation_status", "pending") if bound else "stale"
                if "Pending Agent observation" in path.read_text(encoding="utf-8"):
                    status = "pending"
            except (OSError, ValueError, yaml.YAMLError):
                pass
            result.append({"module": module, "language": language, "status": status,
                           "section_sha256": digest, "observation": str(path), "section": str(section),
                           "reading_scope": metadata.get("reading_scope"),
                           "reviewer": metadata.get("reviewer"), "reviewer_kind": metadata.get("reviewer_kind"),
                           "reviewed_at": metadata.get("reviewed_at"),
                           "module_profile": str(directory / language / "modules" / f"{module}.md")})
            if recorded:
                result[-1].update(section=None, evidence_mode="exported-reviewed-snapshot")
    return result


def list_papers(profile: str, workspace: Path, cached: bool = False, *,
                _include_additions: bool = True, _source_scan: dict | None = None) -> dict:
    from .portable import load_snapshot
    from .profiles import validate_profile

    directory, cache, manifest = _profile(profile, workspace)
    scan = None if cached else (_source_scan if _source_scan is not None else scan_corpus(profile, workspace, _include_additions=False))
    current = {row["relative_path"]: row["sha256"] for row in scan["current_documents"]} if scan else None
    validation = validate_profile(profile, workspace, include_additions=False)
    snapshot, _ = load_snapshot(directory)
    rows = []
    for doc in manifest["documents"]:
        name = doc["relative_path"]
        file_status = ("not-checked" if scan is None else "unavailable" if not scan["source_available"] else
                       "removed" if name not in current else "modified" if current[name] != doc["sha256"] else "unchanged")
        observations = _observations(directory, cache, doc, manifest.get("language_mode", "auto"), snapshot)
        reviewed = sum(item["status"] == "complete" for item in observations)
        total = len(observations)
        missing_records = sorted(item["module"] for item in observations if item["status"] == "missing")
        status = (file_status if file_status in {"removed", "modified"} else
                  "excluded" if not doc["included"] else
                  "review-pending" if missing_records or not total or reviewed != total else
                  "distilled" if validation["generation_ready"] else "reviewed-awaiting-profile")
        rows.append({"source": name, "source_sha256": doc["sha256"], "id": doc["id"],
                     "status": status, "file_status": file_status, "included": doc["included"],
                     "reason": doc["reason"], "duplicate_of": doc.get("duplicate_of"),
                     "reviewed_sections": reviewed, "review_records": total,
                     "recognized_modules": doc["recognized_modules"], "missing_review_records": missing_records,
                     "unrecognized_modules": sorted(set(MODULES) - set(doc["recognized_modules"])),
                     "observations": observations})
    known = {doc["relative_path"] for doc in manifest["documents"]}
    if scan:
        rows.extend({"source": row["relative_path"], "source_sha256": row["sha256"], "status": "not-distilled",
                     "file_status": "new", "reviewed_sections": 0, "review_records": 0}
                    for row in scan["current_documents"] if row["relative_path"] not in known)
    result = {"profile": manifest["profile"], "source": manifest["source"],
            "updated_at": manifest["updated_at"], "generation_ready": validation["generation_ready"],
            "status_counts": dict(Counter(row["status"] for row in rows)), "papers": rows,
            "evidence_mode": validation["evidence_mode"],
            "scan": scan, "notice": "Distilled means reviewed recognized sections in an integrated profile; it does not certify every PDF line or generated-paper quality."}
    if _include_additions:
        from .additions import compose_inventory, registered_additions

        if registered_additions(profile, workspace):
            return compose_inventory(profile, workspace, result, cached=cached)
    return result


def review_plan(profile: str, workspace: Path, module: str | None = None,
                language: str | None = None, include_complete: bool = False, *,
                _include_additions: bool = True) -> dict:
    from .portable import load_snapshot

    directory, cache, manifest = _profile(profile, workspace)
    snapshot, _ = load_snapshot(directory)
    tasks = []
    for doc in manifest["documents"]:
        for row in _observations(directory, cache, doc, manifest.get("language_mode", "auto"), snapshot):
            if (module and row["module"] != module) or (language and row["language"] != language):
                continue
            if include_complete or row["status"] != "complete":
                tasks.append({"source": doc["relative_path"], "source_sha256": doc["sha256"], "document_id": doc["id"], **row})
    syntheses = []
    for lang in ("en", "zh"):
        for role in MODULES:
            if (module and role != module) or (language and lang != language):
                continue
            path = directory / lang / "modules" / f"{role}.md"
            try:
                metadata = _metadata(path)
            except (OSError, ValueError, yaml.YAMLError):
                metadata = {}
            status = metadata.get("synthesis_status", "missing")
            if include_complete or status != "complete":
                syntheses.append({"module": role, "language": lang, "status": status,
                                  "source_count": metadata.get("source_count", 0), "profile_file": str(path)})
    result = {"profile": manifest["profile"], "pending_only": not include_complete, "task_count": len(tasks),
            "tasks": tasks, "profiles_to_synthesize": syntheses,
            "notice": "Codex must read the section evidence and author substantive observations; no semantic review is performed by this command."}
    if _include_additions:
        from .additions import compose_review_plan, registered_additions

        if registered_additions(profile, workspace):
            return compose_review_plan(profile, workspace, result, module, language, include_complete)
    return result


def render_inventory(data: dict) -> str:
    labels = {"distilled": "Distilled recognized sections", "reviewed-awaiting-profile": "Reviewed; profile update pending",
              "review-pending": "Section review pending", "excluded": "Excluded from evidence",
              "modified": "File changed; update needed", "removed": "Missing from source folder",
              "not-distilled": "New; not distilled"}
    lines = [f"Paper profile: {data['profile']}", f"Folder: {data['source']}",
             "Ready for writing: " + ("yes" if data["generation_ready"] else "no"), "",
             "| Paper | Status | Reviewed sections |", "|---|---|---:|"]
    for row in data["papers"]:
        name = row["source"].replace("|", "\\|")
        count = f"{row['reviewed_sections']}/{row['review_records']}" if row["review_records"] else "0"
        lines.append(f"| {name} | {labels.get(row['status'], row['status'])} | {count} |")
    lines.extend(["", data["notice"]])
    if data.get("scan") and not data["scan"]["source_available"]:
        lines.append(data["scan"]["notice"])
    return "\n".join(lines) + "\n"
