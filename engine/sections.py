"""Academic section recognition and deterministic descriptive statistics."""

from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from statistics import mean

from .constants import MODULES

_HEADING_PREFIX = re.compile(r"^\s*(?:#{1,6}\s+|(?:\d+(?:\.\d+)*)[.)]?\s+)?(.{2,120}?)\s*$")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s*")
_NUMBERING = r"(?:(?:\d{1,2}(?:\.\d{1,2})*|[IVXLCDM]{1,8})[.)]?|[A-Z][.)])"
_NUMBERED_HEADING = re.compile(rf"^({_NUMBERING})(?:\s+|(?<=[.)]))(.+)$")
_NON_TITLE_START = re.compile(
    r"(?:this (?:study|paper)|these |those |we |our |it |according |given |let |"
    r"article submitted|springer nature|preprint|submitted|accepted|published|"
    r"engineering applications of|computers\s*&|section\s+\d|"
    r"percentage of|performance ratio|gap to|in this|to further|how |does? |"
    r"generate |evaluate |construct |return |while |for |if |"
    r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})",
    re.I,
)
_CITATION_RE = re.compile(
    r"(?:\\cite\w*\{[^}]+\}|\[[0-9,;\-\s]+\]|\([A-Z][A-Za-z-]+(?:\s+et al\.)?,?\s+\d{4}\))"
)

_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract", "summary", "摘要", "摘 要"),
    "introduction": ("introduction", "background", "引言", "绪论", "研究背景"),
    "related-work": (
        "related work",
        "related works",
        "literature review",
        "related studies",
        "文献综述",
        "相关工作",
        "国内外研究",
    ),
    "problem-definition": (
        "problem definition",
        "problem statement",
        "problem formulation",
        "preliminaries",
        "notation and definitions",
        "model and notation",
        "problem description",
        "mathematical formulation",
        "model formulation",
        "问题定义",
        "问题描述",
        "数学模型",
        "模型构建",
    ),
    "methodology": (
        "method",
        "methods",
        "methodology",
        "proposed approach",
        "solution approach",
        "feasibility test",
        "algorithmic proposal",
        "advanced strategies",
        "main scheme",
        "algorithm",
        "solution method",
        "方法",
        "研究方法",
        "算法设计",
        "求解方法",
    ),
    "experiment-setup": (
        "experimental setup",
        "experiment setup",
        "computational setup",
        "experimental design",
        "implementation details",
        "benchmark instances and experimental setup",
        "benchmark instances and experimental configurations",
        "experimental configurations",
        "experimental protocol",
        "experimental conditions",
        "experimental setting",
        "experimental settings",
        "experiment settings",
        "experiments setup",
        "benchmark instances",
        "reference algorithms",
        "instances, reference algorithms and parameter setting",
        "instances and parameters",
        "parameter setting",
        "parameter tuning",
        "实验设置",
        "实验设计",
        "数据与参数",
        "算例与参数",
    ),
    "results-analysis": (
        "results",
        "results and discussion",
        "computational results",
        "computational tests",
        "computational experiments",
        "experimental results",
        "comparative study",
        "analysis",
        "numerical results",
        "ablation study",
        "analyses and discussions",
        "applications of",
        "real-world example",
        "结果分析",
        "实验结果",
        "计算结果",
        "对比分析",
        "消融实验",
    ),
    "conclusion": (
        "conclusion",
        "conclusions",
        "concluding remarks",
        "discussion and conclusion",
        "结论",
        "总结",
        "结语",
    ),
}

_STOP_HEADINGS = (
    "references",
    "bibliography",
    "appendix",
    "acknowledgement",
    "acknowledgment",
    "acknowledgements",
    "acknowledgments",
    "credit authorship contribution statement",
    "credit author statement",
    "declaration of competing interest",
    "data availability",
    "参考文献",
    "附录",
    "致谢",
)

_EXACT_TITLES = {alias.casefold() for aliases in _ALIASES.values() for alias in aliases} | set(_STOP_HEADINGS)
_DENSE_TITLES = {re.sub(r"\s+", "", title): title for title in _EXACT_TITLES}


def _alias_title(normalized: str, alias: str) -> bool:
    return normalized == alias or normalized.startswith(tuple(alias + mark for mark in (" ", ":", ",")))


