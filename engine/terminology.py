"""Evidence-labelled terminology routing without guessing acronym meanings."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported terminology registry")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Terminology registry must contain entries")
    identifiers = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Terminology entry must be an object")
        identifier = entry.get("id")
        if not isinstance(identifier, str) or identifier in identifiers:
            raise ValueError("Term identifiers must be unique strings")
        identifiers.add(identifier)
        if not entry.get("definition") or not entry.get("sources"):
            raise ValueError("Every definition needs source provenance")
        aliases = entry.get("aliases")
        if not isinstance(aliases, list) or not aliases or not all(isinstance(value, str) and value for value in aliases):
            raise ValueError("Term aliases must be nonempty strings")
    return data


def _problem_text(context: dict[str, Any]) -> str:
    research = context.get("research") or {}
    value = research.get("problem", "") if isinstance(research, dict) else ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        names = [value.get(key) for key in ("full_name", "name", "title")]
        keys = ("full_name", "name", "title", "variant") if any(_expanded_name(name) for name in names) else (
            "full_name", "name", "title", "description", "variant"
        )
        return " ".join(str(value.get(key, "")) for key in keys)
    return ""


def _expanded_name(value: Any) -> bool:
    return isinstance(value, str) and (
        len(re.findall(r"[A-Za-z]+", value)) >= 2 or len(re.findall(r"[\u3400-\u9fff]", value)) >= 4
    )


def _context_defined_model(context: dict[str, Any]) -> bool:
    """An incomplete registry does not make a fully supplied research model missing."""
    research = context.get("research") or {}
    problem = research.get("problem") if isinstance(research, dict) else None
    if not isinstance(problem, dict):
        return False
    full_name = any(_expanded_name(problem.get(key)) for key in ("full_name", "name", "title"))
    return bool(full_name and all(problem.get(key) for key in ("entities", "decisions", "objective", "constraints")))


def terminology_guidance(context: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    text = _problem_text(context)
    full_matches = []
    full_ranges = {}
    acronym_matches = []
    for entry in registry["entries"]:
        matched_full = []
        ranges = []
        matched_acronyms = []
        for alias in entry["aliases"]:
            acronym = not re.search(r"\s", alias) and len(alias) <= 9 and any(char.isupper() for char in alias)
            expression = re.escape(alias) if acronym else r"[\s\-\u2010-\u2015]+".join(
                re.escape(part) for part in re.split(r"[\s\-\u2010-\u2015]+", alias)
            )
            pattern = r"(?<!\w)" + expression + r"(?!\w)"
            occurrences = list(re.finditer(pattern, text, flags=0 if acronym else re.I))
            if occurrences:
                (matched_acronyms if acronym else matched_full).append(alias)
                if not acronym:
                    ranges.extend(match.span() for match in occurrences)
        if matched_full:
            full_matches.append({**entry, "matched_aliases": matched_full})
            full_ranges[entry["id"]] = ranges
        elif matched_acronyms:
            acronym_matches.append({**entry, "matched_aliases": matched_acronyms})
    # A base name embedded only inside a more specific full name is not a
    # separate model mention. Keep independent mentions and equal-span aliases.
    full_matches = [entry for entry in full_matches if not all(
        any(
            other != entry["id"] and c <= a and b <= d and (c < a or b < d)
            for other, spans in full_ranges.items() for c, d in spans
        )
        for a, b in full_ranges[entry["id"]]
    )]
    matches = full_matches or acronym_matches
    status = (
        "resolved" if len(full_matches) == 1 else
        "needs-expansion" if len(matches) == 1 else
        "ambiguous" if matches else "unclassified"
    )
    if status == "unclassified" and _context_defined_model(context):
        status = "context-defined"
    return {
        "registry_status": registry.get("status", "unspecified"),
        "evidence_partition": registry.get("evidence_partition"),
        "status": status,
        "candidates": matches,
        "clarification_required": status not in {"resolved", "context-defined"},
        "definition_basis": "supplied-research-context" if status == "context-defined" else "registry-candidate",
        "instructions": [
            "Use the verified study model. Corpus definitions are variant-specific checks, not replacement research facts.",
            "Resolve ambiguous acronyms through a full problem name before applying a definition.",
            "Confirm each selected variant's required_context and objective direction; preserve explicit user variants.",
            "Do not report a provisional training registry as a completed all-source terminology resource.",
            "For context-defined models, retain the supplied name, entities, decisions, objective and constraints. No matching corpus definition has been verified; review the model explicitly rather than invent a registry entry.",
        ],
        "global_checks": registry.get("global_checks", []),
    }
