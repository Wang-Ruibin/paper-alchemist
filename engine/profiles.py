"""Corpus preparation, deterministic seed profiles, and bilingual integration."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .constants import MODULE_TITLES, MODULES, PROFILE_HEADINGS
from .extractors import (
    PDF_TEXT_ORDERS,
    discover_papers,
    extract_text,
    file_sha256,
    load_pdf_order_map,
    normalize_pdf_order_review,
    text_encoding_warnings,
)
from .language import detect_language, language_scores
from .library import compare_documents
from .section_maps import load_section_maps, mapped_sections
from .sections import academic_heading_count, prose_density, segment_sections, text_statistics


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def profile_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("_", "-")
    slug = re.sub(r"[^\w-]+", "-", normalized, flags=re.UNICODE).replace("_", "-")
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("Profile name must contain at least one letter or digit")
    return slug[:100].rstrip("-")


def state_root(workspace: Path) -> Path:
    return workspace.resolve() / ".paper-alchemist"


def build_profile(
    source: Path,
    profile: str,
    workspace: Path,
    language: str | None = None,
    update: bool = False,
    min_characters: int | None = None,
    ocr_mode: str | None = None,
    include_sources: set[str] | None = None,
    section_map: Path | None = None,
    rebind_source: bool = False,
    pdf_order_map: Path | None = None,
) -> dict[str, Any]:
    slug = profile_slug(profile)
    root = state_root(workspace)
    profile_dir = root / "profiles" / slug
    cache_dir = root / "cache" / slug
    if profile_dir.exists() and not update:
        raise FileExistsError(
            f"Profile already exists: {profile_dir}. Pass --update to refresh it."
        )
    profile_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    previous_manifest = _read_json(profile_dir / "source-manifest.json", default={})
    if previous_manifest.get("source_kind") == "bundled-reviewed-snapshot":
        raise ValueError("The included corpus is an immutable reviewed base. Use --extend for new papers, or choose a separate custom profile for a source-backed rebuild.")
    previous_quality = _read_json(profile_dir / "quality.json", default={})
    if (update and previous_manifest.get("source")
            and Path(previous_manifest["source"]).resolve() != source.resolve() and not rebind_source):
        raise ValueError("This profile tracks another source folder. Use its registered folder for additions, or explicitly --rebind-source after reviewing relocation; rebinding does not merge folders.")
    portable_marker = profile_dir / "portable-profile.json"
    if portable_marker.is_file():
        from .portable import load_snapshot

        _, snapshot_errors = load_snapshot(profile_dir)
        if snapshot_errors:
            raise ValueError("; ".join(snapshot_errors))
        if not source.is_dir():
            raise FileNotFoundError("Supply the reference-paper folder before updating an imported profile")
    language = language or previous_manifest.get("language_mode", "auto")
    ocr_mode = ocr_mode or previous_manifest.get("ocr_mode", "auto")
    min_characters = min_characters if min_characters is not None else previous_manifest.get("min_characters", 800)
    if ocr_mode not in {"auto", "never", "always"} or language not in {"auto", "en", "zh"}:
        raise ValueError("Invalid extraction language or OCR policy")
    if min_characters < 0:
        raise ValueError("min_characters must be nonnegative")
    if update and include_sources is None and previous_manifest.get("selected_sources") is not None:
        include_sources = set(previous_manifest["selected_sources"])
    previous_by_path = {
        item.get("path"): item
        for item in previous_manifest.get("documents", [])
        if isinstance(item, dict)
    }
    previous_by_hash: dict[str, list[dict]] = defaultdict(list)
    for item in previous_manifest.get("documents", []):
        if item.get("included"):
            previous_by_hash[item["sha256"]].append(item)

    documents: list[dict[str, Any]] = []
    module_samples: dict[str, dict[str, list[dict[str, Any]]]] = {
        "en": defaultdict(list),
        "zh": defaultdict(list),
    }
    discovered = discover_papers(source.resolve())
    # Keep an existing canonical paper ahead of newly added identical copies.
    discovered.sort(key=lambda path: (not bool(previous_by_path.get(str(path.resolve()), {}).get("included")), path.as_posix().casefold()))
    stored_map = cache_dir / "section-maps.json"
    reviewed_maps = load_section_maps(stored_map if stored_map.is_file() else None)
    supplied_maps = load_section_maps(section_map) if section_map else {}
    reviewed_maps.update(supplied_maps)
    invalidated_maps = []
    rebound_maps = []
    available = {path.relative_to(source.resolve()).as_posix() for path in discovered}
    digests = {path: file_sha256(path) for path in discovered
               if include_sources is None or path.relative_to(source.resolve()).as_posix() in include_sources}
    pdf_reviews = load_pdf_order_map(pdf_order_map)
    selected_paths = {path.relative_to(source.resolve()).as_posix(): path for path in digests}
    canonical_by_hash = {}
    for path, digest in digests.items():
        canonical_by_hash.setdefault(digest, path.relative_to(source.resolve()).as_posix())
    for name, review in pdf_reviews.items():
        if name not in selected_paths:
            raise ValueError("PDF text-order choices must stay inside the supplied and selected corpus")
        digest = digests[selected_paths[name]]
        if review["source_sha256"] != digest:
            raise ValueError(f"PDF text-order source hash differs from its reviewed bytes: {name}")
        if canonical_by_hash[digest] != name:
            raise ValueError(f"Set the PDF text order for its canonical duplicate source: {canonical_by_hash[digest]}")
    if not set(reviewed_maps) <= available:
        if set(supplied_maps) - available:
            raise ValueError("Section-map sources must exist in the supplied corpus")
        for name in sorted(set(reviewed_maps) - available):
            replacements = [path.relative_to(source.resolve()).as_posix() for path, digest in digests.items()
                            if digest == reviewed_maps[name].get("source_sha256")]
            if len(replacements) == 1 and replacements[0] not in reviewed_maps:
                reviewed_maps[replacements[0]] = {**reviewed_maps[name], "source": replacements[0]}
                rebound_maps.append({"from": name, "to": replacements[0], "reason": "identical source content renamed"})
            else:
                invalidated_maps.append({"source": name, "reason": "source removed"})
            del reviewed_maps[name]
    if include_sources is not None and not set(reviewed_maps) <= include_sources:
        raise ValueError("Section maps must stay inside the selected evaluation partition")
    if include_sources is not None and (not include_sources or not include_sources <= available):
        raise ValueError("Selected sources must be a nonempty subset of the supplied corpus")
    if portable_marker.is_file():
        # Subsequent validation uses actual re-extracted sections. Never continue
        # accepting a frozen index while its files are being updated.
        (cache_dir / "portable-origin.json").write_bytes(portable_marker.read_bytes())
        portable_marker.unlink()
    seen_hashes: dict[str, dict] = {}
    for path in discovered:
        if include_sources is not None and path.relative_to(source.resolve()).as_posix() not in include_sources:
            continue
        digest = digests[path]
        relative = path.relative_to(source.resolve()).as_posix()
        if digest in seen_hashes:
            canonical = seen_hashes[digest]
            documents.append({**canonical, "id": f"{_safe_stem(path.stem)}-{digest[:10]}",
                              "path": str(path.resolve()), "relative_path": relative,
                              "included": False, "reason": "exact-duplicate", "duplicate_of": canonical["relative_path"],
                              "cache_status": "duplicate-not-extracted"})
            continue
        previous = previous_by_path.get(str(path.resolve()))
        if previous is None and len(previous_by_hash.get(digest, [])) == 1:
            previous = previous_by_hash[digest][0]
        pdf_text_order, pdf_review, order_invalidated = "auto", None, False
        if path.suffix.casefold() == ".pdf":
            if relative in pdf_reviews:
                pdf_review = pdf_reviews[relative]
                pdf_text_order = pdf_review["pdf_text_order"]
            elif previous and previous.get("sha256") == digest:
                pdf_text_order = previous.get("pdf_text_order", "auto")
                if pdf_text_order not in PDF_TEXT_ORDERS:
                    raise ValueError("Stored PDF text order must be auto or raw")
                if previous.get("pdf_text_order_review"):
                    pdf_review = normalize_pdf_order_review(previous["pdf_text_order_review"])
                    if pdf_review["source_sha256"] != digest or pdf_review["pdf_text_order"] != pdf_text_order:
                        raise ValueError("Stored PDF text-order review differs from its source hash or choice")
                elif pdf_text_order != "auto":
                    raise ValueError("A stored raw PDF order needs a source-bound review")
            elif previous and previous.get("pdf_text_order", "auto") != "auto":
                order_invalidated = True
            if pdf_review:
                pdf_review = {**pdf_review, "source": relative}
        doc_id = previous["id"] if previous and previous.get("sha256") == digest else f"{_safe_stem(path.stem)}-{digest[:10]}"
        document_cache = cache_dir / "documents" / doc_id
        cached_meta = _read_json(document_cache / "meta.json", default={})
        cache_matches = bool(
            cached_meta.get("sha256") == digest and (document_cache / "full.txt").exists()
        )
        if path.suffix.casefold() == ".pdf":
            cache_matches = bool(
                cache_matches
                and cached_meta.get("pdf_extraction_version") == 4
                and cached_meta.get("ocr_mode") == ocr_mode
                and cached_meta.get("pdf_text_order", "auto") == pdf_text_order
            )
        manifest_matches = bool(previous and previous.get("sha256") == digest)
        # A matching private cache is sufficient for --update. This also lets an
        # interrupted first run resume when it stopped before writing the manifest.
        can_reuse = bool(update and cache_matches and (manifest_matches or not previous))
        warnings: list[str] = []
        if order_invalidated:
            warnings.append("The reviewed PDF text order was reset to auto because source bytes changed; inspect the new reading order")
        if can_reuse:
            text = (document_cache / "full.txt").read_text(encoding="utf-8")
            backend = cached_meta.get("backend", "cache")
            ocr_used = bool(cached_meta.get("ocr_used", False))
            warnings.extend(cached_meta.get("warnings", []))
            status = "reused"
        else:
            extraction_options = {"ocr_mode": ocr_mode}
            if pdf_text_order != "auto":
                extraction_options["pdf_text_order"] = pdf_text_order
            extraction = extract_text(path, **extraction_options)
            text = extraction.text.replace("\x00", "").strip()
            backend = extraction.backend
            ocr_used = extraction.ocr_used
            warnings.extend(extraction.warnings)
            status = "extracted"

        if path.suffix.casefold() == ".pdf":
            # Diagnose old matching caches too; unchanged source text and valid
            # observations need no re-extraction or timestamp churn for a warning.
            warnings = list(dict.fromkeys(warnings + text_encoding_warnings(text)))

        doc_language = language if language in {"en", "zh"} else detect_language(text)
        if relative in reviewed_maps and relative not in supplied_maps:
            row = reviewed_maps[relative]
            if row.get("source_sha256") != digest or row.get("text_sha256") != sha256(text.encode()).hexdigest():
                invalidated_maps.append({"source": relative, "reason": "source or extracted text changed"})
                del reviewed_maps[relative]
                warnings.append("Prior reviewed section map no longer matches; inspect recovered section boundaries before semantic review")
        sections = (
            mapped_sections(text, digest, reviewed_maps[relative])
            if relative in reviewed_maps else segment_sections(text)
        )
        heading_count = academic_heading_count(text)
        density = prose_density(text)
        document_statistics = text_statistics(text, doc_language)
        visual_mentions = int(document_statistics["figure_mentions"]) + int(
            document_statistics["table_mentions"]
        )
        content_mode = (
            "figure-or-table-heavy"
            if path.suffix.casefold() == ".pdf"
            and (density < 0.18 or (len(sections) < 2 and visual_mentions >= 3))
            else "prose"
        )
        if (
            len(text) >= min_characters
            and doc_language != "unknown"
            and content_mode == "figure-or-table-heavy"
            and len(sections) < 2
        ):
            # Visual supplements often have captions, labels, or tabular results but
            # no conventional paper headings. Route them to the only module where
            # their presentation patterns are relevant instead of treating values as
            # a complete paper narrative.
            sections = {"results-analysis": text}
        included = True
        reason = "included"
        if len(text) < min_characters:
            included, reason = False, "low-text-or-scanned"
        elif doc_language == "unknown":
            included, reason = False, "language-undetermined"
        elif len(sections) < 2 and content_mode != "figure-or-table-heavy":
            included, reason = False, "insufficient-paper-structure"

        entry = {
            "id": doc_id,
            "path": str(path.resolve()),
            "relative_path": relative,
            "sha256": digest,
            "format": path.suffix.casefold().lstrip("."),
            "backend": backend,
            "ocr_used": ocr_used,
            "content_mode": content_mode,
            "language": doc_language,
            "language_scores": language_scores(text),
            "characters": len(text),
            "recognized_modules": sorted(sections),
            "segmentation_mode": "reviewed-spans" if relative in reviewed_maps else "automatic-headings",
            "section_map_sha256": sha256(json.dumps(reviewed_maps[relative], sort_keys=True, ensure_ascii=False).encode()).hexdigest() if relative in reviewed_maps else None,
            "academic_heading_count": heading_count,
            "prose_density": density,
            "included": included,
            "reason": reason,
            "cache_status": status,
            "warnings": warnings,
        }
        if path.suffix.casefold() == ".pdf":
            entry.update(pdf_text_order=pdf_text_order, pdf_text_order_review=pdf_review)
        documents.append(entry)
        seen_hashes[digest] = entry

        document_cache.mkdir(parents=True, exist_ok=True)
        if not can_reuse:
            (document_cache / "full.txt").write_text(text, encoding="utf-8")
            _write_json(
                document_cache / "meta.json",
                {"sha256": digest, "backend": backend, "warnings": warnings,
                 "ocr_mode": ocr_mode, "ocr_used": ocr_used,
                 "pdf_text_order": pdf_text_order if path.suffix.casefold() == ".pdf" else None,
                 "pdf_extraction_version": 4 if path.suffix.casefold() == ".pdf" else None},
            )
        if not included:
            continue
        sections_dir = document_cache / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        for old_section in sections_dir.glob("*.txt"):
            if old_section.stem not in sections:
                old_section.unlink()
        for module, section_text in sections.items():
            section_language = (
                language if language in {"en", "zh"} else detect_language(section_text)
            )
            if section_language == "unknown":
                section_language = doc_language
            section_path = sections_dir / f"{module}.txt"
            if not section_path.is_file() or section_path.read_text(encoding="utf-8") != section_text:
                section_path.write_text(section_text, encoding="utf-8")
            module_samples[section_language][module].append(
                {
                    "document_id": doc_id,
                    "source": relative,
                    "source_sha256": digest,
                    "cache_path": str(section_path.resolve()),
                    "text": section_text,
                    "content_mode": content_mode,
                    "statistics": text_statistics(section_text, section_language),
                }
            )

    manifest = {
        "schema_version": 1,
        "profile": slug,
        "source": str(source.resolve()),
        "created_at": previous_manifest.get("created_at", utc_now()),
        "updated_at": utc_now(),
        "language_mode": language,
        "ocr_mode": ocr_mode,
        "min_characters": min_characters,
        "selected_sources": sorted(include_sources) if include_sources is not None else None,
        "documents": documents,
    }
    _write_json(profile_dir / "source-manifest.json", manifest)
    if reviewed_maps or stored_map.exists() or section_map:
        _write_json(stored_map, {"schema_version": 1, "documents": list(reviewed_maps.values())})

    semantic_refresh: list[str] = []
    module_fingerprints = _module_fingerprints(module_samples)
    for lang in ("en", "zh"):
        modules_dir = profile_dir / lang / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        for module in MODULES:
            samples = module_samples[lang].get(module, [])
            seed = _render_module_seed(slug, lang, module, samples)
            seed_path = modules_dir / f"{module}.seed.md"
            seed_path.write_text(seed, encoding="utf-8")
            profile_path = modules_dir / f"{module}.md"
            previous_fingerprint = (
                previous_quality.get("module_fingerprints", {}).get(lang, {}).get(module)
            )
            fingerprint_changed = bool(
                update and previous_fingerprint != module_fingerprints[lang][module]
            )
            other = "zh" if lang == "en" else "en"
            if update:
                # Guidance about missing evidence must change when that language appears
                # or disappears, even if this language's source sections are unchanged.
                previous_other_available = bool(
                    previous_quality.get("module_samples", {}).get(other, {}).get(module, 0)
                )
                fingerprint_changed = fingerprint_changed or (
                    previous_other_available != bool(module_samples[other].get(module, []))
                )
            if not samples and update:
                # Zero-source assistance depends on the available language's rhetoric.
                fingerprint_changed = fingerprint_changed or (
                    previous_quality.get("module_fingerprints", {}).get(other, {}).get(module)
                    != module_fingerprints[other][module]
                )
            if not profile_path.exists():
                profile_path.write_text(seed, encoding="utf-8")
            else:
                content = profile_path.read_text(encoding="utf-8", errors="replace")
                status = _frontmatter(content).get("synthesis_status", "pending")
                if status == "pending":
                    profile_path.write_text(seed, encoding="utf-8")
                elif fingerprint_changed:
                    metadata = _frontmatter(content)
                    fresh_metadata = _frontmatter(seed)
                    metadata.update({key: fresh_metadata[key] for key in ("source_count", "visual_source_count", "confidence")})
                    content = "---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip() + "\n---" + content.split("---", 2)[2]
                    profile_path.write_text(
                        _set_synthesis_status(content, "stale"), encoding="utf-8"
                    )
                    semantic_refresh.append(f"{lang}/{module}")
                elif status == "stale":
                    semantic_refresh.append(f"{lang}/{module}")
            _write_packets(cache_dir, lang, module, samples)
            _write_observations(cache_dir, lang, module, samples)

    quality = _quality_report(
        slug,
        documents,
        module_samples,
        semantic_refresh,
        module_fingerprints,
    )
    incomplete_profiles = _incomplete_module_profiles(profile_dir)
    observation_pending = _incomplete_observations(profile_dir, quality["module_samples"])
    quality["incomplete_observation_count"] = len(observation_pending)
    if incomplete_profiles or observation_pending:
        _invalidate_integration(profile_dir)
    else:
        quality["semantic_synthesis_complete"] = True
        integration_files = (
            "en/integrated.md",
            "zh/integrated.md",
            "bilingual/cross-lingual.md",
            "bilingual/conflicts.md",
        )
        if all((profile_dir / relative).is_file() for relative in integration_files):
            quality["integration_status"] = "complete"
            if previous_quality.get("integrated_at"):
                quality["integrated_at"] = previous_quality["integrated_at"]
    _write_json(profile_dir / "quality.json", quality)
    changes = compare_documents(previous_manifest.get("documents", []), documents)
    event = {"updated_at": manifest["updated_at"], "changes": changes,
             "semantic_refresh_required": semantic_refresh, "invalidated_section_maps": invalidated_maps,
             "rebound_section_maps": rebound_maps}
    with (cache_dir / "update-history.jsonl").open("a", encoding="utf-8") as history:
        history.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {
        "profile": slug,
        "profile_dir": str(profile_dir),
        "cache_dir": str(cache_dir),
        "documents_found": len(documents),
        "documents_included": sum(1 for item in documents if item["included"]),
        "documents_excluded": sum(1 for item in documents if not item["included"]),
        "module_samples": quality["module_samples"],
        "semantic_refresh_required": semantic_refresh,
        "changes": changes,
        "invalidated_section_maps": invalidated_maps,
        "rebound_section_maps": rebound_maps,
        "pending_observation_count": len(observation_pending),
    }


def integrate_profile(profile: str, workspace: Path) -> dict[str, Any]:
    slug = profile_slug(profile)
    profile_dir = state_root(workspace) / "profiles" / slug
    if not profile_dir.exists():
        raise FileNotFoundError(f"Profile does not exist: {profile_dir}")
    if (profile_dir / "portable-profile.json").is_file():
        raise ValueError("The imported profile is already integrated. Update from its source papers before changing its synthesis.")
    incomplete = _incomplete_module_profiles(profile_dir)
    if incomplete:
        joined = ", ".join(incomplete)
        raise ValueError(
            "Semantic synthesis is incomplete for: "
            f"{joined}. Complete those module profiles before integration."
        )
    observations = _incomplete_observations(profile_dir)
    if observations:
        raise ValueError(
            f"Semantic observations are incomplete ({len(observations)} records): "
            + ", ".join(observations[:8])
        )
    quality = _read_json(profile_dir / "quality.json", default={})
    for lang in ("en", "zh"):
        integrated = _render_integrated(slug, lang, profile_dir, quality)
        target = profile_dir / lang / "integrated.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(integrated, encoding="utf-8")
    bilingual = profile_dir / "bilingual"
    bilingual.mkdir(parents=True, exist_ok=True)
    cross = _render_cross_lingual(slug, profile_dir, quality)
    conflicts = _render_conflicts(slug, quality)
    (bilingual / "cross-lingual.md").write_text(cross, encoding="utf-8")
    (bilingual / "conflicts.md").write_text(conflicts, encoding="utf-8")
    quality["semantic_refresh_required"] = []
    quality["incomplete_observation_count"] = 0
    quality["semantic_synthesis_complete"] = True
    quality["integration_status"] = "complete"
    quality["integrated_at"] = utc_now()
    _write_json(profile_dir / "quality.json", quality)
    return {
        "profile": slug,
        "integrated": [
            str(profile_dir / "en" / "integrated.md"),
            str(profile_dir / "zh" / "integrated.md"),
            str(bilingual / "cross-lingual.md"),
            str(bilingual / "conflicts.md"),
        ],
    }


def validate_profile(profile: str, workspace: Path, *, include_additions: bool = True,
                     check_sources: bool = True) -> dict[str, Any]:
    from .portable import load_snapshot

    slug = profile_slug(profile)
    profile_dir = state_root(workspace) / "profiles" / slug
    errors: list[str] = []
    warnings: list[str] = []
    pending: list[str] = []
    snapshot, snapshot_errors = load_snapshot(profile_dir)
    errors.extend(snapshot_errors)
    if snapshot is not None:
        warnings.append("Reviewed exported snapshot: source-paper bytes and extraction prose were not reverified here; check the source folder separately.")
    quality = _read_json(profile_dir / "quality.json", {})
    sample_counts = quality.get("module_samples", {})
    for required in ("source-manifest.json", "quality.json"):
        if not (profile_dir / required).is_file():
            errors.append(f"missing {required}")
    for lang in ("en", "zh"):
        for module in MODULES:
            path = profile_dir / lang / "modules" / f"{module}.md"
            if not path.is_file():
                errors.append(f"missing {lang}/modules/{module}.md")
                pending.append(f"{lang}/{module}")
                continue
            content = path.read_text(encoding="utf-8")
            try:
                metadata = _frontmatter(content)
            except ValueError as exc:
                errors.append(f"{path}: {exc}")
                pending.append(f"{lang}/{module}")
                continue
            for field in ("profile", "language", "module", "source_count", "confidence"):
                if field not in metadata:
                    errors.append(f"{path}: missing frontmatter field {field}")
            if metadata.get("source_count") != sample_counts.get(lang, {}).get(module, 0):
                errors.append(f"{path}: source count differs from current corpus evidence")
            if metadata.get("synthesis_status") != "complete":
                pending.append(f"{lang}/{module}")
                warnings.append(f"semantic synthesis incomplete: {lang}/{module}")
            for heading in PROFILE_HEADINGS:
                if f"## {heading}" not in content:
                    errors.append(f"{path}: missing section {heading}")
            if metadata.get("source_count", 0) < 3:
                warnings.append(f"low-confidence corpus: {lang}/{module}")
    integration_files = (
        "en/integrated.md",
        "zh/integrated.md",
        "bilingual/cross-lingual.md",
        "bilingual/conflicts.md",
    )
    integration_present = [
        relative for relative in integration_files if (profile_dir / relative).is_file()
    ]
    if pending and integration_present:
        warnings.append("integration artifacts are stale while semantic synthesis is incomplete")
    elif not pending:
        for relative in integration_files:
            if not (profile_dir / relative).is_file():
                errors.append(f"missing {relative}")
                continue
            try:
                metadata = _frontmatter((profile_dir / relative).read_text(encoding="utf-8"))
                if metadata.get("integration_policy_version") != 2:
                    errors.append(f"stale integration policy in {relative}; run integrate")
                if relative in {"en/integrated.md", "zh/integrated.md"}:
                    lang = relative.split("/")[0]
                    other = "zh" if lang == "en" else "en"
                    expected = {
                        module: bilingual_blend(
                            sample_counts.get(lang, {}).get(module, 0),
                            sample_counts.get(other, {}).get(module, 0),
                        )
                        for module in MODULES
                    }
                    if metadata.get("module_weights") != expected:
                        errors.append(f"language evidence weights differ in {relative}; run integrate")
            except ValueError as exc:
                errors.append(f"invalid integration metadata in {relative}: {exc}")
    observation_pending = _incomplete_observations(profile_dir, snapshot=snapshot)
    semantic_complete = not pending and not observation_pending
    integration_complete = len(integration_present) == len(integration_files)
    valid = not errors
    result = {
        "profile": slug,
        "valid": valid,
        "semantic_complete": semantic_complete,
        "integration_complete": integration_complete,
        "generation_ready": valid and semantic_complete and integration_complete,
        "incomplete_profiles": pending,
        "incomplete_observation_count": len(observation_pending),
        "incomplete_observations": observation_pending[:30],
        "errors": errors,
        "warnings": warnings,
        "evidence_mode": "exported-reviewed-snapshot" if snapshot is not None else "local-extracted-sections",
    }
    if include_additions:
        from .additions import validate_additions

        extra = validate_additions(slug, workspace, check_sources=check_sources)
        if extra["has_additions"]:
            result["base_generation_ready"] = result["generation_ready"]
            result["generation_ready"] = result["generation_ready"] and extra["ready"]
            result["semantic_complete"] = result["semantic_complete"] and extra["ready"]
            result["integration_complete"] = result["integration_complete"] and extra["ready"]
            result["valid"] = result["valid"] and not extra["errors"]
            result["incomplete_profiles"].extend(extra["incomplete_profiles"])
            result["incomplete_observation_count"] += sum(
                row["validation"]["incomplete_observation_count"] for row in extra["profiles"]
            )
            result["incomplete_observations"] = (result["incomplete_observations"] + [
                row["profile"] + ": " + str(value) for row in extra["profiles"]
                for value in row["validation"]["incomplete_observations"]
            ])[:30]
            result["errors"].extend(extra["errors"])
            result["warnings"].extend(extra["warnings"])
            result["additions"] = extra
            result["evidence_mode"] = "reviewed-base-and-additions"
    return result


def _render_module_seed(
    profile: str, language: str, module: str, samples: list[dict[str, Any]]
) -> str:
    count = len(samples)
    visual_source_count = sum(
        1 for sample in samples if sample.get("content_mode") == "figure-or-table-heavy"
    )
    confidence = "high" if count >= 8 else "medium" if count >= 3 else "low"
    statistics = [sample["statistics"] for sample in samples]
    averages = {
        key: round(mean(float(item[key]) for item in statistics), 2) if statistics else 0
        for key in (
            "paragraphs",
            "sentences",
            "average_sentence_length",
            "citations",
            "hedges",
            "first_person_markers",
            "figure_mentions",
            "table_mentions",
        )
    }
    metadata = {
        "profile": profile,
        "language": language,
        "module": module,
        "source_count": count,
        "visual_source_count": visual_source_count,
        "confidence": confidence,
        "synthesis_status": "pending",
    }
    front = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    source_list = (
        "\n".join(f"- `{item['source']}` ({item.get('content_mode', 'prose')})" for item in samples)
        or "- No qualifying samples."
    )
    body = [
        f"---\n{front}\n---",
        f"# {MODULE_TITLES[module][0]} / {MODULE_TITLES[module][1]}",
        "",
        "> Quantitative seed generated locally. The active Agent must review the private packet files, replace pending notes with corpus-level semantic findings, and set `synthesis_status: complete`. Do not copy source sentences.",
        "",
        "## Corpus evidence",
        "",
        source_list,
        "",
        "## Quantitative baseline",
        "",
        *[f"- {key.replace('_', ' ')}: {value}" for key, value in averages.items()],
    ]
    for heading in PROFILE_HEADINGS:
        body.extend(["", f"## {heading}", "", "- Pending Agent synthesis."])
    return "\n".join(body).rstrip() + "\n"


def _write_packets(
    cache_dir: Path, language: str, module: str, samples: list[dict[str, Any]], batch_size: int = 4
) -> None:
    target = cache_dir / "packets" / language / module
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("batch-*.md"):
        old.unlink()
    for start in range(0, len(samples), batch_size):
        batch = samples[start : start + batch_size]
        lines = [
            f"# Private distillation packet: {language}/{module}",
            "",
            "Summarize recurring rhetorical and organizational patterns. Never reproduce long phrases.",
        ]
        for sample in batch:
            lines.extend(
                [
                    "",
                    f"## Source {sample['document_id']}",
                    "",
                    f"Path label: `{sample['source']}`",
                    f"Content mode: `{sample.get('content_mode', 'prose')}`",
                    "",
                    sample["text"][:16000],
                ]
            )
        (target / f"batch-{start // batch_size + 1:03d}.md").write_text(
            "\n".join(lines).rstrip() + "\n", encoding="utf-8"
        )


def _retain_observation_history(
    cache_dir: Path, language: str, module: str, source: str, content: bytes,
    overwrite: bool = True,
) -> Path:
    history = cache_dir / "observation-history" / language / module
    history.mkdir(parents=True, exist_ok=True)
    path = history / (sha256(source.encode()).hexdigest()[:20] + ".md")
    if overwrite or not path.exists():
        path.write_bytes(content)
    return path


def _write_observations(
    cache_dir: Path,
    language: str,
    module: str,
    samples: list[dict[str, Any]],
) -> None:
    target = cache_dir / "observations" / language / module
    target.mkdir(parents=True, exist_ok=True)
    expected = {f"{sample['document_id']}.md" for sample in samples}
    for old in target.glob("*.md"):
        if old.name not in expected:
            content = old.read_text(encoding="utf-8")
            metadata = _frontmatter(content)
            if metadata.get("observation_status") in {"complete", "stale"}:
                _retain_observation_history(
                    cache_dir, language, module, str(metadata.get("source", old.stem)),
                    old.read_bytes(), overwrite=metadata.get("observation_status") == "complete",
                )
                old.unlink()
            else:
                old.unlink()
    for sample in samples:
        path = target / f"{sample['document_id']}.md"
        evidence_hash = sha256(sample["text"].encode()).hexdigest()
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            try:
                previous = _frontmatter(existing)
            except ValueError:
                previous = {}
            if previous.get("section_sha256") == evidence_hash and previous.get("source_sha256") == sample["source_sha256"]:
                if previous.get("source") != sample["source"]:
                    previous["source"] = sample["source"]
                    path.write_text("---\n" + yaml.safe_dump(previous, sort_keys=False, allow_unicode=True).strip() + "\n---" + existing.split("---", 2)[2], encoding="utf-8")
                continue
            if previous.get("observation_status") in {"complete", "stale"}:
                _retain_observation_history(
                    cache_dir, language, module, str(previous.get("source", sample["source"])),
                    path.read_bytes(), overwrite=previous.get("observation_status") == "complete",
                )
                previous.update(observation_status="stale", source_sha256=sample["source_sha256"], section_sha256=evidence_hash)
                body = existing.split("---", 2)[-1]
                path.write_text("---\n" + yaml.safe_dump(previous, sort_keys=False).strip() + "\n---" + body, encoding="utf-8")
                continue
        metadata = {
            "document_id": sample["document_id"],
            "source": sample["source"],
            "language": language,
            "module": module,
            "content_mode": sample.get("content_mode", "prose"),
            "observation_status": "pending",
            "source_sha256": sample["source_sha256"],
            "section_sha256": evidence_hash,
        }
        frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
        statistics = sample["statistics"]
        lines = [
            f"---\n{frontmatter}\n---",
            f"# Observation: {language}/{module}",
            "",
            "> Private working record. Summarize this source at the functional level; do not copy distinctive phrases.",
            "",
            "## Quantitative evidence",
            "",
            *[f"- {key.replace('_', ' ')}: {value}" for key, value in statistics.items()],
            "",
            "## Rhetorical moves and order",
            "",
            "- Pending Agent observation.",
            "",
            "## Language and stance",
            "",
            "- Pending Agent observation.",
            "",
            "## Evidence introduction",
            "",
            "- Pending Agent observation.",
            "",
            "## Transferable pattern",
            "",
            "- Pending Agent observation.",
            "",
            "## Risks and exceptions",
            "",
            "- Pending Agent observation.",
        ]
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _quality_report(
    profile: str,
    documents: list[dict[str, Any]],
    module_samples: dict[str, dict[str, list[dict[str, Any]]]],
    semantic_refresh: list[str],
    module_fingerprints: dict[str, dict[str, str]],
) -> dict[str, Any]:
    sample_counts = {
        lang: {module: len(module_samples[lang].get(module, [])) for module in MODULES}
        for lang in ("en", "zh")
    }
    module_confidence = {
        lang: {
            module: (
                "high"
                if sample_counts[lang][module] >= 8
                else "medium"
                if sample_counts[lang][module] >= 3
                else "low"
            )
            for module in MODULES
        }
        for lang in ("en", "zh")
    }
    included_documents = [item for item in documents if item["included"]]
    excluded_documents = [item for item in documents if not item["included"]]
    exclusions = Counter(item["reason"] for item in excluded_documents)
    formats = Counter(item["format"] for item in documents)
    languages = Counter(item["language"] for item in included_documents)
    content_modes = Counter(item["content_mode"] for item in included_documents)
    metrics: dict[str, dict[str, dict[str, float]]] = {"en": {}, "zh": {}}
    for lang in ("en", "zh"):
        for module in MODULES:
            stats = [item["statistics"] for item in module_samples[lang].get(module, [])]
            metrics[lang][module] = {
                key: round(mean(float(value[key]) for value in stats), 2) if stats else 0.0
                for key in (
                    "average_sentence_length",
                    "citations",
                    "hedges",
                    "first_person_markers",
                    "figure_mentions",
                    "table_mentions",
                )
            }
    return {
        "schema_version": 1,
        "profile": profile,
        "updated_at": utc_now(),
        "documents_found": len(documents),
        "documents_included": sum(1 for item in documents if item["included"]),
        "documents_excluded": sum(1 for item in documents if not item["included"]),
        "source_coverage": {
            "included_ratio": round(len(included_documents) / len(documents), 4)
            if documents
            else 0.0,
            "formats": dict(sorted(formats.items())),
            "included_languages": dict(sorted(languages.items())),
            "included_content_modes": dict(sorted(content_modes.items())),
            "ocr_documents": sum(1 for item in included_documents if item["ocr_used"]),
            "exclusions_by_reason": dict(sorted(exclusions.items())),
        },
        "anomalies": [
            {
                "source": item["relative_path"],
                "reason": item["reason"],
                "warnings": item["warnings"],
            }
            for item in documents
            if not item["included"] or item["warnings"]
        ],
        "module_samples": sample_counts,
        "module_confidence": module_confidence,
        "metrics": metrics,
        "module_fingerprints": module_fingerprints,
        "semantic_refresh_required": semantic_refresh,
        "semantic_synthesis_complete": False,
        "integration_status": "pending",
        "bilingual_status": (
            "complete"
            if any(sample_counts["en"].values()) and any(sample_counts["zh"].values())
            else "degraded-single-language"
        ),
    }


def _module_fingerprints(
    module_samples: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, dict[str, str]]:
    fingerprints: dict[str, dict[str, str]] = {"en": {}, "zh": {}}
    for lang in ("en", "zh"):
        for module in MODULES:
            evidence = []
            for sample in module_samples[lang].get(module, []):
                content_hash = sha256(sample["text"].encode("utf-8")).hexdigest()
                content_mode = sample.get("content_mode", "prose")
                evidence.append(f"{sample['source']}:{content_mode}:{content_hash}")
            payload = "\n".join(sorted(evidence)).encode("utf-8")
            fingerprints[lang][module] = sha256(payload).hexdigest()
    return fingerprints


def _incomplete_module_profiles(profile_dir: Path) -> list[str]:
    incomplete: list[str] = []
    for lang in ("en", "zh"):
        for module in MODULES:
            path = profile_dir / lang / "modules" / f"{module}.md"
            if not path.is_file():
                incomplete.append(f"{lang}/{module} (missing)")
                continue
            try:
                status = _frontmatter(path.read_text(encoding="utf-8")).get("synthesis_status")
            except ValueError:
                status = None
            if status != "complete":
                incomplete.append(f"{lang}/{module} ({status or 'invalid'})")
    return incomplete


def _incomplete_observations(profile_dir: Path, counts: dict | None = None,
                             snapshot: dict | None = None) -> list[str]:
    """Module status flags cannot substitute for source-level semantic review."""
    manifest = _read_json(profile_dir / "source-manifest.json", {})
    quality = _read_json(profile_dir / "quality.json", {})
    counts = counts if counts is not None else quality.get("module_samples", {})
    included = {item["id"]: item for item in manifest.get("documents", []) if item.get("included")}
    observations_root = profile_dir.parent.parent / "cache" / profile_dir.name / "observations"
    if snapshot is None and (profile_dir / "portable-profile.json").is_file():
        from .portable import load_snapshot

        snapshot, _ = load_snapshot(profile_dir)
    frozen_sections = {(row["language"], row["module"], row["document_id"]): row["section_sha256"]
                       for row in snapshot["observations"]} if snapshot else {}
    incomplete = []
    for lang in ("en", "zh"):
        for module in MODULES:
            expected = counts.get(lang, {}).get(module, 0)
            paths = list((observations_root / lang / module).glob("*.md"))
            if len(paths) != expected:
                incomplete.append(f"{lang}/{module}: expected {expected} source observations, found {len(paths)}")
            for path in paths:
                label = f"{lang}/{module}/{path.stem}"
                try:
                    content = path.read_text(encoding="utf-8")
                    metadata = _frontmatter(content)
                    document = included.get(path.stem)
                    source = observations_root.parent / "documents" / path.stem / "sections" / f"{module}.txt"
                    current_hash = (sha256(source.read_text(encoding="utf-8").encode()).hexdigest() if source.is_file()
                                    else frozen_sections.get((lang, module, path.stem)))
                    valid = bool(
                        metadata.get("observation_status") == "complete"
                        and metadata.get("document_id") == path.stem
                        and metadata.get("language") == lang and metadata.get("module") == module
                        and document and module in document["recognized_modules"]
                        and metadata.get("source") == document["relative_path"]
                        and metadata.get("source_sha256") == document["sha256"]
                        and metadata.get("section_sha256") == current_hash
                        and "Pending Agent observation" not in content
                    )
                except (OSError, ValueError):
                    valid = False
                if not valid:
                    incomplete.append(label)
    return incomplete


def _set_synthesis_status(content: str, status: str) -> str:
    updated, replacements = re.subn(
        r"(?m)^synthesis_status:\s*[^\n]+$",
        f"synthesis_status: {status}",
        content,
        count=1,
    )
    if replacements != 1:
        raise ValueError("module profile is missing synthesis_status frontmatter")
    return updated


def _invalidate_integration(profile_dir: Path) -> None:
    for relative in (
        "en/integrated.md",
        "zh/integrated.md",
        "bilingual/cross-lingual.md",
        "bilingual/conflicts.md",
    ):
        (profile_dir / relative).unlink(missing_ok=True)


def _render_integrated(
    profile: str, language: str, profile_dir: Path, quality: dict[str, Any]
) -> str:
    other = "zh" if language == "en" else "en"
    counts = quality.get("module_samples", {}).get(language, {})
    other_counts = quality.get("module_samples", {}).get(other, {})
    weights = {
        module: bilingual_blend(counts.get(module, 0), other_counts.get(module, 0))
        for module in MODULES
    }
    metadata = {
        "profile": profile,
        "language": language,
        "secondary_language": other,
        "integration_policy_version": 2,
        "weight_policy": "per-module-corpus-evidence",
        "module_weights": weights,
    }
    lines = [
        "---\n" + yaml.safe_dump(metadata, sort_keys=False).strip() + "\n---",
        f"# Integrated {language.upper()} writing profile",
        "",
        "Use module-specific profiles before this integrated fallback. The weights describe corpus influence, not observed quality. A language with zero sources contributes no corpus evidence; its guidance provides linguistic assistance only.",
        "",
        "## Module routing",
        "",
    ]
    for module in MODULES:
        blend = weights[module]
        lines.append(
            f"- `{module}`: `{language}/modules/{module}.md` ({counts.get(module, 0)} sources); secondary `{other}/modules/{module}.md` ({other_counts.get(module, 0)} sources). Corpus weights: target={blend['target_weight']}, secondary={blend['secondary_weight']}; {blend['status']}."
        )
    lines.extend(
        [
            "",
            "## Shared constraints",
            "",
            "- Preserve factual grounding from `paper-context.yaml`.",
            "- Use only supplied citation keys.",
            "- Transfer discourse functions, never source-language surface syntax.",
            "- Keep language-evidence status in the profile or review record, outside manuscript content.",
        ]
    )
    return "\n".join(lines) + "\n"


def bilingual_blend(target_count: int, secondary_count: int) -> dict[str, Any]:
    """Use one policy in integration artifacts and executable drafting briefs."""
    both = bool(target_count and secondary_count)
    return {
        "target_weight": 0.7 if both else (1.0 if target_count else 0.0),
        "secondary_weight": 0.3 if both else (1.0 if secondary_count else 0.0),
        "status": "complete" if both else (
            "degraded-single-language" if target_count or secondary_count else "no-corpus-evidence"
        ),
    }


def _render_cross_lingual(profile: str, profile_dir: Path, quality: dict[str, Any]) -> str:
    counts = quality.get("module_samples", {})
    lines = [
        "---",
        f"profile: {profile}",
        "mode: bilingual",
        "integration_policy_version: 2",
        "both_language_target_weight: 0.7",
        "both_language_secondary_weight: 0.3",
        "weight_policy: conditional-on-both-languages-having-evidence",
        "single_language_corpus_weight: 1.0",
        "---",
        "# Cross-lingual academic structure profile",
        "",
        "Align high-level rhetorical functions across English and Chinese. Do not translate or reuse source sentences.",
        "",
        "## Aligned modules",
        "",
        "| Module | English sources | Chinese sources | Transfer rule |",
        "|---|---:|---:|---|",
    ]
    for module in MODULES:
        en = counts.get("en", {}).get(module, 0)
        zh = counts.get("zh", {}).get(module, 0)
        rule = ("bidirectional; target=0.7, secondary=0.3" if en and zh else
                "English corpus=1.0; Chinese assistance=0.0" if en else
                "Chinese corpus=1.0; English assistance=0.0" if zh else "no corpus evidence")
        lines.append(f"| {module} | {en} | {zh} | {rule} |")
    lines.extend(
        [
            "",
            "## Transfer boundaries",
            "",
            "- Transfer problem framing, gap placement, contribution ordering, evidence chains, and conclusion closure.",
            "- Keep terminology, grammar, voice, citation punctuation, and sentence rhythm under the target-language profile.",
            "- The 70/30 split applies only when both module languages have evidence. Otherwise assign the available language 100% corpus influence and the unavailable language 0%.",
            "- Mark one-language evidence as degraded. Target-language grammar may use general language ability, but must not be presented as an observed missing-language corpus style.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_conflicts(profile: str, quality: dict[str, Any]) -> str:
    metrics = quality.get("metrics", {})
    counts = quality.get("module_samples", {})
    lines = [
        "---",
        f"profile: {profile}",
        "integration_policy_version: 2",
        "resolution: target-language-wins",
        "---",
        "# Bilingual profile conflicts",
        "",
        "When English and Chinese conventions conflict, preserve the rhetorical function but use the target language's wording and grammar.",
        "Extracted-text diagnostics are not reviewed style evidence. English word counts and Chinese character counts use different units and must not be treated as a shared scale.",
        "",
        "| Module | Potential metric differences | Resolution |",
        "|---|---|---|",
    ]
    for module in MODULES:
        en_count = counts.get("en", {}).get(module, 0)
        zh_count = counts.get("zh", {}).get(module, 0)
        if not en_count or not zh_count:
            absent = "Chinese" if en_count else "English" if zh_count else "English or Chinese"
            lines.append(f"| {module} | No observed {absent} evidence; no bilingual comparison | Available corpus evidence only; other-language assistance |")
            continue
        en = metrics.get("en", {}).get(module, {})
        zh = metrics.get("zh", {}).get(module, {})
        differences = (
            f"sentence length en={en.get('average_sentence_length', 0)}, "
            f"zh={zh.get('average_sentence_length', 0)}; "
            f"first-person en={en.get('first_person_markers', 0)}, "
            f"zh={zh.get('first_person_markers', 0)}"
        )
        lines.append(f"| {module} | {differences} | Target-language convention |")
    return "\n".join(lines) + "\n"


def _frontmatter(content: str) -> dict[str, Any]:
    if not content.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unclosed YAML frontmatter")
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data


def _safe_stem(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9-]+", "-", value).strip("-").casefold()
    return safe[:60] or "paper"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
