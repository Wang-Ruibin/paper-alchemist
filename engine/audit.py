"""Reproducible draft diagnostics; semantic verification remains an Agent task."""

from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from .context import citation_keys, get_nested, missing_context_fields
from .extractors import text_encoding_warnings
from .terminology import terminology_guidance

_NUMBER = re.compile(
    r"(?<![\w.])[+\-−]?\d+(?:(?:,|\{,\})\d{3})*(?:\.\d+)?(?:[eE][+-]?\d+)?"
    r"(?:\s*(?:%|percent\b|per\s+cent\b))?(?!\w|\.\d)", re.I,
)
_SPELLED_NUMBERS = {word: str(index) for index, word in enumerate(("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"))}
_CITE = re.compile(r"\\cite\w*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}|\[@([^\]]+)\]")
_WORDS = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
_MANUSCRIPT_SCAFFOLDING = re.compile(
    r"\bas an? (?:AI(?: language)? model|AI assistant|large language model)\b"
    r"|(?m:^[ \t>]*(?:here is|below is|the following is) (?:the |your )?(?:requested )?(?:draft|manuscript|paper|section)\b)"
    r"|\bsynthetic evaluation notice\b"
    r"|all study names, references, experimental conditions and outcomes are fictional supplied facts"
    r"|(?m:^[ \t>]*以下(?:是|为)(?:按要求)?(?:生成|撰写|整理|提供)的(?:论文|初稿|章节|正文))"
    r"|(?m:^[ \t>]*作为(?:一个|一名)?(?:人工智能|AI|语言模型)(?:助手|模型)?[，,：:])",
    re.I,
)
_CLAIM_CHECKS = (
    ("optimality", r"\b(?:globally optimal|global optimality|proven optimal|provably optimal|guarantees? optimality|optimal solution)\b|全局最优|证明最优|保证最优"),
    ("significance", r"\b(?:statistically significant|significantly (?:better|outperforms?|improves?|reduces?))\b|统计显著|显著优于|显著提升"),
    ("novelty", r"\b(?:first (?:algorithm|method|approach|study)|unprecedented|state-of-the-art performance)\b|首次提出|首个算法|前所未有"),
    ("complexity", r"\bNP[- ]hard\b|\\(?:mathcal|mathrm)\{O\}|\bO\([^)]*\)"),
    ("generality", r"\b(?:all (?:instances|problems|applications)|any (?:instance|problem)|guaranteed convergence|parameter[- ]free)\b|任意问题|所有实例|保证收敛|无参数"),
)