@lru_cache(maxsize=8192)
def normalize_heading(raw: str) -> str:
    heading = re.sub(r"\s+", " ", raw.strip().strip(".:："))
    for word in ("RELATED", "ASSESSMENT", "COMPUTATIONAL", "EXPERIMENTAL", "ALGORITHM", "METHODOLOGY", "PROBLEM", "RESULTS", "CONCLUSION", "CONCLUSIONS"):
        heading = re.sub(rf"\b{word[0]}\s+{word[1:]}\b", word, heading)
    # IEEE small capitals may extract as "I NTRODUCTION" or "C ONCLUSION".
    # Recover an exact known heading before treating its initial as numbering.
    dense = re.sub(r"\s+", "", heading).casefold()
    if dense in _DENSE_TITLES:
        return _DENSE_TITLES[dense]
    heading = re.sub(rf"^{_NUMBERING}(?:\s+|(?<=[.)]))", "", heading)
    dense = re.sub(r"\s+", "", heading).casefold()
    if dense in _DENSE_TITLES:
        return _DENSE_TITLES[dense]
    return heading.casefold()


@lru_cache(maxsize=8192)
def classify_heading(raw: str) -> str | None:
    normalized = normalize_heading(raw)
    if normalized in {"article info abstract", "article information abstract"}:
        return "abstract"
    if any(normalized == stop or normalized.startswith(stop + " ") for stop in _STOP_HEADINGS):
        return "__stop__"
    for module, aliases in _ALIASES.items():
        for alias in aliases:
            key = alias.casefold()
            if _alias_title(normalized, key):
                return module
    if re.search(r"\b(?:instance|benchmark|parameter)s?\b", normalized) and re.search(
        r"\b(?:setup|setting|configuration|design|implementation|tuning)s?\b", normalized
    ):
        return "experiment-setup"
    if re.search(
        r"\b(?:problem|formulation|preliminaries|notation)s?\b", normalized
    ) and not re.search(r"\b(?:algorithm|heuristic|search|methodology|method)\b", normalized):
        return "problem-definition"
    if re.search(
        r"\b(?:result|experiment|comparison|analysis|performance|sensitivity|ablation|evaluation|assessment|test)s?\b",
        normalized,
    ):
        return "results-analysis"
    if re.search(
        r"\b(?:algorithm|heuristic|matheuristic|method|methodology|procedure|framework|search|formulation)s?\b",
        normalized,
    ):
        return "methodology"
    return None


def looks_like_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    # A large gap between a section number and its title is not a column break.
    number_match = _NUMBERED_HEADING.match(stripped)
    if number_match:
        title = re.split(r"\s{4,}", number_match.group(2), maxsplit=1)[0].strip()
        candidate = f"{number_match.group(1)} {title}"
    else:
        candidate = re.split(r"\s{4,}", stripped, maxsplit=1)[0].strip()
    if len(candidate) > 120:
        return None
    markdown = bool(re.match(r"^#{1,6}\s+", candidate))
    numbered = bool(_NUMBERED_HEADING.match(candidate))
    plain = candidate.lstrip("# ")
    if re.match(r"^algorithm\s+\d+[.:]?\b", plain, re.I):
        return None  # Algorithm floats are not section boundaries.
    known = classify_heading(plain)
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", plain))
    letters = re.sub(r"[^A-Za-z]", "", plain)
    visibly_styled = bool(has_cjk or (letters and (letters.isupper() or plain.istitle())))
    normalized = normalize_heading(plain)
    if numbered:
        body = _NUMBERED_HEADING.match(candidate).group(2).strip()
        if not body or not body[0].isalpha():
            return None
        exact_title = any(_alias_title(normalized, title) for title in _EXACT_TITLES)
        number = _NUMBERED_HEADING.match(candidate).group(1).rstrip(".)")
        if re.fullmatch(r"\d+", number) and int(number) > 20:
            return None  # Counts and margin numbers are not section numbers.
        if re.match(r"(?:algorithm\s+\d+|fig(?:ure)?\.?\s+\d+|table\s+\d+)", body, re.I):
            return None
        if (re.search(r"[.!?;]$|,", body) and not exact_title) or _NON_TITLE_START.match(body):
            return None
        if body and body[0].isalpha() and body[0].islower() and not exact_title:
            return None  # Numerical findings such as "26 improved best results".
    alias_title = any(
        _alias_title(normalized, alias.casefold())
        for aliases in _ALIASES.values() for alias in aliases
    )
    exact_stop = known == "__stop__" and normalized in set(_STOP_HEADINGS)
    appendix_title = bool(re.match(
        r"(?i:appendix)\s+(?:[A-Z](?:\.\d+)*|\d+(?:\.\d+)*)[.:]\s+[A-Z]", plain
    ))
    detached_result_title = bool(re.fullmatch(
        r"Computational results (?:on|for) .{1,80}(?:instances|benchmarks)", plain
    ))
    if known and (markdown or numbered or exact_stop or appendix_title or detached_result_title
                  or (visibly_styled and (alias_title or known == "__stop__"))):
        return known
    match = _HEADING_PREFIX.match(candidate)
    if match and (markdown or numbered):
        return classify_heading(match.group(1))
    return None


