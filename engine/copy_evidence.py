"""Add decoded lexical evidence without changing reviewed semantic source bytes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_FIELDS = {
    "schema_version", "kind", "source_sha256", "base_section_bindings_sha256",
    "text_sha256", "producer", "pages", "normalized_words", "font_review_sha256",
    "applied_glyph_mappings", "reviewer", "reviewer_kind", "reviewed_at_utc",
    "review_scope", "coverage", "encoding_warnings", "additional_fingerprints",
    "source_prose_included",
}


def section_binding(record: dict) -> str:
    rows = sorted((row["module"], row["section_sha256"]) for row in record["sections"])
    return sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def validate_variant(variant: dict, record: dict) -> None:
    if (not isinstance(variant, dict) or set(variant) != _FIELDS
            or variant["schema_version"] != 1 or variant["kind"] != "source-bound-decoded-copy-evidence"
            or variant["source_sha256"] != record["sha256"]
            or variant["base_section_bindings_sha256"] != section_binding(record)
            or variant["coverage"] != "full-PDF-decoded-text" or variant["encoding_warnings"] != []
            or variant["source_prose_included"] is not False
            or not isinstance(variant["reviewer"], str) or not variant["reviewer"].strip()
            or variant["reviewer_kind"] not in {"agent", "human"}
            or not isinstance(variant["review_scope"], str) or len(variant["review_scope"].strip()) < 40
            or not isinstance(variant["reviewed_at_utc"], str) or not variant["reviewed_at_utc"]
            or not _HEX.fullmatch(str(variant["text_sha256"]))
            or type(variant["pages"]) is not int or variant["pages"] <= 0
            or type(variant["normalized_words"]) is not int or variant["normalized_words"] < 13
            or type(variant["applied_glyph_mappings"]) is not int or variant["applied_glyph_mappings"] < 0
            or not isinstance(variant["producer"], str)
            or not variant["producer"].startswith(("pypdf-copy-v1:", "reviewed-font-copy-v1:"))):
        raise ValueError("Decoded copy evidence differs from its source, section bindings or completed review")
    font_review = variant["font_review_sha256"]
    if ((font_review is not None and not _HEX.fullmatch(str(font_review)))
            or (variant["applied_glyph_mappings"] and font_review is None)):
        raise ValueError("Reviewed glyph recovery lacks its source-bound review")
    values = variant["additional_fingerprints"]
    if (not isinstance(values, list) or any(not isinstance(v, str) or not _HEX.fullmatch(v) for v in values)
            or values != sorted(set(values))):
        raise ValueError("Invalid decoded copy fingerprint inventory")


def merge_variants(record: dict, variants: list[dict]) -> dict:
    combined = {}
    for variant in [*record.get("decoded_variants", []), *variants]:
        validate_variant(variant, record)
        key = (variant["text_sha256"], variant["producer"], variant["font_review_sha256"])
        combined.setdefault(key, variant)
    return {**record, "decoded_variants": list(combined.values())} if combined else record


def active_uncertainties(record: dict) -> list:
    variants = record.get("decoded_variants", [])
    for variant in variants:
        validate_variant(variant, record)
    return [] if variants else record["encoding_uncertainties"]


def local_variants(profile: str, workspace: Path, record: dict) -> list[dict]:
    from .profiles import state_root

    folder = state_root(workspace) / "copy-evidence" / profile / record["id"]
    result = []
    for path in sorted(folder.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("source_sha256") != record["sha256"]
                or value.get("base_section_bindings_sha256") != section_binding(record)):
            continue  # A later source or boundary update retains, but cannot reuse, this evidence.
        validate_variant(value, record)
        result.append(value)
    return result


def register_copy_evidence(profile: str, workspace: Path, source: str, receipt_path: Path,
                           reviewer: str, review_scope: str, reviewer_kind: str = "agent",
                           *, _records: list[dict] | None = None) -> dict:
    from pypdf import PdfReader

    from .audit import _words
    from .copying import THRESHOLD, _digest, profile_fingerprints
    from .extractors import text_encoding_warnings
    from .profiles import profile_slug, state_root

    name = profile_slug(profile)
    records = (_records if _records is not None
               else [json.loads(value) for value in profile_fingerprints(name, workspace).values()])
    matches = [record for record in records if record["relative_path"] == source]
    if len(matches) != 1:
        raise ValueError("Name one currently included source with complete section fingerprints")
    record = matches[0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    candidate = Path(receipt["candidate"]).resolve()
    if not candidate.is_relative_to(workspace.resolve()):
        raise ValueError("The private copy candidate leaves its writing workspace")
    original = Path(receipt["source"])
    text = candidate.read_bytes().decode("utf-8")
    if (receipt.get("schema_version") != 1 or receipt.get("source_sha256") != record["sha256"]
            or sha256(original.read_bytes()).hexdigest() != record["sha256"]
            or sha256(text.encode()).hexdigest() != receipt.get("text_sha256")
            or len(PdfReader(original).pages) != receipt.get("pages")
            or receipt.get("encoding_warnings") != [] or text_encoding_warnings(text)
            or receipt.get("source_pdf_modified") is not False
            or receipt.get("semantic_profile_modified") is not False
            or receipt.get("diagnostic_only") is not True):
        raise ValueError("The current source, candidate bytes, page coverage or unresolved glyphs differ")
    words = _words(text)
    hashes = {_digest(words[offset:offset + THRESHOLD]) for offset in range(max(0, len(words) - THRESHOLD + 1))}
    variant = {
        "schema_version": 1, "kind": "source-bound-decoded-copy-evidence",
        "source_sha256": record["sha256"], "base_section_bindings_sha256": section_binding(record),
        "text_sha256": receipt["text_sha256"], "producer": receipt["producer"], "pages": receipt["pages"],
        "normalized_words": len(words), "font_review_sha256": receipt.get("review_sha256"),
        "applied_glyph_mappings": receipt.get("applied_glyph_mappings", 0),
        "reviewer": reviewer, "reviewer_kind": reviewer_kind,
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "review_scope": review_scope,
        "coverage": "full-PDF-decoded-text", "encoding_warnings": [],
        "additional_fingerprints": sorted(hashes - set(record["fingerprints"])),
        "source_prose_included": False,
    }
    validate_variant(variant, record)
    identity = sha256((variant["text_sha256"] + variant["producer"] + variant["base_section_bindings_sha256"]).encode()).hexdigest()
    target = state_root(workspace) / "copy-evidence" / name / record["id"] / (identity + ".json")
    if target.exists():
        previous = json.loads(target.read_text(encoding="utf-8"))
        validate_variant(previous, record)
        if {k: v for k, v in previous.items() if k != "reviewed_at_utc"} != {k: v for k, v in variant.items() if k != "reviewed_at_utc"}:
            raise ValueError("An existing copy review differs; preserve and resolve the review explicitly")
        variant = previous
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(variant, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "profile": name, "source": source, "source_sha256": record["sha256"], "review": str(target),
        "additional_fingerprints": len(variant["additional_fingerprints"]),
        "legacy_encoding_warnings_retained": len(record["encoding_uncertainties"]),
        "active_encoding_uncertainties": 0, "semantic_profile_modified": False, "source_prose_included": False,
        "scope": "Reviewed decoded English lexical evidence only; not semantic originality, Chinese copying or manuscript acceptance.",
    }


def register_copy_evidence_batch(profile: str, workspace: Path, reviews: Path, reviewer: str,
                                 review_scope: str, reviewer_kind: str = "agent") -> dict:
    from .copying import profile_fingerprints
    from .profiles import profile_slug

    rows = json.loads(reviews.read_text(encoding="utf-8"))
    if (not isinstance(rows, list) or not rows
            or any(not isinstance(row, dict) or set(row) != {"source", "receipt"}
                   or not isinstance(row["source"], str) or not isinstance(row["receipt"], str) for row in rows)
            or len({row["source"] for row in rows}) != len(rows)):
        raise ValueError("Supply a nonempty, unique source-and-receipt review list")
    name = profile_slug(profile)
    records = [json.loads(value) for value in profile_fingerprints(name, workspace).values()]
    results = [register_copy_evidence(name, workspace, row["source"], Path(row["receipt"]),
                                     reviewer, review_scope, reviewer_kind, _records=records) for row in rows]
    return {"profile": name, "registered_sources": len(results), "results": results,
            "semantic_profile_modified": False, "source_prose_included": False}
