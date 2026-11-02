"""Apply source-bound Agent-reviewed section spans when PDF headings are ambiguous."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from .constants import MODULES
from .sections import segment_sections


def load_section_maps(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported section-map schema")
    rows = data.get("documents")
    if not isinstance(rows, list):
        raise ValueError("Section maps require a documents list")
    maps = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("source"), str):
            raise ValueError("Each section map requires a source")
        name = row["source"]
        if name in maps:
            raise ValueError("Section-map sources must be unique")
        if row.get("reviewer_kind") not in {"agent", "human"} or not row.get("reviewer"):
            raise ValueError("A section map needs an identified semantic reviewer")
        if row.get("review_status") != "complete" or not row.get("rationale"):
            raise ValueError("An incomplete semantic boundary map cannot replace automatic sections")
        maps[name] = row
    return maps


def mapped_sections(text: str, source_hash: str, row: dict) -> dict[str, str]:
    if row.get("source_sha256") != source_hash or row.get("text_sha256") != sha256(text.encode()).hexdigest():
        raise ValueError(f"Section-map evidence changed: {row['source']}")
    spans = row.get("spans")
    if not isinstance(spans, list) or not spans:
        raise ValueError("A section map requires reviewed spans")
    partial = "replace_modules" in row
    selected = row.get("replace_modules")
    if partial and (
        not isinstance(selected, list) or not selected
        or any(not isinstance(module, str) or module not in MODULES for module in selected)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("replace_modules must list unique known academic modules")
    buckets: dict[str, list[tuple[int, str, str]]] = {}
    previous_end = 0
    for span in spans:
        if not isinstance(span, dict):
            raise ValueError("Section spans must be objects")
        module = span.get("module")
        start, end = span.get("start"), span.get("end")
        if module not in {*MODULES, "exclude"}:
            raise ValueError("Unknown section-map module")
        if partial and module != "exclude" and module not in selected:
            raise ValueError("Mapped span is outside the selected replacement modules")
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(text) or start < previous_end):
            raise ValueError("Section spans must be ordered, disjoint and inside the current text")
        if not span.get("scope") or not span.get("notes"):
            raise ValueError("Record the scope and source evidence for each mapped span")
        order = span.get("module_order", len(spans))
        join = span.get("join", "paragraph")
        if (type(order) is not int or order < 0 or not isinstance(join, str)
                or join not in {"paragraph", "continuation", "word"}):
            raise ValueError("Invalid module reading order or continuation rule")
        if module == "exclude" and join == "word":
            raise ValueError("A reviewed word join cannot be an exclusion rule")
        previous_end = end
        if module != "exclude":
            buckets.setdefault(module, []).append((order, text[start:end].strip(), join))
    result = {}
    for name, values in buckets.items():
        content = ""
        for _, value, join in sorted(values, key=lambda row: row[0]):
            if join == "word":
                if not content or not value or not content[-1].isalpha() or not value[0].isalpha():
                    raise ValueError("A reviewed word join requires two existing letter fragments")
                separator = ""
            else:
                separator = " " if join == "continuation" else "\n\n"
            content += separator + value
        if len(content.strip()) >= 120:
            result[name] = content.strip()
    if partial:
        preserved = {module: content for module, content in segment_sections(text).items()
                     if module not in selected}
        return preserved | result
    return result
