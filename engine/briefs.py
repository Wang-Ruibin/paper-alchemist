"""Generation-brief construction for an Agent, without making an LLM call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .bundled import select_generation_profile
from .constants import MODULES, OUTPUT_FORMATS
from .context import citation_keys, load_context, missing_context_fields
from .profiles import bilingual_blend, state_root, validate_profile
from .terminology import load_registry, terminology_guidance


def build_generation_brief(
    profile: str | None,
    module: str,
    language: str,
    output_format: str,
    workspace: Path,
    context_path: Path | None = None,
    section_name: str | None = None,
    terminology_registry: Path | None = None,
) -> dict[str, Any]:
    if module not in {*MODULES, "section"}:
        raise ValueError(f"Unknown module: {module}")
    if language not in {"en", "zh"}:
        raise ValueError("Generation language must be en or zh")
    if output_format not in OUTPUT_FORMATS:
        raise ValueError("Output format must be latex or markdown")
    if module == "section" and not section_name:
        raise ValueError("Custom section generation requires --section-name")

    slug = select_generation_profile(profile, workspace)
    profile = slug
    profile_dir = state_root(workspace) / "profiles" / slug
    if not profile_dir.exists():
        raise FileNotFoundError(f"Profile does not exist: {profile_dir}")
    secondary = "zh" if language == "en" else "en"
    target_module = module if module != "section" else "methodology"
    target_path = profile_dir / language / "modules" / f"{target_module}.md"
    secondary_path = profile_dir / secondary / "modules" / f"{target_module}.md"
    required_profiles = {
        f"{language}/{target_module}": target_path,
        f"{secondary}/{target_module}": secondary_path,
    }
    incomplete = [
        label for label, path in required_profiles.items() if _synthesis_status(path) != "complete"
    ]
    if incomplete:
        raise ValueError(
            "Generation requires completed semantic module profiles. Incomplete: "
            + ", ".join(incomplete)
        )
    integration_paths = (
        profile_dir / language / "integrated.md",
        profile_dir / "bilingual" / "cross-lingual.md",
        profile_dir / "bilingual" / "conflicts.md",
    )
    missing_integration = [str(path) for path in integration_paths if not path.is_file()]
    if missing_integration:
        raise ValueError(
            "Generation requires an integrated profile. Run `paper-alchemist integrate` "
            "after semantic synthesis. Missing: " + ", ".join(missing_integration)
        )
    validation = validate_profile(profile, workspace)
    if not validation["generation_ready"]:
        raise ValueError("Generation requires current, complete semantic evidence, including source observations")
    target_count = _source_count(target_path)
    secondary_count = _source_count(secondary_path)
    blend = bilingual_blend(target_count, secondary_count)
    context = load_context(context_path)
    missing = missing_context_fields(context, module)
    explicit_registry = terminology_registry is not None
    if terminology_registry is None and (profile_dir / "terminology.json").is_file():
        terminology_registry = profile_dir / "terminology.json"
    terms = terminology_guidance(context, load_registry(terminology_registry)) if terminology_registry else None
    if terms and terms["clarification_required"]:
        missing.append("research.problem.full_name_or_variant")
    result = {
        "schema_version": 1,
        "task": "draft-academic-section",
        "profile": slug,
        "module": module,
        "section_name": section_name,
        "target_language": language,
        "output_format": output_format,
        "bilingual_blend": {
            "target_language": language,
            "secondary_language": secondary,
            **blend,
        },
        "profile_files": {
            "target_module": str(target_path),
            "secondary_module": str(secondary_path),
            "target_integrated": str(profile_dir / language / "integrated.md"),
            "cross_lingual": str(profile_dir / "bilingual" / "cross-lingual.md"),
            "conflicts": str(profile_dir / "bilingual" / "conflicts.md"),
        },
        "source_counts": {language: target_count, secondary: secondary_count},
        "context": context,
        "missing_context_fields": missing,
        "allowed_citation_keys": citation_keys(context),
        "terminology": terms,
        "terminology_registry": str(terminology_registry) if terminology_registry else None,
        "profile_evidence_mode": validation["evidence_mode"],
        "manuscript_contract": {
            "form": "submission-manuscript",
            "content_only": True,
            "operational_records": "separate-from-manuscript",
            "authoring_gaps_are_scientific_limitations": False,
            "exclude": ["assistant-preface", "AI-notice", "generation-explanation",
                        "task-framing", "writing-reminders", "review-checklist", "unresolved-placeholders"],
            "retain": ["research-argument", "verified-assumptions", "scientific-limitations",
                       "equations", "figures-and-tables", "references"],
        },
        "instructions": [
            "Use only evidenced profile languages. Zero-source guidance is assistance, not observed corpus style.",
            "Ask interactively for every missing_context_fields item before drafting.",
            "Use target-language wording and grammar; transfer only rhetorical functions from the secondary language.",
            "Do not invent claims, contributions, numerical results, significance, limitations, or citations.",
            "Use only allowed_citation_keys.",
            "Bind each cited clause to the reference's supplied support; separate configured benchmark facts from claims about the publication.",
            "Return submission-form manuscript content directly, without AI notices, assistant explanations, task framing or writing reminders. Keep review/provenance outside the article.",
            "State scientific assumptions, methods, findings and relevant limitations directly; resolve required missing facts before drafting instead of inserting placeholders.",
            "Keep unattached writing materials and unperformed author checks outside research facts and manuscript content; their absence does not establish that the study performed no test or audit.",
            "Describe each component's input and resulting state. Resolve material ambiguity between restarting construction and refilling a residual solution before drafting.",
            "Confirm an ambiguous problem's full name, entities, objective and defining constraints; expand a confirmed acronym at first use. Preserve metric aggregation, denominator and percent versus percentage-point units in summaries.",
            "Ask for actual statistical evidence before asserting significance. Explain an unexecuted budget or run-policy change and obtain matching results before reporting it as performed; keep clarification outside the article.",
            "Return in chat unless the user explicitly supplied an output path.",
        ],
    }
    from .additions import compose_brief

    return compose_brief(slug, workspace, result, explicit_registry=explicit_registry)


def render_brief(brief: dict[str, Any], as_json: bool = False) -> str:
    if as_json:
        import json

        return json.dumps(brief, ensure_ascii=False, indent=2) + "\n"
    return yaml.safe_dump(brief, sort_keys=False, allow_unicode=True)


def _source_count(path: Path) -> int:
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8", errors="replace")
    if not content.startswith("---"):
        return 0
    parts = content.split("---", 2)
    if len(parts) < 3:
        return 0
    metadata = yaml.safe_load(parts[1]) or {}
    try:
        return int(metadata.get("source_count", 0))
    except (TypeError, ValueError):
        return 0


def _synthesis_status(path: Path) -> str | None:
    if not path.is_file():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    metadata = yaml.safe_load(parts[1]) or {}
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("synthesis_status")
    return str(value) if value is not None else None