def _reference_table_header(lines: list[str], index: int, normalized: str) -> bool:
    """Identify joined table-column labels, not a bibliography title."""
    if not normalized.startswith("references "):
        return False
    columns = normalized.removeprefix("references ")
    labels = r"(?:matheuristics?|metaheuristics?|heuristics?|algorithms?|methods?|approach(?:es)?|strateg(?:y|ies)|instances?|capacity|routes?|depots?)"
    if not re.match(labels + r"\b", columns) or len(re.findall(labels + r"\b", columns)) < 2:
        return False
    return any(re.match(r"\s*table\s+(?:\d+|[IVXLCDM]+)[.:]?(?:\s|$)", value, re.I)
               for value in lines[max(0, index - 6):index])


def _wrapped_appendix_pointer(lines: list[str], index: int, normalized: str) -> bool:
    """Keep an appendix label completing the immediately preceding sentence."""
    if index == 0 or lines[index].lstrip().startswith("#"):
        return False
    if not re.fullmatch(r"appendix\s+[a-z](?:\.\d+)*", normalized):
        return False
    return bool(re.search(
        r"\b(?:shown|given|provided|presented|reported|described|detailed|listed|included|available)\s+in\s*$|\b(?:see|refer to)\s*$",
        lines[index - 1], re.I,
    ))


