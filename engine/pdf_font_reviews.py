"""Source-bound, explicitly reviewed font decoding for copy-check evidence."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .extractors import text_encoding_warnings

_HEX = re.compile(r"[0-9a-fA-F]{64}\Z")
_CODE = re.compile(r"(?:[0-9a-fA-F]{2}){1,4}\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\ufffd]")


def _font_encoding(font: Any) -> tuple[Any, dict]:
    try:
        from pypdf._cmap import get_encoding
    except ImportError as error:
        raise ValueError("Reviewed font decoding requires pypdf6.10 or later") from error
    return get_encoding(font)


def _width(encoding: Any, cmap: dict) -> int:
    if isinstance(encoding, str) and encoding.lower().startswith("utf-16"):
        return 2
    value = cmap.get(-1, 1)
    if isinstance(value, int) and 1 <= value <= 4:
        return value
    return 1


def _decode(code: bytes, encoding: Any, cmap: dict) -> str:
    if isinstance(encoding, dict):
        intermediate = "".join(encoding.get(byte, chr(byte)) for byte in code)
    else:
        intermediate = code.decode(encoding)
    return "".join(cmap.get(char, char) for char in intermediate)


def _used_codes(reader: Any, selected: set[int]) -> dict[int, set[bytes]]:
    from pypdf.generic import ContentStream

    codes: dict[int, set[bytes]] = defaultdict(set)
    encodings = {}

    def capture(value: Any, font: Any) -> None:
        if font is None:
            return
        identifier = font.indirect_reference.idnum
        if identifier not in selected:
            return
        if identifier not in encodings:
            encodings[identifier] = _font_encoding(font)
        encoding, cmap = encodings[identifier]
        width = _width(encoding, cmap)
        raw = bytes(value) if isinstance(value, bytes) else value.original_bytes
        if len(raw) % width:
            raise ValueError("A reviewed font contains an unsupported variable-width text code")
        codes[identifier].update(raw[i:i + width] for i in range(0, len(raw), width))

    def visit(stream: Any, resources: Any, inherited: dict, active: set[int]) -> None:
        if len(active) >= 31:
            raise ValueError("Unbounded PDF form nesting")
        state = dict(inherited)
        stack = []
        for args, operator in ContentStream(stream, reader).operations:
            if operator == b"q":
                stack.append(dict(state))
            elif operator == b"Q":
                state = stack.pop() if stack else dict(inherited)
            elif operator == b"Tf":
                state["font"] = resources["/Font"][args[0]].get_object()
            elif operator in {b"Tj", b"'", b'"'}:
                capture(args[-1], state.get("font"))
            elif operator == b"TJ":
                for value in args[0]:
                    if isinstance(value, (str, bytes)):
                        capture(value, state.get("font"))
            elif operator == b"Do":
                reference = resources.get("/XObject", {}).get(args[0])
                if reference is not None:
                    form = reference.get_object()
                    if form.get("/Subtype") == "/Form":
                        identifier = getattr(reference, "idnum", id(form))
                        if identifier in active:
                            raise ValueError("Cyclic PDF form")
                        visit(form, form.get("/Resources", resources).get_object(), state, active | {identifier})
    for page in reader.pages:
        visit(page.get_contents(), page["/Resources"].get_object(), {"font": None}, set())
    return codes


def _cmap_bytes(mappings: dict[bytes, str]) -> bytes:
    widths = sorted({len(code) for code in mappings})
    lines = [
        "/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /ReviewedCopyEvidence def", "/CMapType 2 def",
        f"{len(widths)} begincodespacerange",
        *[f"<{'00' * width}> <{'FF' * width}>" for width in widths],
        "endcodespacerange",
    ]
    entries = sorted(mappings.items())
    for offset in range(0, len(entries), 100):
        batch = entries[offset:offset + 100]
        lines.append(f"{len(batch)} beginbfchar")
        for code, value in batch:
            if not value:
                raise ValueError("An empty original glyph mapping cannot be normalized implicitly")
            lines.append(f"<{code.hex().upper()}> <{value.encode('utf-16-be').hex().upper()}>")
        lines.append("endbfchar")
    lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"])
    return ("\n".join(lines) + "\n").encode("ascii")


def reviewed_copy_text(source: Path, review_path: Path) -> dict[str, Any]:
    """Decode a private candidate; do not edit the PDF or semantic profile/cache."""
    from pypdf import PdfReader
    from pypdf.generic import DecodedStreamObject, IndirectObject, NameObject

    original = source.read_bytes()
    source_sha = sha256(original).hexdigest()
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if (not isinstance(review, dict) or review.get("schema_version") != 1
            or review.get("kind") != "source-bound-font-glyph-review"
            or not review.get("reviewer") or review.get("reviewer_kind") not in {"agent", "human"}
            or not isinstance(review.get("mappings"), list)):
        raise ValueError("Identify a source-bound glyph reviewer and mapping inventory")
    rows = [row for row in review["mappings"] if isinstance(row, dict) and row.get("source_sha256") == source_sha]
    if not rows:
        raise ValueError("No reviewed glyph mappings match the actual source bytes")
    reader = PdfReader(source)
    fonts, replacements = {}, defaultdict(dict)
    for row in rows:
        identifier = row.get("font_object")
        value, evidence = row.get("unicode_text"), row.get("visual_evidence_image_sha256")
        if (not isinstance(identifier, int) or isinstance(identifier, bool) or identifier <= 0
                or row.get("review_status") != "complete"
                or not isinstance(value, str) or not 1 <= len(value) <= 8 or _CONTROL.search(value)
                or not isinstance(evidence, str) or not _HEX.fullmatch(evidence)
                or len(str(row.get("rationale", "")).strip()) < 20):
            raise ValueError("Every glyph needs a completed, identified, source-evidenced review")
        try:
            font = fonts.setdefault(identifier, IndirectObject(identifier, 0, reader).get_object())
        except (ValueError, AttributeError, KeyError) as error:
            raise ValueError("The reviewed PDF font object is unavailable") from error
        if font.get("/Type") != "/Font":
            raise ValueError("The reviewed object is not a PDF font")
        raw_hex = row.get("raw_glyph_hex")
        if raw_hex is None and font.get("/Subtype") == "/Type3":
            codepoint = row.get("codepoint", "")
            if re.fullmatch(r"U\+[0-9A-Fa-f]{4}", codepoint) and int(codepoint[2:], 16) <= 255:
                # Legacy diagnostic sheets rendered exactly this one-byte Type3 code.
                raw_hex = f"{int(codepoint[2:], 16):02X}"
        if not isinstance(raw_hex, str) or not _CODE.fullmatch(raw_hex):
            raise ValueError("A glyph review requires its actual encoded PDF character bytes")
        code = bytes.fromhex(raw_hex)
        previous = replacements[identifier].get(code)
        if previous is not None and previous != value:
            raise ValueError("Conflicting reviews for the same source font and glyph")
        replacements[identifier][code] = value
    used = _used_codes(reader, set(fonts))
    applied = 0
    for identifier, changes in replacements.items():
        if not set(changes) <= used.get(identifier, set()):
            raise ValueError("A reviewed glyph is not used by its named font in this PDF")
        encoding, cmap = _font_encoding(fonts[identifier])
        try:
            values = {code: _decode(code, encoding, cmap) for code in used[identifier]}
        except (UnicodeError, LookupError) as error:
            raise ValueError("The original font encoding cannot be decoded faithfully") from error
        values.update(changes)
        normalized = DecodedStreamObject()
        normalized.set_data(_cmap_bytes(values))
        fonts[identifier][NameObject("/ToUnicode")] = normalized
        applied += len(changes)
    pages = [page.extract_text() or "" for page in reader.pages]
    # These are actual PDF page boundaries, not inferred missing letters.
    text = "\n\f\n".join(pages)
    warnings = [{"page": index + 1, "warnings": found}
                for index, page in enumerate(pages) if (found := text_encoding_warnings(page))]
    if source.read_bytes() != original:
        raise ValueError("The source PDF changed during font review")
    return {
        "schema_version": 1, "source_sha256": source_sha, "review_sha256": sha256(review_bytes).hexdigest(),
        "reviewer": review["reviewer"], "reviewer_kind": review["reviewer_kind"],
        "fonts_verified": len(fonts), "applied_glyph_mappings": applied, "pages": len(pages),
        "text": text, "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "encoding_warnings": warnings, "source_pdf_modified": False, "semantic_profile_modified": False,
        "scope": "Only explicitly reviewed source/font/encoded-glyph mappings; remaining fonts stay unchanged. This candidate is not a completed semantic or manuscript review.",
    }


def prepare_copy_text(source: Path, review_path: Path | None = None) -> dict[str, Any]:
    if review_path is not None:
        return reviewed_copy_text(source, review_path)
    from pypdf import PdfReader

    original = source.read_bytes()
    pages = [page.extract_text() or "" for page in PdfReader(source).pages]
    text = "\n\f\n".join(pages)
    if source.read_bytes() != original:
        raise ValueError("The source PDF changed during text extraction")
    return {
        "schema_version": 1, "source_sha256": sha256(original).hexdigest(),
        "review_sha256": None, "reviewer": None, "reviewer_kind": None,
        "fonts_verified": 0, "applied_glyph_mappings": 0, "pages": len(pages),
        "text": text, "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "encoding_warnings": [{"page": index + 1, "warnings": found}
                              for index, page in enumerate(pages) if (found := text_encoding_warnings(page))],
        "source_pdf_modified": False, "semantic_profile_modified": False,
        "scope": "Full PDF text from the current decoder, without inferred glyph substitutions. This candidate is not a semantic or manuscript review.",
    }


def save_reviewed_copy_candidate(source: Path, review_path: Path | None, workspace: Path) -> dict[str, Any]:
    """Save a private diagnostic without claiming source-review completion."""
    import pypdf

    result = prepare_copy_text(source, review_path)
    producer = ("reviewed-font-copy-v1:" if review_path else "pypdf-copy-v1:") + pypdf.__version__
    identity = sha256(((result["review_sha256"] or "no-font-substitutions") + producer).encode()).hexdigest()[:24]
    directory = workspace.resolve() / ".paper-alchemist" / "copy-font-reviews" / result["source_sha256"] / identity
    if not directory.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("The copy candidate leaves its workspace")
    candidate, receipt = directory / "candidate.txt", directory / "receipt.json"
    payload = result["text"].encode("utf-8")
    if candidate.exists() and candidate.read_bytes() != payload:
        raise ValueError("Existing copy candidate differs; preserve and review that evidence")
    if receipt.exists():
        previous = json.loads(receipt.read_text(encoding="utf-8"))
        if (not candidate.is_file() or previous.get("text_sha256") != result["text_sha256"]
                or previous.get("review_sha256") != result["review_sha256"]
                or previous.get("source_sha256") != result["source_sha256"]
                or previous.get("producer") != producer):
            raise ValueError("Existing copy-candidate receipt differs from current evidence")
        return previous
    directory.mkdir(parents=True, exist_ok=True)
    if not candidate.exists():
        candidate.write_bytes(payload)
    report = {key: value for key, value in result.items() if key != "text"}
    report.update(
        source=str(source.resolve()), review_file=str(review_path.resolve()) if review_path else None, candidate=str(candidate),
        producer=producer, created_at_utc=datetime.now(timezone.utc).isoformat(),
        diagnostic_only=True, semantic_review_performed=False,
        notice="Inspect the remaining warnings and source coverage. This candidate does not update or complete a semantic profile or manuscript audit.",
    )
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
