"""Local, read-only checks of registered evidence and revision handoffs.

This validates bindings and recorded judgments, never scientific truth or the
completeness of an Agent's claim extraction. It performs no network requests.
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from .context import citation_keys

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}")
_CITE = re.compile(r"\\cite\w*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}|\[@([^\]]+)\]")
_KINDS = {"study", "literature", "review", "draft"}


def workflow_hashes(text: str, context: dict) -> dict[str, str]:
    """Use the same text and canonical-context hash conventions as audit-draft."""
    return {
        "draft_sha256": sha256(text.encode("utf-8")).hexdigest(),
        "context_sha256": sha256(json.dumps(
            context, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _cited_keys(text: str) -> set[str]:
    keys = set()
    for match in _CITE.finditer(text):
        if match[1]:
            keys.update(key.strip() for key in match[1].split(","))
        else:
            keys.update(re.findall(r"@([A-Za-z0-9_.:+-]+)", "@" + match[2]))
    return keys - {""}


def _context_value(context: dict, path: Any) -> Any:
    if not isinstance(path, str) or path.split(".")[0] not in {"research", "citations"}:
        return None
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def check_workflow(record: Any, text: str, context: dict, workspace: Path,
                   stage: str = "review") -> dict[str, Any]:
    """Validate an Agent-authored record against current files, without writing.

    Artifact paths are relative to the explicit workspace. Quotes use UTF-8
    text with universal newlines; artifact hashes always cover original bytes.
    """
    if stage not in {"review", "final"}:
        raise ValueError("Workflow stage must be review or final")
    root = workspace.resolve()
    hashes = workflow_hashes(text, context)
    issues: list[dict] = []
    artifacts: dict[str, dict] = {}
    artifact_text: dict[str, str] = {}
    claims: dict[str, dict] = {}
    claim_spans: list[tuple[int, int]] = []
    comments: dict[str, dict] = {}
    unresolved_claims: list[str] = []
    unresolved_comments: list[str] = []

    def issue(code: str, message: str, *, pending: bool = False, **details: Any) -> None:
        severity = "warning" if pending and stage == "review" else "error"
        issues.append({"code": code, "severity": severity, "message": message, **details})

    def rows(parent: dict, name: str, *, required: bool = False) -> list[dict]:
        values = parent.get(name, None if required else [])
        if not isinstance(values, list):
            issue("invalid-record", f"{name} must be a list")
            return []
        if any(not isinstance(value, dict) for value in values):
            issue("invalid-record", f"Every {name} entry must be an object")
        return [value for value in values if isinstance(value, dict)]

    def identifier(row: dict, target: dict, kind: str) -> str | None:
        key = row.get("id")
        if not isinstance(key, str) or not _ID.fullmatch(key) or key in target:
            issue("invalid-id", f"{kind} needs a unique nonempty ID", item_id=key)
            return None
        target[key] = row
        return key

    def span(row: dict, content: str, label: str) -> bool:
        start, end, quote = row.get("start"), row.get("end"), row.get("text")
        valid = (type(start) is int and type(end) is int and _present(quote)
                 and 0 <= start < end <= len(content) and content[start:end] == quote)
        if not valid:
            issue("invalid-span", "Offsets must identify the exact current text", item_id=label)
        return valid

    def context_paths(row: dict, label: str) -> bool:
        paths = row.get("context_paths", [])
        if not isinstance(paths, list):
            issue("invalid-context-path", "context_paths must be a list", item_id=label)
            return False
        for path in paths:
            value = _context_value(context, path)
            if value is None or value == "" or value == [] or value == {}:
                issue("invalid-context-path", "Use a populated research or citation fact", item_id=label, path=path)
        return bool(paths)

    def evidence_rows(row: dict, label: str) -> tuple[bool, set[str], bool]:
        supported, citations, adverse = False, set(), False
        for evidence in rows(row, "evidence"):
            ref = evidence.get("artifact_id")
            artifact = artifacts.get(ref) if isinstance(ref, str) else None
            quote = evidence.get("quote")
            relation = evidence.get("relation")
            if (artifact is None or artifact.get("kind") not in ("study", "literature")
                    or not _present(evidence.get("locator")) or not _present(quote)
                    or quote not in artifact_text.get(ref, "") or not _present(evidence.get("rationale"))):
                issue("invalid-evidence", "Evidence needs a checked study/literature artifact, locator, exact quote and rationale", item_id=label)
            if not isinstance(relation, str) or relation not in {"supports", "contradicts", "insufficient"}:
                issue("invalid-evidence", "Declare supports, contradicts or insufficient", item_id=label)
            supported |= relation == "supports"
            adverse |= isinstance(relation, str) and relation in {"contradicts", "insufficient"}
            key = evidence.get("citation_key")
            if key is not None:
                if (not isinstance(key, str) or key not in authorized
                        or artifact is None or artifact.get("kind") != "literature"):
                    issue("invalid-citation-evidence", "Citation evidence needs an authorized key and literature artifact", item_id=label)
                elif relation == "supports":
                    citations.add(key)
        return supported, citations, adverse

    if not isinstance(record, dict):
        issue("invalid-record", "The workflow record must be an object")
        record = {}
    if type(record.get("schema_version")) is not int or record.get("schema_version") != 1:
        issue("invalid-record", "Use workflow record schema_version 1")
    for name, digest in hashes.items():
        if record.get(name) != digest:
            issue("stale-binding", f"{name} differs from the current draft or context")
    if not text.strip():
        issue("empty-draft", "The draft is empty")
    authorized = set(citation_keys(context))

    for row in rows(record, "artifacts", required=True):
        key = identifier(row, artifacts, "Artifact")
        if key is None:
            continue
        name = row.get("path")
        kind = row.get("kind")
        if not isinstance(kind, str) or kind not in _KINDS:
            issue("invalid-artifact", "Artifact kind must be study, literature, review or draft", item_id=key)
        if not _present(name):
            issue("invalid-artifact", "Artifact needs a workspace-relative file path", item_id=key)
            continue
        path = (root / name).resolve()
        if Path(name).is_absolute() or not path.is_relative_to(root):
            issue("artifact-outside-workspace", "Artifact path must stay inside the workspace", item_id=key)
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            issue("missing-artifact", "Artifact file is unavailable", item_id=key)
            continue
        actual = sha256(raw).hexdigest()
        if row.get("sha256") != actual:
            issue("stale-artifact", "Artifact bytes changed; review affected evidence again", item_id=key, actual_sha256=actual)
        try:
            artifact_text[key] = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            issue("non-text-artifact", "Use inspected UTF-8 text; keep PDF page provenance in its locator", item_id=key)

    for row in rows(record, "claims", required=True):
        key = identifier(row, claims, "Claim")
        if key is None:
            continue
        if span(row, text, key):
            claim_spans.append((row["start"], row["end"]))
        assessment = row.get("assessment")
        has_context = context_paths(row, key)
        has_evidence, cited, adverse = evidence_rows(row, key)
        if not has_context and not has_evidence:
            issue("unbound-claim", "A registered claim needs context facts or supporting evidence",
                  pending=assessment == "unresolved", item_id=key)
        claimed = row.get("text") if isinstance(row.get("text"), str) else ""
        for citation in _cited_keys(claimed) - cited:
            issue("untraced-citation", "Cited clauses need inspected source evidence with the same key",
                  pending=assessment == "unresolved" and citation in authorized, item_id=key, citation_key=citation)
        if not isinstance(assessment, str) or assessment not in {"supported", "unresolved"} or not _present(row.get("rationale")):
            issue("invalid-assessment", "Record supported or unresolved with a substantive reason", item_id=key)
        if assessment == "unresolved" or adverse:
            unresolved_claims.append(key)
            issue("unresolved-claim", "Resolve contrary or insufficient evidence before final handoff", pending=True, item_id=key)
    if not claims:
        issue("missing-claims", "Register the factual and cited claims being handed off")
    for match in _CITE.finditer(text):
        if not any(start <= match.start() and match.end() <= end for start, end in claim_spans):
            issue("unregistered-citation", "This citation occurrence has no registered draft span", offset=match.start())

    review_ids: dict[str, dict] = {}
    for row in rows(record, "reviews"):
        key = identifier(row, review_ids, "Review")
        if key is None:
            continue
        ref, target = row.get("artifact_id"), row.get("draft_artifact_id")
        report = artifacts.get(ref) if isinstance(ref, str) else None
        draft = artifacts.get(target) if isinstance(target, str) else None
        if report is None or report.get("kind") != "review" or draft is None or draft.get("kind") != "draft":
            issue("invalid-review", "A review needs its report and the preserved draft it reviewed", item_id=key)
        if (not _present(row.get("reviewer")) or not isinstance(row.get("reviewer_kind"), str)
                or row.get("reviewer_kind") not in {"agent", "human"}):
            issue("invalid-review", "Identify the actual reviewer and distinguish Agent from human review", item_id=key)
        for comment in rows(row, "comments", required=True):
            comment_id = identifier(comment, comments, "Review comment")
            if comment_id is None:
                continue
            quote = comment.get("text")
            report_text = artifact_text.get(ref, "") if isinstance(ref, str) else ""
            if not _present(quote) or quote not in report_text:
                issue("invalid-review-comment", "Keep each comment's exact text in its original report", item_id=comment_id)
            if not isinstance(comment.get("severity"), str) or comment.get("severity") not in {"major", "minor"}:
                issue("invalid-review-comment", "Distinguish major and minor findings", item_id=comment_id)

    resolved: set[str] = set()
    seen: set[str] = set()
    for row in rows(record, "resolutions"):
        key = row.get("comment_id")
        if not isinstance(key, str) or key not in comments or key in seen:
            issue("invalid-resolution", "Resolve each known comment at most once", item_id=key)
            continue
        seen.add(key)
        action = row.get("action")
        if not isinstance(action, str) or action not in {"revised", "rebutted", "deferred"} or not _present(row.get("rationale")):
            issue("invalid-resolution", "Record revised, rebutted or deferred and explain the decision", item_id=key)
            continue
        if action == "deferred":
            continue
        resolution_start = len(issues)
        if (any(row.get(name) != digest for name, digest in hashes.items())
                or not _present(row.get("verified_by"))
                or not isinstance(row.get("verifier_kind"), str) or row.get("verifier_kind") not in {"agent", "human"}):
            issue("stale-resolution", "Recheck the resolution against the current draft and context with an identified verifier", item_id=key)
        if action == "revised":
            span(row, text, key)
        else:
            has_context = context_paths(row, key)
            supported, _, adverse = evidence_rows(row, key)
            if (not has_context and not supported) or adverse:
                issue("unsupported-rebuttal", "A rebuttal needs current facts or supporting evidence", item_id=key)
        if not any(item["severity"] == "error" for item in issues[resolution_start:]):
            resolved.add(key)
    unresolved_comments = sorted(set(comments) - resolved)
    for key in unresolved_comments:
        issue("unresolved-comment", "This comment is open or deferred", pending=True, item_id=key)

    return {
        "schema_version": 1, **hashes, "stage": stage,
        "traceability_ready": not any(row["severity"] == "error" for row in issues),
        "registered_claims": len(claims), "registered_artifacts": len(artifacts),
        "registered_reviews": len(review_ids), "registered_comments": len(comments),
        "unresolved_claim_ids": sorted(unresolved_claims),
        "unresolved_comment_ids": unresolved_comments, "issues": issues,
        "scope": "Registered evidence and revision bindings only; manuscript acceptance is not assessed.",
        "limitations": [
            "Exact quotes and file hashes do not prove entailment, source authenticity or experiment execution.",
            "Claim and comment extraction completeness requires a separate full semantic review.",
            "Reviewer and verifier identities are recorded assertions, not authenticated independent reviewers.",
            "Run audit-draft with a current semantic review and inspect the rendered deliverable before finalizing.",
        ],
    }