def segment_sections(text: str) -> dict[str, str]:
    """Split extracted paper text into canonical academic modules."""
    buckets: dict[str, list[str]] = defaultdict(list)
    current: str | None = None
    lines = _join_detached_heading_numbers(_without_line_number_runs(text.splitlines()))
    parents: dict[str, str | None] = {}
    initial_abstract = next((index for index, value in enumerate(lines[:100])
                            if re.match(r"^\s*(?:\d+\s+)?abstract\b", value, re.I)), None)
    introduction_line: int | None = None
    for index, line in enumerate(lines):
        if initial_abstract is not None and index < initial_abstract:
            continue
        inline_abstract = re.match(r"^\s*abstract\s*[.—:–-]\s*(.+)$", line, re.I)
        if inline_abstract:
            current = "abstract"
            buckets[current].append(inline_abstract.group(1))
            continue
        if current == "abstract" and re.match(r"^\s*(?:index terms|key\s*words|funding|note to practitioners)(?:\s*[.—:–-]|\s*$)", line, re.I):
            current = None
            continue
        heading = looks_like_heading(line)
        number = _NUMBERED_HEADING.match(line.strip())
        normalized = normalize_heading(line)
        explicit_module = any(
            _alias_title(normalized, alias.casefold())
            for aliases in _ALIASES.values() for alias in aliases
        )
        number_key = number.group(1).rstrip(".)") if number else ""
        ancestors = number_key.split(".")[:-1]
        parent_module = None
        while ancestors:
            key = ".".join(ancestors)
            if key in parents:
                parent_module = parents[key]
                break
            ancestors.pop()
        if heading and number and "." in number_key and not explicit_module:
            # An overlapping test in a decoding subsection is still methods;
            # an algorithm rationale in a component assessment is still results.
            heading = parent_module or heading
        if heading == "abstract" and introduction_line is not None:
            heading = parent_module or current  # A results summary is not a new abstract.
        if heading == "methodology" and not number and not line.strip().startswith("#"):
            if normalized in {"method", "algorithm"}:
                heading = None  # Common table column headers.
        if heading == "__stop__" and (
            _reference_table_header(lines, index, normalized)
            or _wrapped_appendix_pointer(lines, index, normalized)
        ):
            heading = None
        if heading == "__stop__" and normalized == "references":
            following = [value.strip() for value in lines[index + 1:index + 9] if value.strip()][:2]
            if len(following) == 2 and all(re.fullmatch(r"\[[\d,;\s–-]+\]", value) for value in following):
                # A benchmark table can have a column of citation-key lists.
                # Its label must not discard the remaining research sections.
                heading = None
        if heading == "__stop__":
            if normalized.startswith(("acknowledg", "credit author", "declaration", "data availability")):
                current = None
                continue  # A two-column page may place the conclusion next.
            break  # Never resume research prose after the bibliography/appendix.
        if heading:
            current = heading
            if number:
                parents[number_key] = heading
            if heading == "introduction" and introduction_line is None:
                introduction_line = index
            continue
        if number:
            # A clearly isolated, unclassified title ends the preceding role.
            # A later classified child can then provide evidence in its own role.
            body = number.group(2).strip()
            isolated = index + 1 < len(lines) and not lines[index + 1].strip()
            valid_number = not number_key.isdigit() or int(number_key) <= 20
            if (valid_number and isolated and body[:1].isupper() and len(body.split()) <= 18
                    and not re.search(r"[.!?;,]", body)
                    and not re.fullmatch(r"[IVXLCDM\s]+", body)
                    and not _NON_TITLE_START.match(body)
                    and not re.match(r"(?:algorithm\s+\d|fig(?:ure)?|table|input|output|generate|evaluate|construct|return|while|for|if|how|do)\b", body, re.I)):
                parents[number_key] = parent_module
                current = parent_module
        if current:
            buckets[current].append(line.rstrip())
    result = {
        module: "\n".join(lines).strip()
        for module, lines in buckets.items()
        if module in MODULES and len("".join(lines).strip()) >= 120
    }
    if "abstract" not in result and introduction_line is not None:
        inferred = _infer_preamble_abstract(lines[:introduction_line])
        if len(inferred) >= 300:
            result["abstract"] = inferred
    return result


def _join_detached_heading_numbers(lines: list[str]) -> list[str]:
    """Recover numbers separated from heading titles by PDF reading order."""
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(rf"\s*{_NUMBERING}\s*", line):
            following = index + 1
            while following < min(len(lines), index + 9):
                value = lines[following].strip()
                if not value or (value.isdigit() and int(value) > 20):
                    following += 1
                else:
                    break
            if following < len(lines):
                title_end = following
                title = lines[following].strip()
                if (following + 2 < len(lines) and lines[following + 1].strip()
                        and not lines[following + 2].strip()
                        and len(title + lines[following + 1]) < 120):
                    title += " " + lines[following + 1].strip()
                    title_end += 1
                candidate = f"{line.strip()} {title}"
                known_title = normalize_heading(title)
                exact_alias = any(
                    _alias_title(known_title, alias)
                    for alias in _EXACT_TITLES
                )
                if re.match(r"algorithm\s+\d+", title, re.I):
                    result.append(line)
                    index += 1
                    continue
                isolated_title = title_end + 1 < len(lines) and not lines[title_end + 1].strip()
                descriptive_title = (
                    isolated_title and title[:1].isupper()
                    and len(title.split()) <= 18
                    and not re.search(r"[.!?;]$", title)
                )
                if looks_like_heading(candidate) and (
                    line.strip().endswith((".", ")")) or exact_alias or descriptive_title
                ):
                    result.append(candidate)
                    index = title_end + 1
                    continue
        result.append(line)
        index += 1
    return result


