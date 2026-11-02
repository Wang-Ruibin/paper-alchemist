"""Persist Codex-authored semantic observations through the plugin runtime."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

import yaml

from .constants import MODULES
from .profiles import (
    _frontmatter,
    _incomplete_observations,
    _invalidate_integration,
    _retain_observation_history,
    _set_synthesis_status,
    profile_slug,
    state_root,
    utc_now,
)

FIELDS = {
    "rhetorical_moves": "Rhetorical moves and order",
    "language_and_stance": "Language and stance",
    "evidence_introduction": "Evidence introduction",
    "transferable_pattern": "Transferable pattern",
    "risks_and_exceptions": "Risks and exceptions",
}


def record_observations(workspace: Path, profile: str, annotations: Path,
                        reviewer: str, reviewer_kind: str = "agent") -> dict:
    if not reviewer.strip() or reviewer_kind not in {"agent", "human"}:
        raise ValueError("Identify the semantic reviewer and reviewer kind")
    state = state_root(workspace)
    slug = profile_slug(profile)
    cache = state / "cache" / slug
    corpus = json.loads((state / "profiles" / slug / "source-manifest.json").read_text(encoding="utf-8"))
    documents = {item["relative_path"]: item for item in corpus["documents"] if item["included"]}
    rows = json.loads(annotations.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Supply a nonempty list of semantic observation annotations")
    prepared, seen, semantic_modules = [], set(), set()
    unchanged = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("source") not in documents:
            raise ValueError("Each annotation must name a currently included source")
        doc, module, language = documents[row["source"]], row.get("module"), row.get("language")
        if module not in MODULES or language not in {"en", "zh"}:
            raise ValueError("Invalid annotation module or language")
        key = (row["source"], language, module)
        if key in seen:
            raise ValueError("Duplicate semantic observation annotation")
        seen.add(key)
        scope = row.get("reading_scope")
        if not isinstance(scope, (str, dict)) or (isinstance(scope, str) and len(scope.strip()) < 20):
            raise ValueError("Record the actual reading scope; windowed reading is not a complete-section review")
        section = cache / "documents" / doc["id"] / "sections" / f"{module}.txt"
        if module not in doc["recognized_modules"] or not section.is_file():
            raise ValueError("Annotation section is absent from current source evidence")
        section_text = section.read_text(encoding="utf-8")
        digest = sha256(section_text.encode()).hexdigest()
        if isinstance(scope, dict):
            intervals = scope.get("read_char_intervals_half_open")
            if not isinstance(intervals, list) or not intervals or scope.get("section_length_characters") != len(section_text):
                raise ValueError("Structured reading scope must match the current section length and intervals")
            end, coverage = 0, 0
            for interval in intervals:
                if (not isinstance(interval, list) or len(interval) != 2
                        or any(type(value) is not int for value in interval)
                        or not end <= interval[0] < interval[1] <= len(section_text)):
                    raise ValueError("Reading intervals must be ordered, disjoint and within the current section")
                end, coverage = interval[1], coverage + interval[1] - interval[0]
            if scope.get("read_characters") != coverage or not scope.get("mode") or not scope.get("interpretation"):
                raise ValueError("Structured reading scope must record actual coverage and interpretation")
            if scope["mode"] == "complete-section" and coverage != len(section_text):
                raise ValueError("A partial reading scope cannot claim a complete-section review")
        if digest != row.get("section_sha256"):
            raise ValueError(f"Evidence changed since semantic review: {row['source']}/{module}")
        if row.get("source_sha256", doc["sha256"]) != doc["sha256"]:
            raise ValueError("Source identity changed since semantic review")
        path = cache / "observations" / language / module / f"{doc['id']}.md"
        content = path.read_text(encoding="utf-8")
        metadata = _frontmatter(content)
        if (metadata.get("language") != language or metadata.get("document_id") != doc["id"]
                or metadata.get("module") != module):
            raise ValueError("Observation template does not match the source and language")
        body = content.split("---", 2)[2]
        semantic_changed = (
            metadata.get("observation_status") != "complete"
            or metadata.get("reading_scope") != scope
            or metadata.get("source") != row["source"]
            or metadata.get("source_sha256") != doc["sha256"]
            or metadata.get("section_sha256") != digest
        )
        for field, heading in FIELDS.items():
            text = row.get(field)
            if not isinstance(text, str) or len(text.strip()) < 40 or "Pending Agent" in text:
                raise ValueError(f"Missing substantive semantic observation: {field}")
            previous = re.search(rf"## {re.escape(heading)}\n\n(.*?)(?=\n## |\Z)", body, flags=re.S)
            semantic_changed = semantic_changed or previous is None or previous.group(1).strip() != text.strip()
            body, count = re.subn(rf"(## {re.escape(heading)}\n\n).*?(?=\n## |\Z)",
                                 lambda match: match.group(1) + text.strip() + "\n", body, flags=re.S)
            if count != 1:
                raise ValueError(f"Observation template missing {heading}")
        if not semantic_changed and metadata.get("reviewer") == reviewer and metadata.get("reviewer_kind") == reviewer_kind:
            unchanged += 1
            continue
        if semantic_changed:
            semantic_modules.add((language, module))
        old_status = metadata.get("observation_status")
        metadata.update(observation_status="complete", source=row["source"], source_sha256=doc["sha256"],
                        section_sha256=digest, reading_scope=row["reading_scope"],
                        reviewer_kind=reviewer_kind, reviewer=reviewer, reviewed_at=utc_now())
        prepared.append((path, "---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip() + "\n---" + body,
                         language, module, row["source"], old_status))
    # Validate every annotation before writing any record in this batch.
    for path, content, language, module, source, old_status in prepared:
        if old_status in {"complete", "stale"}:
            _retain_observation_history(cache, language, module, source, path.read_bytes(), overwrite=old_status == "complete")
        path.write_text(content, encoding="utf-8")
    directory = state / "profiles" / slug
    quality_path = directory / "quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    stale_profiles = set()
    for language, module in sorted(semantic_modules):
        other = "zh" if language == "en" else "en"
        affected = [language]
        if not quality.get("module_samples", {}).get(other, {}).get(module, 0):
            affected.append(other)
        for target_language in affected:
            target = directory / target_language / "modules" / f"{module}.md"
            if target.is_file():
                content = target.read_text(encoding="utf-8")
                if _frontmatter(content).get("synthesis_status") == "complete":
                    target.write_text(_set_synthesis_status(content, "stale"), encoding="utf-8")
                    stale_profiles.add(f"{target_language}/{module}")
    if semantic_modules:
        _invalidate_integration(directory)
        quality["integration_status"] = "pending"
        quality.pop("integrated_at", None)
    quality["incomplete_observation_count"] = len(_incomplete_observations(directory))
    quality["last_observation_review_at"] = utc_now()
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"recorded_observations": len(rows), "written_observations": len(prepared),
            "unchanged_observations": unchanged, "stale_profiles": sorted(stale_profiles),
            "reviewer": reviewer, "reviewer_kind": reviewer_kind,
            "semantic_author": "identified reviewer; not this persistence command"}
