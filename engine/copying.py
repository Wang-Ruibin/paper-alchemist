"""Source-bound lexical fingerprints; no recoverable reference prose is shipped."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

NORMALIZATION = "nfkc-prose-english-words-v1"
THRESHOLD = 13
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _digest(words: list[str]) -> str:
    return sha256(" ".join(words).encode("utf-8")).hexdigest()


def validate_fingerprint(record: dict, document: dict) -> None:
    if (not isinstance(record, dict) or record.get("schema_version") != 1
            or record.get("kind") != "paper-alchemist-copy-fingerprints"
            or record.get("normalization") != NORMALIZATION or record.get("threshold_words") != THRESHOLD
            or record.get("hash_algorithm") != "sha256"
            or any(record.get(key) != document.get(key) for key in ("id", "relative_path", "sha256"))):
        raise ValueError("Copy fingerprints differ from their source binding or normalization")
    hashes = record.get("fingerprints")
    sections = record.get("sections")
    if (not isinstance(hashes, list) or any(not isinstance(value, str) or not _HEX.fullmatch(value) for value in hashes)
            or hashes != sorted(set(hashes)) or not isinstance(sections, list)
            or {row.get("module") for row in sections} != set(document.get("recognized_modules", []))
            or len(sections) != len(document.get("recognized_modules", []))
            or not isinstance(record.get("encoding_uncertainties"), list)):
        raise ValueError("Invalid copy-fingerprint inventory")
    for row in sections:
        if (not _HEX.fullmatch(str(row.get("section_sha256", "")))
                or not isinstance(row.get("normalized_words"), int) or row["normalized_words"] < 0):
            raise ValueError("Invalid copy-fingerprint section binding")
    from .copy_evidence import validate_variant

    variants = record.get("decoded_variants", [])
    if not isinstance(variants, list):
        raise ValueError("Invalid decoded copy evidence")
    for variant in variants:
        validate_variant(variant, record)


def build_fingerprints(document: dict, sections: dict[str, str]) -> dict:
    from .audit import _words
    from .extractors import text_encoding_warnings

    if set(sections) != set(document["recognized_modules"]):
        raise ValueError("Copy fingerprints require all recognized sections for their declared scope")
    hashes, bindings, uncertain = set(), [], []
    for module, text in sorted(sections.items()):
        words = _words(text)
        hashes.update(_digest(words[index:index + THRESHOLD]) for index in range(max(0, len(words) - THRESHOLD + 1)))
        digest = sha256(text.encode("utf-8")).hexdigest()
        bindings.append(dict(module=module, section_sha256=digest, normalized_words=len(words)))
        warnings = text_encoding_warnings(text)
        if warnings:
            uncertain.append(dict(module=module, section_sha256=digest, warnings=warnings))
    record = dict(schema_version=1, kind="paper-alchemist-copy-fingerprints",
                  **{key: document[key] for key in ("id", "relative_path", "sha256")},
                  normalization=NORMALIZATION, threshold_words=THRESHOLD, hash_algorithm="sha256",
                  language_scope="normalized-English-words", sections=bindings,
                  fingerprints=sorted(hashes), encoding_uncertainties=uncertain,
                  source_prose_included=False,
                  limits=["Exact normalized word sequences within recognized extracted sections only; not semantic similarity or a full plagiarism check.",
                          "No cross-section-boundary, Chinese prose, unreadable glyph or unrecovered PDF-layout coverage is claimed."])
    validate_fingerprint(record, document)
    return record


def profile_fingerprints(profile: str, workspace: Path) -> dict[str, bytes]:
    """Return stored or locally recoverable records without editing any profile."""
    from .bundled import reviewed_copy_upgrade
    from .copy_evidence import local_variants, merge_variants, section_binding
    from .portable import load_snapshot
    from .profiles import state_root

    state = state_root(workspace)
    directory, cache = state / "profiles" / profile, state / "cache" / profile
    manifest = json.loads((directory / "source-manifest.json").read_text(encoding="utf-8"))
    snapshot, errors = load_snapshot(directory)
    if errors:
        raise ValueError("; ".join(errors))
    frozen = {(row["document_id"], row["module"]): row["section_sha256"]
              for row in snapshot["observations"]} if snapshot else {}
    payload = {}
    for document in manifest["documents"]:
        if not document.get("included"):
            continue
        path = cache / "copy-fingerprints" / (document["id"] + ".json")
        paths = {module: cache / "documents" / document["id"] / "sections" / (module + ".txt")
                 for module in document["recognized_modules"]}
        if all(path.is_file() for path in paths.values()):
            sections = {module: path.read_text(encoding="utf-8") for module, path in paths.items()}
            record = build_fingerprints(document, sections)
        elif path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
        else:
            continue
        validate_fingerprint(record, document)
        if snapshot and any(frozen.get((document["id"], row["module"])) != row["section_sha256"]
                            for row in record["sections"]):
            raise ValueError("Copy fingerprints differ from reviewed snapshot sections")
        variants = local_variants(profile, workspace, record)
        if path.is_file():
            stored = json.loads(path.read_text(encoding="utf-8"))
            if (stored.get("sha256") == record["sha256"]
                    and section_binding(stored) == section_binding(record)):
                variants.extend(stored.get("decoded_variants", []))
        upgrade = reviewed_copy_upgrade(document)
        if upgrade is not None and section_binding(upgrade) == section_binding(record):
            variants.extend(upgrade.get("decoded_variants", []))
        record = merge_variants(record, variants)
        validate_fingerprint(record, document)
        payload[f"cache/copy-fingerprints/{document['id']}.json"] = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    return payload


def load_profile_fingerprints(profile: str, workspace: Path) -> dict:
    from .additions import registered_additions
    from .profiles import state_root

    names = [profile, *[row["profile"] for row in registered_additions(profile, workspace) if row["active"]]]
    sources, expected = [], 0
    for name in names:
        manifest = json.loads((state_root(workspace) / "profiles" / name / "source-manifest.json").read_text(encoding="utf-8"))
        expected += sum(bool(row.get("included")) for row in manifest["documents"])
        for data in profile_fingerprints(name, workspace).values():
            sources.append({**json.loads(data), "profile": name})
    return {"schema_version": 1, "normalization": NORMALIZATION, "threshold_words": THRESHOLD,
            "sources": sources, "expected_reference_sources": expected,
            "coverage_complete_for_declared_extracted_sections": len(sources) == expected and expected > 0}


def indexed_matches(text: str, index: dict) -> list[dict]:
    from .audit import _words

    if index.get("normalization") != NORMALIZATION or index.get("threshold_words") != THRESHOLD:
        raise ValueError("Unsupported copying-index normalization")
    words = _words(text)
    positions = {_digest(words[offset:offset + THRESHOLD]): offset
                 for offset in reversed(range(max(0, len(words) - THRESHOLD + 1)))}
    matches = []
    for source in index["sources"]:
        from .copy_evidence import validate_variant

        fingerprints = set(source["fingerprints"])
        for variant in source.get("decoded_variants", []):
            validate_variant(variant, source)
            fingerprints.update(variant["additional_fingerprints"])
        shared = positions.keys() & fingerprints
        if shared:
            digest = min(shared, key=positions.get)
            matches.append({"source": source["relative_path"], "profile": source.get("profile"),
                            "source_sha256": source["sha256"], "draft_word_offset": positions[digest],
                            "overlap_words": THRESHOLD, "fingerprint_sha256": digest,
                            "basis": "source-bound-lexical-fingerprint"})
    return matches