def _without_line_number_runs(lines: list[str]) -> list[str]:
    """Exclude manuscript margin numbers while retaining the original text cache.

    Isolated ascending runs occur between a detached heading number and its
    title. Require four consecutive values; single page/equation numbers and
    numbered algorithm instructions remain untouched.
    """
    removed: set[int] = set()
    run: list[tuple[int, int]] = []
    for index, line in enumerate([*lines, "end"]):
        value = line.strip()
        if not value:
            continue
        if re.fullmatch(r"\d{1,4}", value):
            number = int(value)
            if run and number != run[-1][1] + 1:
                if len(run) >= 4:
                    removed.update(position for position, _ in run)
                run = []
            run.append((index, number))
        else:
            if len(run) >= 4:
                removed.update(position for position, _ in run)
            run = []
    result: list[str] = []
    for index, line in enumerate(lines):
        if index in removed:
            continue
        if re.match(r"^\s*\d{2,4}\s+(?:\d{1,2}(?:\.\d+)*)\s+[A-Z]", line):
            candidate = re.sub(r"^\s*\d{2,4}\s+", "", line)
            if looks_like_heading(candidate):
                line = candidate
        if line.strip() or not result or result[-1].strip():
            result.append(line)
    return result


def _infer_preamble_abstract(lines: list[str]) -> str:
    """Recover an unlabeled abstract from the front matter of journal PDFs."""
    metadata = re.compile(
        r"journal homepage|available online|article history|article info|keywords?|received|accepted|copyright|doi:|e-mail|corresponding author",
        re.I,
    )
    candidates: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        parts = [part.strip() for part in re.split(r"\s{4,}", stripped) if part.strip()]
        if parts and metadata.search(parts[0]) and len(parts) > 1:
            stripped = " ".join(parts[1:])
        elif metadata.search(stripped):
            continue
        if len(stripped) < 45:
            continue
        if len(re.findall(r"[A-Za-z\u3400-\u9fff]", stripped)) < 35:
            continue
        candidates.append(stripped)
    return "\n".join(candidates[-30:])[:8000].strip()


def academic_heading_count(text: str) -> int:
    found = set()
    for line in text.splitlines():
        module = looks_like_heading(line)
        if module and module != "__stop__":
            found.add(module)
    return len(found)


def prose_density(text: str) -> float:
    """Estimate how much extracted text resembles prose rather than labels or tables."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    total_characters = sum(len(line) for line in lines)
    if not total_characters:
        return 0.0
    prose_characters = 0
    for line in lines:
        word_count = len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", line))
        cjk_count = len(re.findall(r"[\u3400-\u9fff]", line))
        language_characters = len(re.findall(r"[A-Za-z\u3400-\u9fff]", line))
        language_ratio = language_characters / max(len(line), 1)
        if language_ratio >= 0.5 and (word_count >= 8 or cjk_count >= 24):
            prose_characters += len(line)
    return round(prose_characters / total_characters, 4)


def split_sentences(text: str) -> list[str]:
    """Keep decimal results and common scientific abbreviations inside sentences."""
    marker = "\ue000"
    protected = re.sub(r"(?<=\d)\.(?=\d)", marker, text)
    protected = re.sub(
        r"\b(?:e\.g|i\.e|et al|figs?|eqs?|sec|sect|nos?|dr|prof|vs|cf)\.",
        lambda match: match.group(0).replace(".", marker), protected, flags=re.I,
    )
    return [
        sentence.strip().replace(marker, ".")
        for sentence in _SENTENCE_SPLIT.split(protected) if len(sentence.strip()) >= 5
    ]


def text_statistics(text: str, language: str) -> dict[str, float | int]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) >= 20]
    sentences = split_sentences(text)
    if language == "zh":
        sentence_lengths = [len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", s)) for s in sentences]
    else:
        sentence_lengths = [len(re.findall(r"\b[\w'-]+\b", s)) for s in sentences]
    citation_count = len(_CITATION_RE.findall(text))
    hedges = len(
        re.findall(
            r"\b(?:may|might|could|suggests?|indicates?|approximately|typically)\b|可能|表明|大约|通常",
            text,
            re.I,
        )
    )
    first_person = len(re.findall(r"\b(?:we|our)\b|本文|我们", text, re.I))
    figure_mentions = len(re.findall(r"\bfig(?:ure)?\.?\s*\d+[a-z]?|图\s*\d+[a-z]?", text, re.I))
    table_mentions = len(re.findall(r"\btable\s*\d+[a-z]?|表\s*\d+[a-z]?", text, re.I))
    return {
        "characters": len(text),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "average_sentence_length": round(mean(sentence_lengths), 2) if sentence_lengths else 0.0,
        "citations": citation_count,
        "hedges": hedges,
        "first_person_markers": first_person,
        "figure_mentions": figure_mentions,
        "table_mentions": table_mentions,
    }