def _scalars(value: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _scalars(child, f"{prefix}.{key}".strip("."))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _scalars(child, f"{prefix}.{index}")
    elif value is not None:
        yield prefix, str(value)


def _number_key(raw: str) -> str:
    value = re.sub(r"\s+", "", raw.replace("{,}", ",").replace(",", "").replace("+", "").replace("−", "-")).casefold()
    if value.endswith("percent"):
        value = value[:-7] + "%"
    unit = "%" if value.endswith("%") else ""
    number = value[:-1] if unit else value
    try:
        parsed = Decimal(number)
    except InvalidOperation:
        return value
    if not parsed.is_finite():
        return value
    sign, digits, exponent = parsed.as_tuple()
    if not any(digits):
        return "0" + unit
    # Work on the exact tuple: Decimal.normalize() can round long literals under
    # the ambient precision. Scientific notation also avoids expanding 1e99999.
    significant = list(digits)
    while significant[-1] == 0:
        significant.pop()
        exponent += 1
    return ("-" if sign else "") + "".join(map(str, significant)) + "e" + str(exponent) + unit


def _explicit_percent_numbers(research: dict) -> set[str]:
    """Use declared units, never convert an unlabelled ratio into a percentage."""
    accepted = set()
    for path, value in _scalars(research):
        parts = path.split(".")
        leaf = parts[-1]
        measurement = bool(re.fullmatch(r"value|exact|display|decimal_\d+", leaf))
        percent_field = leaf.casefold().endswith("_percent")
        percent_parent = measurement and any(part.casefold().endswith("_percent") for part in parts[:-1])
        parent = _read_provenance(research, ".".join(parts[:-1])) if len(parts) > 1 else research
        explicit_unit = measurement and isinstance(parent, dict) and str(parent.get("unit", "")).strip().casefold() in {"%", "percent"}
        if (percent_field or percent_parent or explicit_unit) and re.fullmatch(
            r"[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][+-]?\d+)?", value.strip(),
        ):
            accepted.add(_number_key(value.strip() + "%"))
    return accepted


def _bibliography_entries(text: str) -> Iterable[tuple[int, int, str]]:
    """Recognize explicitly keyed entries, not an arbitrary trailing text region."""
    for block in re.finditer(
        r"\\begin\s*\{thebibliography\}\s*\{[^{}]*\}(.*?)\\end\s*\{thebibliography\}",
        text, re.S,
    ):
        entries = list(re.finditer(r"\\bibitem(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}", block.group(1)))
        for index, entry in enumerate(entries):
            end = entries[index + 1].start() if index + 1 < len(entries) else len(block.group(1))
            yield block.start(1) + entry.start(), block.start(1) + end, entry.group(1).strip()
    headings = list(re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", text))
    for index, heading in enumerate(headings):
        if heading.group(2).strip().casefold() not in {"references", "bibliography", "参考文献"}:
            continue
        end = next((other.start() for other in headings[index + 1:]
                    if len(other.group(1)) <= len(heading.group(1))), len(text))
        body = text[heading.end():end]
        entry_pattern = (
            r"(?m)^[ \t]*(?:[-*+][ \t]+)?"
            r"(?:\[([A-Za-z0-9_.:+-]+)\]"
            r"|\*\*\[([A-Za-z0-9_.:+-]+)\]\*\*"
            r"|\*\*([A-Za-z0-9_.:+-]+)\.\*\*)[ \t]+[^\n]+"
        )
        for entry in re.finditer(entry_pattern, body):
            entry_end = entry.end()
            # A wrapped entry may continue in its paragraph. Blank lines,
            # another keyed entry or a heading end its numeric evidence scope.
            for line_index, line in enumerate(body[entry_end:].splitlines(keepends=True)):
                if line_index == 0 and line in {"\n", "\r\n"}:
                    entry_end += len(line)
                    continue
                if not line.strip():
                    break
                if re.match(r"\s*(?:[-*+]\s+)?(?:\[|\*\*)|\s*#", line):
                    break
                entry_end += len(line)
            key = next(key for key in entry.groups() if key is not None)
            yield heading.end() + entry.start(), heading.end() + entry_end, key


def _citation_record(context: dict, key: str) -> Any:
    citations = context.get("citations", {})
    if isinstance(citations, dict):
        return citations.get(key)
    if isinstance(citations, list):
        return next((row for row in citations if isinstance(row, dict) and row.get("key") == key), None)
    return None


def _math_spans(text: str) -> list[tuple[int, int]]:
    spans = [match.span() for match in re.finditer(
        r"\\\(.*?\\\)|\\\[.*?\\\]|(?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)\$(?!\$).*?(?<!\\)\$",
        text, re.S,
    )]
    spans.extend(match.span() for match in re.finditer(
        r"\\begin\s*\{((?:equation|align|aligned|gather|gathered|multline|flalign|eqnarray|displaymath|math|cases)\*?)\}"
        r".*?\\end\s*\{\1\}", text, re.S,
    ))
    return spans


def _math_scientific_numbers(text: str) -> str:
    """Normalize literal base-ten displays in math, preserving source offsets."""
    spans = _math_spans(text)
    if not spans:
        return text
    mantissa = r"[+\-−]?\d+(?:(?:,|\{,\})\d{3})*(?:\.\d+)?"
    pattern = re.compile(
        r"(?<![\w.\\+\-−])(?:(?P<coefficient>" + mantissa +
        r")\s*(?:\\times|\\cdot|×|·)\s*|(?P<sign>[+\-−]?))10\s*\^\s*"
        r"(?:\{\s*(?P<exponent>[+\-−]?\s*\d+)\s*\}|(?P<single>\d)(?!\d))"
    )

    def replace(match: re.Match) -> str:
        if not any(start <= match.start() and match.end() <= end for start, end in spans):
            return match.group()
        exponent = re.sub(r"\s+", "", match.group("exponent") or match.group("single")).replace("−", "-")
        coefficient = match.group("coefficient") or (match.group("sign") + "1")
        coefficient = coefficient.replace("{,}", "").replace(",", "").replace("−", "-")
        literal = coefficient + "e" + exponent
        return literal + " " * (len(match.group()) - len(literal))

    return pattern.sub(replace, text)


def _table_preambles(text: str) -> Iterable[tuple[int, int, str]]:
    for match in re.finditer(r"\\begin\s*\{(tabularx|tabular\*?|array)\}\s*(?:\[[^\]]*\]\s*)?", text):
        position = match.end()
        count = 2 if match.group(1) in {"tabularx", "tabular*"} else 1
        for index in range(count):
            while position < len(text) and text[position].isspace():
                position += 1
            if position >= len(text) or text[position] != "{":
                break
            start, depth = position + 1, 1
            position += 1
            while position < len(text) and depth:
                if position == 0 or text[position - 1] != "\\":
                    depth += (text[position] == "{") - (text[position] == "}")
                position += 1
            if depth:
                break
            yield start, position - 1, "columns" if index == count - 1 else "width"


def _mask_tex_layout(text: str) -> str:
    def mask(match: re.Match) -> str:
        return " " * len(match.group())
    text = re.sub(
        r"\\renewcommand\*?\s*\{\s*\\(?:arraystretch|baselinestretch)\s*\}\s*\{[^{}]*\}",
        mask, text,
    )
    text = re.sub(r"\\(?:clubpenalty|widowpenalty)\s*(?:=\s*)?[+-]?\d+", mask, text)
    lengths = {"linewidth", "textwidth", "columnwidth", "textheight", "hsize", "vsize"}
    lengths.update(re.findall(r"\\newlength\s*\{\s*\\([A-Za-z@]+)\s*\}", text))
    dimension = r"(?:\d+(?:\.\d+)?|\.\d+)\s*\\(?:" + "|".join(sorted(map(re.escape, lengths))) + r")"
    for start, end, kind in _table_preambles(text):
        contents = text[start:end]
        if kind == "width" and re.fullmatch(r"\s*" + dimension + r"\s*", contents):
            replacement = " " * len(contents)
        elif kind == "columns":
            replacement = re.sub(r"[pmb]\{\s*" + dimension + r"\s*\}", mask, contents)
        else:
            continue
        text = text[:start] + replacement + text[end:]
    return text


def _prose(text: str, *, numeric: bool = False) -> str:
    """Mask citation keys, markup and section/enumeration numbers, not result values."""
    def mask(match: re.Match) -> str:
        return " " * len(match.group())
    if numeric:
        text = _math_scientific_numbers(text)
    text = _CITE.sub(mask, text)
    text = re.sub(r"(?m)^#{1,6}\s+.*$|\\(?:sub)*section\*?\{[^}]*\}|\\label\{[^}]*\}", mask, text)
    # The bibliography argument controls the rendered label width, not a study value.
    text = re.sub(r"\\begin\s*\{thebibliography\}\s*\{[^{}]*\}", mask, text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", mask, text)
    text = re.sub(r"\[\d+(?:[,;–-]\s*\d+)*\]|\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)", mask, text)
    if numeric:
        text = _mask_tex_layout(text)
        math = _math_spans(text)
        text = re.sub(r"(?<=\d)--+(?=\d)", lambda match: match.group() if any(
            start <= match.start() < end for start, end in math
        ) else "–" + " " * (len(match.group()) - 1), text)
    return text.replace(r"\%", " %")


def _words(text: str) -> list[str]:
    return [word.casefold() for word in _WORDS.findall(unicodedata.normalize("NFKC", _prose(text)))]


def _single_number_cell(text: str) -> bool:
    """Only an entire scalar cell inherits a header unit; annotations stay explicit."""
    value = _prose(text, numeric=True).strip()
    for _ in range(3):
        before = value
        for left, right in [(r"\(", r"\)"), ("$", "$"), ("**", "**"), ("`", "`")]:
            if value.startswith(left) and value.endswith(right) and len(value) > len(left) + len(right):
                value = value[len(left):-len(right)].strip()
                break
        wrapped = re.fullmatch(r"\\(?:textbf|textit|mathrm|mathbf|num)\s*\{(.*)\}", value, re.S)
        if wrapped:
            value = wrapped.group(1).strip()
        if value == before:
            break
    return _NUMBER.fullmatch(value) is not None


def _percent_header(text: str, *, tex: bool) -> bool:
    if re.search(r"\bpercentage[-\s]+points?\b|\bpp\b", text, re.I):
        return False
    if _NUMBER.search(_prose(text, numeric=True)):
        return False  # A percentage-valued data row is not a column declaration.
    return bool((r"\%" in text if tex else "%" in text) or
                re.search(r"\(\s*(?:percent|per\s+cent)\s*\)", text, re.I))


def _markdown_cells(line: str, offset: int) -> list[tuple[int, int]]:
    cells, start, position = [], 0, 0
    while position < len(line):
        if line[position] == "\\":
            position += 2
            continue
        if line[position] == "|":
            cells.append((offset + start, offset + position))
            start = position + 1
        position += 1
    cells.append((offset + start, offset + len(line)))
    if cells and not line[cells[0][0] - offset:cells[0][1] - offset].strip():
        cells.pop(0)
    if cells and not line[cells[-1][0] - offset:cells[-1][1] - offset].strip():
        cells.pop()
    return cells


def _tex_comments_masked(text: str) -> str:
    value = list(text)
    position = 0
    while position < len(text):
        if text[position] == "\\":
            position += 2
        elif text[position] == "%":
            end = text.find("\n", position)
            end = len(text) if end < 0 else end
            value[position:end] = " " * (end - position)
            position = end
        else:
            position += 1
    return "".join(value)


def _tex_table_rows(text: str, start: int, end: int) -> list[list[tuple[int, int]]]:
    rows, row, cell_start, position, depth = [], [], start, start, 0
    while position < end:
        char = text[position]
        if char == "\\":
            if text[position:position + 2] == r"\\" and depth == 0:
                row.append((cell_start, position))
                rows.append(row)
                row = []
                position += 2
                spacing = re.match(r"\s*\[[^\]]*\]", text[position:end])
                if spacing:
                    position += spacing.end()
                cell_start = position
            else:
                position += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "&" and depth == 0:
            row.append((cell_start, position))
            cell_start = position + 1
        position += 1
    row.append((cell_start, end))
    rows.append(row)
    return rows


def _percent_table_cells(text: str) -> list[tuple[int, int]]:
    """Read explicit units in simple column headers, without global numeric exemptions."""
    spans = []
    lines, offset = [], 0
    for line in text.splitlines(keepends=True):
        lines.append((line, offset))
        offset += len(line)
    index = 0
    while index + 1 < len(lines):
        line, offset = lines[index]
        header = _markdown_cells(line, offset) if "|" in line else []
        separator, separator_offset = lines[index + 1]
        alignment = _markdown_cells(separator, separator_offset) if "|" in separator else []
        if len(header) < 2 or len(header) != len(alignment) or not all(
            re.fullmatch(r"\s*:?-{3,}:?\s*", text[start:end]) for start, end in alignment
        ):
            index += 1
            continue
        columns = {i for i, (start, end) in enumerate(header) if _percent_header(text[start:end], tex=False)}
        index += 2
        while index < len(lines):
            line, offset = lines[index]
            cells = _markdown_cells(line, offset) if "|" in line else []
            if len(cells) != len(header):
                break
            spans.extend(cells[i] for i in columns if _single_number_cell(text[slice(*cells[i])]))
            index += 1
    masked = _tex_comments_masked(text)
    for begin in re.finditer(r"\\begin\s*\{(tabularx|tabular\*?|array)\}\s*(?:\[[^\]]*\]\s*)?", masked):
        position = begin.end()
        valid = True
        for _ in range(2 if begin.group(1) in {"tabularx", "tabular*"} else 1):
            while position < len(masked) and masked[position].isspace():
                position += 1
            if position >= len(masked) or masked[position] != "{":
                valid = False
                break
            position += 1
            depth = 1
            while position < len(masked) and depth:
                if masked[position] == "\\":
                    position += 2
                    continue
                depth += (masked[position] == "{") - (masked[position] == "}")
                position += 1
            if depth:
                valid = False
                break
        end = re.search(r"\\end\s*\{" + re.escape(begin.group(1)) + r"\}", masked[position:]) if valid else None
        if end is None:
            continue
        stop = position + end.start()
        body = masked[position:stop]
        if re.search(r"\\(?:begin|multicolumn|multirow)\b", body):
            continue  # No inferred units through nested or spanning structures.
        rows = [row for row in _tex_table_rows(masked, position, stop) if len(row) >= 2]
        if not rows:
            continue
        header = rows[0]
        columns = {i for i, (start, end) in enumerate(header) if _percent_header(masked[start:end], tex=True)}
        for cells in rows[1:]:
            if len(cells) == len(header):
                spans.extend(cells[i] for i in columns if _single_number_cell(masked[slice(*cells[i])]))
    return spans


def _copy_matches(text: str, corpus: dict[str, str], threshold: int = 13) -> list[dict]:
    words = _words(text)
    if len(words) < threshold:
        return []
    positions: dict[tuple[str, ...], int] = {}
    for index in range(len(words) - threshold + 1):
        positions.setdefault(tuple(words[index:index + threshold]), index)
    matches = []
    for name, reference in corpus.items():
        tokens = _words(reference)
        for index in range(len(tokens) - threshold + 1):
            sequence = tuple(tokens[index:index + threshold])
            if sequence in positions:
                matches.append({"source": name, "draft_word_offset": positions[sequence],
                                "reference_word_offset": index, "overlap_words": threshold})
                break
    return matches


def _read_provenance(context: dict, path: str) -> Any:
    current: Any = context
    for component in path.split("."):
        if isinstance(current, dict):
            current = current.get(component)
        elif isinstance(current, list) and component.isdigit() and int(component) < len(current):
            current = current[int(component)]
        else:
            return None
    return current


def audit_draft(
    text: str, context: dict[str, Any], module: str = "section",
    registry: dict | None = None, corpus: dict[str, str] | None = None,
    semantic_review: dict | None = None,
    *, copy_index: dict | None = None,
) -> dict[str, Any]:
    digest = sha256(text.encode()).hexdigest()
    context_hash = sha256(json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    issues: list[dict] = []

    def issue(code: str, message: str, severity: str = "error", **evidence: Any) -> None:
        issues.append({"code": code, "severity": severity, "message": message, **evidence})

    if not text.strip():
        issue("empty-draft", "The draft is empty.")
    for match in _MANUSCRIPT_SCAFFOLDING.finditer(text):
        issue("manuscript-scaffolding", "Remove assistant or evaluation framing from the manuscript; keep operational records separate.", offset=match.start())
    for field in missing_context_fields(context, module):
        issue("missing-fact", f"Missing required research facts: {field}")
    authorized = set(citation_keys(context))
    used = set()
    for match in _CITE.finditer(text):
        raw = match.group(1) or match.group(2)
        keys = ([key.strip() for key in raw.split(",")] if match.group(1)
                else re.findall(r"@([A-Za-z0-9_.:+-]+)", "@" + raw))
        for key in keys:
            if not key:
                continue
            used.add(key)
            if key not in authorized:
                issue("unauthorized-citation", f"Citation is not authorized: {key}", offset=match.start())
    # Numeric citation lists and author-year prose cannot be validated by key.
    if re.search(r"\[\d+(?:[,;–-]\s*\d+)*\]|\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)", text):
        issue("unmapped-citation", "Map rendered citations to supplied bibliography keys before acceptance.", "review")
    facts = list(_scalars(context.get("research", {})))
    allowed_numbers = {_number_key(match.group()) for _, value in facts
                       for match in _NUMBER.finditer(_math_scientific_numbers(value))}
    allowed_numbers.update(_number_key(_SPELLED_NUMBERS[word.casefold()]) for _, value in facts
                           for word in re.findall(r"\b(?:" + "|".join(_SPELLED_NUMBERS) + r")\b", value, re.I))
    allowed_numbers.update(_explicit_percent_numbers(context.get("research", {})))
    semantic_status = "not-performed"
    if semantic_review is not None:
        if not isinstance(semantic_review, dict):
            issue("invalid-semantic-review", "The semantic review must be an object.")
            semantic_status = "invalid"
        else:
            semantic_status = _validate_semantic_review(semantic_review, digest, context_hash, context, text, issues)
            if semantic_status == "verified":
                allowed_numbers.update(_derived_values(semantic_review, context, text, issues))
    numeric_prose = _prose(text, numeric=True)
    bibliography_keys = []
    for start, end, key in _bibliography_entries(text):
        bibliography_keys.append(key)
        if key not in authorized:
            issue("unauthorized-bibliography", f"Bibliography key is not authorized: {key}", offset=start)
        else:
            source_numbers = {_number_key(match.group()) for _, value in _scalars(_citation_record(context, key))
                              for match in _NUMBER.finditer(value)}
            for match in _NUMBER.finditer(_prose(text[start:end], numeric=True)):
                if _number_key(match.group()) not in source_numbers:
                    issue("unsupported-bibliography-number",
                          f"Numeric literal is absent from this citation's metadata: {match.group().strip()}",
                          citation_key=key, offset=start + match.start())
        numeric_prose = numeric_prose[:start] + " " * (end - start) + numeric_prose[end:]
    percent_cells = _percent_table_cells(text)
    for match in _NUMBER.finditer(numeric_prose):
        value = _number_key(match.group())
        if not value.endswith("%") and any(start <= match.start() < end for start, end in percent_cells):
            value += "%"
        if value not in allowed_numbers:
            issue("unsupported-number", f"Numeric literal is absent from the research facts: {match.group().strip()}", offset=match.start())
    # Occurrence is only an initial diagnostic; the semantic ledger verifies roles.
    for code, pattern in _CLAIM_CHECKS:
        for match in re.finditer(pattern, text, re.I):
            issue(f"review-{code}", f"Verify the scope and evidence for: {match.group()}", "review", offset=match.start())
    for phrase in get_nested(context, "writing.forbidden_expressions") or []:
        if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I):
            issue("forbidden-expression", f"The confirmed writing contract prohibits: {phrase}")
    terms = terminology_guidance(context, registry) if registry else None
    if terms and terms["clarification_required"]:
        issue("unresolved-variant", "Expand the problem name and confirm the variant before applying terminology.")
    overlaps = _copy_matches(text, corpus or {})
    if copy_index:
        from .copying import indexed_matches

        overlaps.extend(indexed_matches(text, copy_index))
    for overlap in overlaps:
        issue("source-overlap", "At least 13 consecutive normalized words match corpus prose; review copying and formula exclusions.", "review", **overlap)
    uncertain_encodings = []
    for name, reference in (corpus or {}).items():
        warnings = text_encoding_warnings(reference)
        if warnings:
            uncertain_encodings.append({"source": name, "text_sha256": sha256(reference.encode()).hexdigest(), "warnings": warnings})
            issue("copy-source-encoding", "Reference glyph uncertainty can hide word overlaps. Review the affected source pages or verified recovery before accepting the copying gate.", "review", source=name)
    indexed_sources = copy_index.get("sources", []) if copy_index else []
    from .copy_evidence import active_uncertainties

    for source in indexed_sources:
        remaining = active_uncertainties(source)
        if remaining:
            uncertain_encodings.append({"source": source["relative_path"], "source_sha256": source["sha256"],
                                        "warnings": remaining, "basis": "source-bound-lexical-fingerprint"})
            issue("copy-source-encoding", "The portable lexical screen has source glyph uncertainty; its coverage does not include unrecovered words.",
                  "review", source=source["relative_path"])
    mechanical_pass = not any(row["severity"] == "error" for row in issues)
    return {
        "schema_version": 1, "draft_sha256": digest, "context_sha256": context_hash,
        "module": module, "automated_checks_pass": mechanical_pass,
        "semantic_review_status": semantic_status,
        "ready_after_review": mechanical_pass and semantic_status == "verified",
        "used_citation_keys": sorted(used), "terminology": terms,
        "bibliography_check": {"mapped_entries": len(bibliography_keys), "mapped_keys": sorted(set(bibliography_keys)),
                               "scope": "Explicitly keyed reference entries use their own authorized citation metadata; those numbers do not become study facts."},
        "copy_check": {"performed": bool(corpus or indexed_sources),
                       "reference_sources": len(corpus or {}) + len(indexed_sources), "threshold_words": 13,
                       "raw_reference_units": len(corpus or {}), "indexed_reference_papers": len(indexed_sources),
                       "expected_indexed_reference_papers": copy_index.get("expected_reference_sources") if copy_index else None,
                       "indexed_section_coverage_complete": copy_index.get("coverage_complete_for_declared_extracted_sections", False) if copy_index else False,
                       "reviewed_decoded_reference_papers": sum(bool(source.get("decoded_variants")) for source in indexed_sources),
                       "encoding_uncertainties": uncertain_encodings,
                       "scope": "Exact normalized English word sequences within supplied or indexed extracted sections; no semantic, Chinese, full-PDF or unrecovered-glyph copying clearance."},
        "issues": issues,
        "limitations": [
            "Numeric occurrence does not verify the associated population, metric, comparator, direction or unit.",
            "Regex checks cannot establish factual entailment, technical validity, citation support or quality of prose.",
            "A semantic-review record is an accountable Agent or human judgment, not machine proof or peer review.",
        ],
    }


def _validate_semantic_review(review: dict, digest: str, context_hash: str, context: dict,
                              text: str, issues: list) -> str:
    def error(message: str) -> str:
        issues.append({"code": "invalid-semantic-review", "severity": "error", "message": message})
        return "invalid"
    if review.get("draft_sha256") != digest or review.get("context_sha256") != context_hash:
        return error("The semantic review is not bound to the current draft and facts.")
    if review.get("reviewer_kind") not in {"agent", "human"} or not review.get("reviewer"):
        return error("Identify the reviewer and distinguish Agent judgment from human review.")
    dimensions = ("factual_entailment", "terminology_and_notation", "citation_entailment", "claim_calibration", "cross_section_consistency", "copying", "format")
    checks = review.get("checks", {})
    if any(checks.get(name) != "pass" for name in dimensions):
        return error("Every semantic gate requires an explicit pass judgment; unresolved gates cannot be accepted.")
    claims = review.get("claims", [])
    if not isinstance(claims, list) or not claims:
        return error("Provide the reviewed claim ledger with context paths and rationale.")
    for claim in claims:
        if not isinstance(claim, dict) or not claim.get("text") or claim["text"] not in text:
            return error("Each reviewed claim must quote a span present in the current draft.")
        paths = claim.get("context_paths", [])
        if (not isinstance(paths, list) or not paths
                or any(not isinstance(path, str) or _read_provenance(context, path) is None for path in paths)):
            return error("A claim cites a missing or invalid context fact.")
        if all(path == "materials" or path.startswith("materials.") for path in paths):
            return error("Writing-material availability alone cannot support a research claim; use confirmed study facts or authorized source evidence.")
        if claim.get("judgment") != "supported" or len(str(claim.get("rationale", "")).strip()) < 20:
            return error("Each claim requires a supported judgment and a substantive rationale.")
    if review.get("coverage") != "all-factual-and-citation-bearing-sentences":
        return error("The reviewer must attest coverage of all factual and citation-bearing sentences.")
    # Verify sentence coverage explicitly: the reviewer cannot approve one sentence
    # of a long draft by setting a status flag. Non-claims need their own rationale.
    excluded = review.get("non_claim_spans", [])
    reviewed_spans = [claim["text"] for claim in claims]
    for row in excluded:
        if not isinstance(row, dict) or not row.get("text") or row["text"] not in text or len(str(row.get("rationale", ""))) < 20:
            return error("Non-claim spans require exact draft text and a substantive rationale.")
        reviewed_spans.append(row["text"])
    unreviewed = text
    for span in sorted(reviewed_spans, key=len, reverse=True):
        unreviewed = unreviewed.replace(span, " ")
    unreviewed = re.sub(r"(?m)^#{1,6}\s+.*$|\\(?:sub)*section\*?\{[^}]*\}|\\(?:begin|end)\{[^}]*\}", " ", unreviewed)
    if len(_WORDS.findall(unreviewed)) > 0 or re.search(r"[\u3400-\u9fff]", unreviewed):
        return error("The ledger leaves unreviewed prose; include supported claims or justified non-claim spans.")
    return "verified"


def _derived_values(review: dict, context: dict, text: str, issues: list) -> set[str]:
    """Verify explicitly reviewed sums rather than importing arbitrary new values."""
    accepted = set()
    for row in review.get("derived_values", []):
        try:
            if (not isinstance(row, dict) or row.get("operation") != "sum"
                    or not row.get("claim_text") or row["claim_text"] not in text):
                raise ValueError("A derivation needs a supported sum and an exact draft claim")
            operands = row.get("operands", [])
            if len(operands) < 2:
                raise ValueError("A sum needs at least two fact-bound operands")
            total = Decimal(0)
            for operand in operands:
                source = _read_provenance(context, operand["context_path"])
                literal = _number_key(str(operand["literal"]))
                present = {_number_key(match.group()) for match in _NUMBER.finditer(_math_scientific_numbers(str(source)))}
                if source is None or literal not in present or "%" in literal:
                    raise ValueError("A sum operand is not an explicit numeric context value")
                total += Decimal(literal)
            value = _number_key(str(row["value"]))
            if "%" in value or Decimal(value) != total:
                raise ValueError("The derived sum is arithmetically incorrect")
            if value not in {_number_key(match.group()) for match in _NUMBER.finditer(_math_scientific_numbers(row["claim_text"]))}:
                raise ValueError("The derived value is absent from the reviewed claim")
            accepted.add(value)
        except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
            issues.append({"code": "invalid-derivation", "severity": "error", "message": str(exc)})
    return accepted


def load_copy_corpus(root: Path | None) -> dict[str, str]:
    if root is None:
        return {}
    if not root.is_dir():
        raise ValueError("Copy-check corpus must be a directory of permitted extracted prose files")
    return {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(root.rglob("*.txt")) if path.is_file() and path.name != "full.txt"}
