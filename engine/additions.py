"""Incremental source layers retain a reviewed base and compose current module guidance."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Iterator
from uuid import uuid4


def _paths(profile: str, workspace: Path) -> tuple[str, Path, Path]:
    from .profiles import profile_slug, state_root

    name = profile_slug(profile)
    state = state_root(workspace)
    return name, state / "profiles" / name, state / "source-additions" / f"{name}.json"


def _read(path: Path, default: dict | None = None) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else (default or {})


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def registered_additions(profile: str, workspace: Path) -> list[dict]:
    from .profiles import profile_slug

    name, _, path = _paths(profile, workspace)
    data = _read(path)
    if not data:
        return []
    if data.get("schema_version") != 1 or data.get("profile") != name or not isinstance(data.get("layers"), list):
        raise ValueError("Invalid added-paper source layers")
    seen = set()
    for layer in data["layers"]:
        child = layer.get("profile")
        if (not isinstance(child, str) or profile_slug(child) != child or child == name or child in seen
                or not isinstance(layer.get("source"), str) or not isinstance(layer.get("active"), bool)):
            raise ValueError("Invalid or colliding added-paper layer")
        seen.add(child)
    return data["layers"]


def _known_sources(profile: str, workspace: Path, exclude: str | None = None) -> dict[str, dict]:
    from .profiles import state_root

    root = state_root(workspace) / "profiles"
    names = [profile, *[r["profile"] for r in registered_additions(profile, workspace)
                       if r["active"] and r["profile"] != exclude]]
    known = {}
    for name in names:
        for doc in _read(root / name / "source-manifest.json").get("documents", []):
            if doc.get("included"):
                known.setdefault(doc["sha256"], {"profile": name, "source": doc["relative_path"]})
    return known


def scan_addition(profile: str, workspace: Path, layer: dict) -> dict:
    from .extractors import discover_papers, file_sha256
    from .library import compare_documents
    from .profiles import state_root

    if layer.get("source_kind") == "portable-reviewed-snapshot":
        return {"profile": layer["profile"], "source": layer["source"], "read_only": True,
                "source_available": False, "changes": None, "current_documents": [], "duplicate_sources": [],
                "notice": "Reviewed imported guidance is retained; rebind a local added-paper folder explicitly to scan it."}
    source = Path(layer["source"])
    manifest = _read(state_root(workspace) / "profiles" / layer["profile"] / "source-manifest.json")
    result = {"profile": layer["profile"], "source": str(source), "read_only": True,
              "selection_limited": False, "source_available": source.is_dir()}
    if not source.is_dir():
        return {**result, "changes": None, "current_documents": [], "duplicate_sources": [],
                "notice": "Added-paper folder is unavailable; reviewed guidance is retained, not treated as deleted."}
    known = _known_sources(profile, workspace, layer["profile"])
    rows, duplicates = [], []
    for path in discover_papers(source):
        name, digest = path.relative_to(source).as_posix(), file_sha256(path)
        if digest in known:
            duplicates.append({"source": name, "sha256": digest, "already_reviewed_in": known[digest]})
        else:
            rows.append({"relative_path": name, "sha256": digest})
    return {**result, "changes": compare_documents(manifest.get("documents", []), rows),
            "current_documents": rows, "duplicate_sources": duplicates, "outside_selection_count": len(duplicates),
            "notice": "Only this added-paper folder is compared. The reviewed base is not a missing local input."}


@contextmanager
def _layer_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 40
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError("An added-paper update is already running; retry after it finishes") from None
            time.sleep(0.1)
    try:
        yield
    finally:
        path.unlink()


def extend_profile(profile: str, source: Path, workspace: Path, *, language: str | None = None,
                   min_characters: int | None = None, ocr_mode: str | None = None,
                   section_map: Path | None = None, pdf_order_map: Path | None = None,
                   addition_profile: str | None = None, rebind_source: bool = False) -> dict:
    from .bundled import BUILTIN_PROFILE, ensure_builtin_profile
    from .profiles import build_profile, profile_slug, state_root, utc_now, validate_profile

    name, directory, descriptor = _paths(profile, workspace)
    for path in (state_root(workspace) / "source-additions").glob("*.json"):
        if path != descriptor and any(row["profile"] == name for row in registered_additions(path.stem, workspace)):
            raise ValueError("Add this folder to the parent library; nested added-paper layers are unsupported")
    if not directory.exists() and name == BUILTIN_PROFILE:
        ensure_builtin_profile(workspace)
    if not validate_profile(name, workspace, include_additions=False)["generation_ready"]:
        raise ValueError("Finish the reviewed base profile before adding another paper folder")
    source = source.expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError("The added-paper folder is unavailable")
    with _layer_lock(descriptor.with_suffix(".lock")):
        layers = registered_additions(name, workspace)
        if addition_profile:
            child = profile_slug(addition_profile)
            matches = [r for r in layers if r["profile"] == child]
            if len(matches) != 1:
                raise ValueError("Choose an existing added-paper layer for relocation")
            layer = matches[0]
            if Path(layer["source"]).resolve() != source and not rebind_source:
                raise ValueError("Relocating added papers requires --rebind-source")
        else:
            matches = [r for r in layers if Path(r["source"]).resolve() == source]
            if matches:
                layer = matches[0]
            else:
                child = profile_slug(name[:65] + "-add-" + sha256(str(source).encode()).hexdigest()[:10])
                child_dir = state_root(workspace) / "profiles" / child
                if child_dir.exists():
                    raise ValueError("The proposed added-paper profile already exists; existing state is preserved")
                layer = {"profile": child, "source": str(source), "active": False}
                layers.append(layer)
        layer["source"] = str(source)
        layer.pop("source_kind", None)
        scan = scan_addition(name, workspace, layer)
        selected = {row["relative_path"] for row in scan["current_documents"]}
        child_dir = state_root(workspace) / "profiles" / layer["profile"]
        # Register unfinished work before extraction so a failed first attempt
        # remains visible and can be resumed instead of stranding an orphan.
        layer["active"] = bool(selected)
        _write(descriptor, {"schema_version": 1, "profile": name, "layers": layers})
        if selected:
            result = build_profile(source, layer["profile"], workspace, language=language,
                                   update=child_dir.exists(), min_characters=min_characters, ocr_mode=ocr_mode,
                                   include_sources=selected, section_map=section_map, pdf_order_map=pdf_order_map,
                                   rebind_source=rebind_source)
            layer["active"] = result["documents_included"] > 0
        else:
            layer["active"] = False
            result = {"documents_found": 0, "documents_included": 0, "pending_observation_count": 0}
        layer["updated_at"] = utc_now()
        layer["duplicate_sources"] = scan["duplicate_sources"]
        _write(descriptor, {"schema_version": 1, "profile": name, "layers": layers})
        _write(state_root(workspace) / "active-profile.json", {"profile": name})
    baseline = _read(directory / "source-manifest.json")
    return {"profile": name, "extension_profile": layer["profile"],
            "profile_dir": str(child_dir), "source": str(source),
            "baseline_source_papers": sum(bool(d.get("included")) for d in baseline["documents"]),
            "new_source_papers": result["documents_included"], "base_profile_changed": False,
            "duplicate_sources": scan["duplicate_sources"], "extraction": result,
            "notice": "Finish the added profile's source observations, module synthesis and integration. The reviewed base remains intact."}


def validate_additions(profile: str, workspace: Path, *, check_sources: bool = True) -> dict:
    from .profiles import state_root, validate_profile

    _, _, descriptor = _paths(profile, workspace)
    if descriptor.with_suffix(".lock").exists():
        return {"has_additions": True, "ready": False, "profiles": [],
                "incomplete_profiles": ["added-paper-update-running"], "errors": [], "warnings": []}
    layers = registered_additions(profile, workspace)
    results, incomplete, errors, warnings = [], [], [], []
    for layer in layers:
        if not layer["active"]:
            continue
        result = validate_profile(layer["profile"], workspace, include_additions=False)
        scan = scan_addition(profile, workspace, layer) if check_sources else None
        changes = (scan or {}).get("changes")
        changed = bool(changes and changes["has_changes"])
        ready = result["generation_ready"] and not changed
        results.append({"profile": layer["profile"], "source": layer["source"], "ready": ready,
                        "validation": result, "scan": scan})
        if not ready:
            incomplete.extend(f"{layer['profile']}/{x}" for x in result["incomplete_profiles"])
            if changed:
                incomplete.append(layer["profile"] + "/source-update")
        errors.extend(f"{layer['profile']}: {x}" for x in result["errors"])
        warnings.extend(f"{layer['profile']}: {x}" for x in result["warnings"])
    # Inactive watch folders must still expose a newly arrived unique paper.
    for layer in layers if check_sources else []:
        if not layer["active"]:
            scan = scan_addition(profile, workspace, layer)
            if scan.get("current_documents") and (scan.get("changes") or {}).get("has_changes"):
                incomplete.append(layer["profile"] + "/source-update")
    return {"has_additions": bool(results or incomplete), "ready": not incomplete and not errors
            and all(row["ready"] for row in results), "profiles": results,
            "incomplete_profiles": sorted(set(incomplete)), "errors": errors, "warnings": warnings,
            "source_changes_checked": check_sources, "state_root": str(state_root(workspace))}


def compose_scan(profile: str, workspace: Path, base: dict, *, scans: list[dict] | None = None) -> dict:
    if scans is None:
        scans = [scan_addition(profile, workspace, layer) for layer in registered_additions(profile, workspace)]
    changes = {key: list((base.get("changes") or {}).get(key, []))
               for key in ("added", "removed", "renamed", "modified", "unchanged", "exact_duplicate_groups")}
    documents = list(base.get("current_documents", []))
    for scan in scans:
        prefix = scan["profile"] + "/"
        for key in ("added", "removed", "modified", "unchanged"):
            changes[key].extend(prefix + name for name in (scan.get("changes") or {}).get(key, []))
        changes["renamed"].extend({**row, "from": prefix + row["from"], "to": prefix + row["to"]}
                                  for row in (scan.get("changes") or {}).get("renamed", []))
        changes["exact_duplicate_groups"].extend(
            [prefix + name for name in group]
            for group in (scan.get("changes") or {}).get("exact_duplicate_groups", [])
        )
        documents.extend({**row, "relative_path": prefix + row["relative_path"]} for row in scan["current_documents"])
    changes["has_changes"] = any(changes[k] for k in ("added", "removed", "renamed", "modified"))
    return {**base, "changes": changes, "current_documents": documents, "added_source_folders": scans,
            "base_source_available": base["source_available"],
            "source_available": base["source_available"] or any(row["source_available"] for row in scans),
            "source_papers_reverified": False,
            "source_verification_scope": {
                "base": "live-file-hashes" if base["source_available"] else "reviewed-snapshot-or-unavailable",
                "added_folders": [{"profile": row["profile"], "live_file_hashes_checked": row["source_available"],
                                   "files_checked": len(row["current_documents"]) + len(row["duplicate_sources"])}
                                  for row in scans],
            },
            "notice": "Reviewed base and added folders have separate provenance; unavailable baseline PDFs are not deletions."}


def compose_inventory(profile: str, workspace: Path, base: dict, *, cached: bool = False) -> dict:
    from .library import list_papers
    from .profiles import state_root, validate_profile

    papers = [{**row, "profile": profile, "source_layer": "reviewed-base"} for row in base["papers"]]
    duplicates, scans = [], []
    for layer in registered_additions(profile, workspace):
        scan = None if cached else scan_addition(profile, workspace, layer)
        if scan:
            scans.append(scan)
        duplicates.extend(scan["duplicate_sources"] if scan else layer.get("duplicate_sources", []))
        directory = state_root(workspace) / "profiles" / layer["profile"]
        if directory.is_dir():
            child = list_papers(layer["profile"], workspace, cached=cached,
                                _include_additions=False, _source_scan=scan)
            papers.extend({**row, "profile": layer["profile"], "source_layer": "added-papers"} for row in child["papers"])
        elif scan:
            papers.extend({"source": row["relative_path"], "source_sha256": row["sha256"],
                           "profile": layer["profile"], "source_layer": "added-papers",
                           "status": "not-distilled", "file_status": "new",
                           "reviewed_sections": 0, "review_records": 0}
                          for row in scan["current_documents"])
    validation = validate_profile(profile, workspace, check_sources=not cached)
    return {**base, "papers": papers, "status_counts": dict(Counter(r["status"] for r in papers)),
            "generation_ready": validation["generation_ready"], "duplicate_added_sources": duplicates,
            "scan": compose_scan(profile, workspace, base["scan"], scans=scans) if not cached else None,
            "source_changes_checked": not cached,
            "evidence_mode": "reviewed-base-and-additions"}


def compose_review_plan(profile: str, workspace: Path, base: dict, module: str | None,
                        language: str | None, include_complete: bool) -> dict:
    from .library import review_plan
    from .profiles import state_root

    tasks = [{**row, "profile": profile} for row in base["tasks"]]
    syntheses = [{**row, "profile": profile} for row in base["profiles_to_synthesize"]]
    updates = []
    for layer in registered_additions(profile, workspace):
        scan = scan_addition(profile, workspace, layer)
        if (scan.get("changes") or {}).get("has_changes"):
            updates.append({"profile": layer["profile"], "source": layer["source"],
                            "changes": scan["changes"], "action": "distill-added-source-update"})
        if not layer["active"] or not (state_root(workspace) / "profiles" / layer["profile"]).is_dir():
            continue
        child = review_plan(layer["profile"], workspace, module, language, include_complete, _include_additions=False)
        tasks.extend({**row, "profile": layer["profile"]} for row in child["tasks"])
        syntheses.extend({**row, "profile": layer["profile"]} for row in child["profiles_to_synthesize"])
    return {**base, "tasks": tasks, "task_count": len(tasks), "profiles_to_synthesize": syntheses,
            "source_updates": updates}


def compose_brief(profile: str, workspace: Path, brief: dict, *, explicit_registry: bool = False) -> dict:
    from .profiles import bilingual_blend, state_root

    additions = [row for row in registered_additions(profile, workspace) if row["active"]]
    if not additions:
        return brief
    language = brief["target_language"]
    other = "zh" if language == "en" else "en"
    module = brief["module"] if brief["module"] != "section" else "methodology"
    counts = dict(brief["source_counts"])
    guides = []
    for layer in additions:
        directory = state_root(workspace) / "profiles" / layer["profile"]
        quality = _read(directory / "quality.json")
        local = {lang: quality["module_samples"].get(lang, {}).get(module, 0) for lang in (language, other)}
        if not any(local.values()):
            continue
        for lang in counts:
            counts[lang] += local[lang]
        guides.append({"profile": layer["profile"], "source_counts": local,
                       "target_module": str(directory / language / "modules" / f"{module}.md"),
                       "secondary_module": str(directory / other / "modules" / f"{module}.md"),
                       "target_integrated": str(directory / language / "integrated.md"),
                       "cross_lingual": str(directory / "bilingual" / "cross-lingual.md"),
                       "conflicts": str(directory / "bilingual" / "conflicts.md")})
    terminology = brief["terminology"]
    missing = list(brief["missing_context_fields"])
    registry_sources, global_checks = [], []
    if not explicit_registry:
        from .terminology import load_registry, terminology_guidance

        entries = {}
        for name in [profile, *[row["profile"] for row in additions]]:
            path = state_root(workspace) / "profiles" / name / "terminology.json"
            if not path.is_file():
                continue
            registry = load_registry(path)
            for check in registry.get("global_checks", []):
                if check not in global_checks:
                    global_checks.append(check)
            registry_sources.append({"profile": name, "path": str(path), "status": registry.get("status")})
            for entry in registry["entries"]:
                identifier = entry["id"]
                if identifier in entries and entries[identifier]["definition"] != entry["definition"]:
                    identifier = name + ":" + identifier
                if identifier not in entries:
                    entries[identifier] = {**entry, "id": identifier}
                else:
                    entries[identifier] = {**entries[identifier],
                                           "sources": sorted(set(entries[identifier]["sources"]) | set(entry["sources"])),
                                           "aliases": sorted(set(entries[identifier]["aliases"]) | set(entry["aliases"]))}
        if entries:
            terminology = terminology_guidance(brief["context"], {
                "entries": list(entries.values()), "status": "source-scoped-profile-layers",
                "evidence_partition": "reviewed-base-and-additions",
                "global_checks": global_checks,
            })
            key = "research.problem.full_name_or_variant"
            missing = [value for value in missing if value != key]
            if terminology["clarification_required"]:
                missing.append(key)
    return {**brief, "base_source_counts": brief["source_counts"], "source_counts": counts,
            "additional_module_profiles": guides, "profile_evidence_mode": "reviewed-base-and-additions",
            "terminology": terminology, "terminology_sources": registry_sources,
            "missing_context_fields": missing,
            "bilingual_blend": {"target_language": language, "secondary_language": other,
                                **bilingual_blend(counts[language], counts[other])},
            "instructions": [*brief["instructions"],
                "Apply the matching reviewed added-paper modules alongside the base module. Keep source scopes and confidence explicit internally; a narrow addition does not overturn a broadly supported base pattern automatically.",
                "All corpus material supplies writing guidance, not new-study methods, numbers or citations. Use the combined language-evidence weights and preserve the verified current research facts."]}
