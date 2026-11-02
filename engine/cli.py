"""Paper Alchemist command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import __version__
from .additions import extend_profile
from .audit import audit_draft, load_copy_corpus
from .briefs import build_generation_brief, render_brief
from .bundled import select_generation_profile
from .constants import LANGUAGES, MODULES, OUTPUT_FORMATS
from .context import load_context
from .corpus import prepare_evaluation_split
from .extractors import compare_pdf_text
from .installer import AGENTS, install
from .library import list_papers, render_inventory, review_plan, scan_corpus
from .observations import record_observations
from .packaging import package_plugin, package_skill, validate_plugin_bundle
from .portable import export_profile, import_profile
from .profiles import build_profile, integrate_profile, validate_profile
from .skill_validation import validate_skill_bundle
from .terminology import load_registry, terminology_guidance


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="paper-alchemist",
        description="Prepare bilingual academic style profiles for Agent-driven writing.",
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = root.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit-draft", help="Check a draft and its fact-bound semantic review")
    audit.add_argument("draft", type=Path)
    audit.add_argument("--context", type=Path, required=True)
    audit.add_argument("--module", choices=[*MODULES, "section"], default="section")
    audit.add_argument("--terminology-registry", type=Path)
    audit.add_argument("--corpus-prose", type=Path)
    audit.add_argument("--semantic-review", type=Path)
    audit.add_argument("--profile", help="Profile for source-free copying checks; defaults to the selected or included corpus")
    audit.add_argument("--workspace", type=Path, default=Path.cwd())
    audit.add_argument("--out", type=Path)

    copy_candidate = sub.add_parser("prepare-copy-evidence", help="Extract a private PDF copy-screen candidate without changing semantic evidence")
    copy_candidate.add_argument("source", type=Path)
    copy_candidate.add_argument("--font-reviews", type=Path)
    copy_candidate.add_argument("--workspace", type=Path, default=Path.cwd())
    copy_record = sub.add_parser("register-copy-evidence", help="Register an identified review of a clean source-bound decoded copy candidate")
    copy_record.add_argument("--profile", required=True)
    copy_record.add_argument("--source", help="Exact included source path from the inventory")
    copy_record.add_argument("--receipt", type=Path)
    copy_record.add_argument("--batch", type=Path, help="Agent-authored source-and-receipt list; earlier valid registrations survive a later error")
    copy_record.add_argument("--reviewer", required=True)
    copy_record.add_argument("--reviewer-kind", choices=["agent", "human"], default="agent")
    copy_record.add_argument("--review-scope", required=True)
    copy_record.add_argument("--workspace", type=Path, default=Path.cwd())

    distill = sub.add_parser("distill", help="Extract and partition an academic paper corpus")
    distill.add_argument("source", type=Path)
    distill.add_argument("--profile", required=True)
    distill.add_argument("--language", choices=sorted(LANGUAGES))
    distill.add_argument("--workspace", type=Path, default=Path.cwd())
    distill.add_argument("--update", action="store_true")
    distill.add_argument("--extend", action="store_true", help="Distill only added papers while retaining the reviewed base")
    distill.add_argument("--addition-profile", help="Choose an existing added-paper layer, for example when relocating it")
    distill.add_argument("--min-characters", type=int)
    distill.add_argument("--evaluation-split", type=Path)
    distill.add_argument("--section-map", type=Path, help="Source-bound reviewed spans for ambiguous PDF sections")
    distill.add_argument("--pdf-order-map", type=Path, help="Source-hashed reviewed PDF text-order choices; updates preserve saved choices")
    distill.add_argument("--rebind-source", action="store_true", help="Explicitly relocate the tracked folder; this does not merge folders")
    distill.add_argument("--partition", choices=("train", "development", "train-development"))
    distill.add_argument(
        "--ocr",
        choices=("auto", "never", "always"),
        help="OCR policy: auto, never or always; updates preserve the saved policy unless overridden",
    )

    compare = sub.add_parser("compare-pdf-text", help="Compare PDF text orders without distilling or selecting an order")
    compare.add_argument("source", type=Path)
    compare.add_argument("--workspace", type=Path, default=Path.cwd())

    glyphs = sub.add_parser("review-copy-fonts", help="Build a source/font-reviewed copy-text candidate without editing a profile")
    glyphs.add_argument("source", type=Path)
    glyphs.add_argument("--reviews", type=Path, required=True)
    glyphs.add_argument("--workspace", type=Path, default=Path.cwd())

    inventory = sub.add_parser("list-papers", help="Show tracked, reviewed and not-yet-distilled papers")
    inventory.add_argument("--profile")
    inventory.add_argument("--workspace", type=Path, default=Path.cwd())
    inventory.add_argument("--cached", action="store_true", help="Skip live source-folder hashing")
    inventory.add_argument("--json", action="store_true")

    scan = sub.add_parser("scan-corpus", help="Detect added, modified, renamed and removed papers without distilling")
    scan.add_argument("--profile")
    scan.add_argument("--workspace", type=Path, default=Path.cwd())
    scan.add_argument("--source", type=Path, help="Inspect a possible relocated folder without changing the profile")

    plan = sub.add_parser("review-plan", help="List only pending or stale source-section semantic reviews")
    plan.add_argument("--profile")
    plan.add_argument("--workspace", type=Path, default=Path.cwd())
    plan.add_argument("--module", choices=MODULES)
    plan.add_argument("--language", choices=("en", "zh"))
    plan.add_argument("--all", action="store_true", help="Include current completed observations")

    observations = sub.add_parser("record-observations", help="Persist an identified reviewer's source-bound semantic observations")
    observations.add_argument("--profile", required=True)
    observations.add_argument("--workspace", type=Path, default=Path.cwd())
    observations.add_argument("--annotations", type=Path, required=True)
    observations.add_argument("--reviewer", required=True)
    observations.add_argument("--reviewer-kind", choices=("agent", "human"), default="agent")

    integrate = sub.add_parser("integrate", help="Build language and cross-lingual integrations")
    integrate.add_argument("--profile", required=True)
    integrate.add_argument("--workspace", type=Path, default=Path.cwd())

    validate = sub.add_parser(
        "validate-profile", help="Validate profile structure and generation readiness"
    )
    validate.add_argument("--profile")
    validate.add_argument("--workspace", type=Path, default=Path.cwd())

    profile_export = sub.add_parser("export-profile", help="Export reviewed guidance, observations and optional terminology without paper prose")
    profile_export.add_argument("--profile", required=True)
    profile_export.add_argument("--workspace", type=Path, default=Path.cwd())
    profile_export.add_argument("--out", type=Path, required=True)
    profile_export.add_argument("--terminology-registry", type=Path)
    profile_import = sub.add_parser("import-profile", help="Use a reviewed profile archive in this workspace")
    profile_import.add_argument("archive", type=Path)
    profile_import.add_argument("--workspace", type=Path, default=Path.cwd())

    brief = sub.add_parser("brief", help="Prepare a grounded bilingual generation brief")
    brief.add_argument("module", choices=[*MODULES, "section"])
    brief.add_argument("--profile", help="Use an existing profile; a fresh workspace defaults to the included corpus")
    brief.add_argument("--language", choices=["en", "zh"], required=True)
    brief.add_argument("--format", choices=sorted(OUTPUT_FORMATS), default="latex")
    brief.add_argument("--context", type=Path)
    brief.add_argument("--terminology-registry", type=Path)
    brief.add_argument("--section-name")
    brief.add_argument("--workspace", type=Path, default=Path.cwd())
    brief.add_argument("--json", action="store_true")
    brief.add_argument("--out", type=Path)

    installer = sub.add_parser("install", help="Install the Codex skill for local development")
    installer.add_argument("--agent", choices=sorted(AGENTS), default="codex")
    installer.add_argument("--scope", choices=["user", "project"], default="user")
    installer.add_argument("--project-root", type=Path, default=Path.cwd())
    installer.add_argument("--home", type=Path)
    installer.add_argument("--force", action="store_true")
    installer.add_argument("--dry-run", action="store_true")

    package = sub.add_parser("package-skill", help="Build the paper-alchemist.skill archive")
    package.add_argument("--output", type=Path, default=Path("dist"))

    plugin_package = sub.add_parser("package-plugin", help="Package a native Codex plugin")
    plugin_package.add_argument("--output", type=Path, default=Path("dist"))
    plugin_validation = sub.add_parser("validate-plugin", help="Validate the Codex plugin bundle")
    plugin_validation.add_argument("path", nargs="?", type=Path, default=Path.cwd())

    freeze = sub.add_parser("freeze-evaluation", help="Freeze grouped source splits before semantic synthesis")
    freeze.add_argument("--profile", required=True)
    freeze.add_argument("--workspace", type=Path, default=Path.cwd())
    freeze.add_argument("--out", type=Path, required=True)
    freeze.add_argument("--seed", default="paper-alchemist-domain-eval-v1")
    freeze.add_argument("--audited-source", action="append", default=[])

    terms = sub.add_parser("term-brief", help="Resolve domain terms against an evidence-labelled registry")
    terms.add_argument("--registry", type=Path, required=True)
    terms.add_argument("--context", type=Path, required=True)

    skill_validation = sub.add_parser(
        "validate-skill", help="Validate the portable Agent Skill bundle"
    )
    skill_validation.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("skills/paper-alchemist"),
    )
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result: Any
        if args.command == "compare-pdf-text":
            _print_json(compare_pdf_text(args.source, args.workspace))
        elif args.command == "review-copy-fonts":
            from .pdf_font_reviews import save_reviewed_copy_candidate

            _print_json(save_reviewed_copy_candidate(args.source, args.reviews, args.workspace))
        elif args.command == "prepare-copy-evidence":
            from .pdf_font_reviews import save_reviewed_copy_candidate

            _print_json(save_reviewed_copy_candidate(args.source, args.font_reviews, args.workspace))
        elif args.command == "register-copy-evidence":
            from .copy_evidence import register_copy_evidence, register_copy_evidence_batch

            if args.batch:
                if args.source or args.receipt:
                    raise ValueError("Use a batch or one source and receipt, not both")
                result = register_copy_evidence_batch(args.profile, args.workspace, args.batch,
                                                     args.reviewer, args.review_scope, args.reviewer_kind)
            else:
                if not args.source or not args.receipt:
                    raise ValueError("Name the source and its private candidate receipt")
                result = register_copy_evidence(args.profile, args.workspace, args.source, args.receipt,
                                               args.reviewer, args.review_scope, args.reviewer_kind)
            _print_json(result)
        elif args.command == "distill":
            selected = None
            if args.evaluation_split or args.partition:
                if not args.evaluation_split or not args.partition:
                    raise ValueError("Use --evaluation-split and --partition together")
                split = json.loads(args.evaluation_split.read_text(encoding="utf-8"))
                if split.get("status") != "frozen-before-semantic-synthesis":
                    raise ValueError("Evaluation split must be frozen before semantic synthesis")
                partitions = {"train", "development"} if args.partition == "train-development" else {args.partition}
                selected = {item["source"] for item in split["documents"] if item["split"] in partitions}
                frozen = {item["source"]: item["sha256"] for item in split["documents"]}
                from .extractors import file_sha256
                for name in selected:
                    selected_path = (args.source / name).resolve()
                    if not selected_path.is_relative_to(args.source.resolve()) or file_sha256(selected_path) != frozen[name]:
                        raise ValueError(f"Selected source differs from the frozen corpus: {name}")
            if args.extend:
                if selected is not None:
                    raise ValueError("An added-paper layer cannot replace a frozen evaluation partition")
                result = extend_profile(
                    args.profile, args.source, args.workspace, language=args.language,
                    min_characters=args.min_characters, ocr_mode=args.ocr,
                    section_map=args.section_map, pdf_order_map=args.pdf_order_map,
                    addition_profile=args.addition_profile, rebind_source=args.rebind_source,
                )
            else:
                if args.addition_profile:
                    raise ValueError("--addition-profile requires --extend")
                result = build_profile(
                    args.source, args.profile, args.workspace, language=args.language,
                    update=args.update, min_characters=args.min_characters, ocr_mode=args.ocr,
                    include_sources=selected, section_map=args.section_map,
                    rebind_source=args.rebind_source, pdf_order_map=args.pdf_order_map,
                )
            _print_json(result)
        elif args.command == "list-papers":
            result = list_papers(select_generation_profile(args.profile, args.workspace), args.workspace, args.cached)
            if args.json:
                _print_json(result)
            else:
                print(render_inventory(result), end="")
        elif args.command == "scan-corpus":
            _print_json(scan_corpus(select_generation_profile(args.profile, args.workspace), args.workspace, args.source))
        elif args.command == "review-plan":
            _print_json(review_plan(select_generation_profile(args.profile, args.workspace), args.workspace, args.module, args.language, args.all))
        elif args.command == "record-observations":
            _print_json(record_observations(args.workspace, args.profile, args.annotations, args.reviewer, args.reviewer_kind))
        elif args.command == "audit-draft":
            from .copying import load_profile_fingerprints

            copy_index = (None if args.corpus_prose else load_profile_fingerprints(
                select_generation_profile(args.profile, args.workspace), args.workspace))
            result = audit_draft(
                args.draft.read_text(encoding="utf-8"), load_context(args.context), args.module,
                load_registry(args.terminology_registry) if args.terminology_registry else None,
                load_copy_corpus(args.corpus_prose),
                json.loads(args.semantic_review.read_text(encoding="utf-8")) if args.semantic_review else None,
                copy_index=copy_index,
            )
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print_json(result)
            return 0 if result["ready_after_review"] else 2
        elif args.command == "integrate":
            _print_json(integrate_profile(args.profile, args.workspace))
        elif args.command == "validate-profile":
            result = validate_profile(select_generation_profile(args.profile, args.workspace), args.workspace)
            _print_json(result)
            return 0 if result["generation_ready"] else 2
        elif args.command == "export-profile":
            _print_json(export_profile(args.profile, args.workspace, args.out, args.terminology_registry))
        elif args.command == "import-profile":
            _print_json(import_profile(args.archive, args.workspace))
        elif args.command == "brief":
            result = build_generation_brief(
                args.profile,
                args.module,
                args.language,
                args.format,
                args.workspace,
                args.context,
                args.section_name,
                args.terminology_registry,
            )
            rendered = render_brief(result, as_json=args.json)
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(rendered, encoding="utf-8")
                _print_json(
                    {
                        "brief": str(args.out),
                        "missing_context_fields": result["missing_context_fields"],
                    }
                )
            else:
                print(rendered, end="")
        elif args.command == "install":
            result = install(
                args.agent,
                args.scope,
                args.project_root,
                home=args.home,
                force=args.force,
                dry_run=args.dry_run,
            )
            _print_json(asdict(result))
        elif args.command == "package-skill":
            target = package_skill(args.output)
            _print_json({"package": str(target)})
        elif args.command == "package-plugin":
            _print_json({"package": str(package_plugin(args.output))})
        elif args.command == "validate-plugin":
            result = validate_plugin_bundle(args.path)
            _print_json(result)
            return 0 if result["valid"] else 2
        elif args.command == "freeze-evaluation":
            result = prepare_evaluation_split(args.profile, args.workspace, args.out, args.seed, tuple(args.audited_source))
            _print_json({"manifest": str(args.out), "split_counts": result["split_counts"], "split_fingerprint": result["split_fingerprint"], "limitations": result["limitations"]})
        elif args.command == "term-brief":
            _print_json(terminology_guidance(load_context(args.context), load_registry(args.registry)))
        elif args.command == "validate-skill":
            result = validate_skill_bundle(args.path)
            _print_json(result)
            return 0 if result["valid"] else 2
        else:  # pragma: no cover
            raise AssertionError(f"Unhandled command: {args.command}")
        return 0
    except (FileNotFoundError, FileExistsError, ValueError, TimeoutError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
