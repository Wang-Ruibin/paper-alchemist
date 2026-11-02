"""Reproducible corpus grouping and immutable evaluation splits."""

from __future__ import annotations

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from .extractors import file_sha256
from .profiles import profile_slug, state_root


def grouped_split(
    group_ids: list[str], seed: str, development_groups: set[str] | None = None
) -> dict[str, str]:
    """Split whole document groups; audited development material never enters test."""
    unique = set(group_ids)
    development = set(development_groups or ())
    if not development <= unique:
        raise ValueError("Development groups must belong to this corpus")
    if len(unique) < 5:
        raise ValueError("At least five independent document groups are required")
    train_count = int(len(unique) * 0.6)
    test_count = max(1, int(len(unique) * 0.2))
    if len(development) > len(unique) - train_count - test_count:
        raise ValueError("Too much material already reviewed; reserve a new test population")
    ranked = sorted(unique - development, key=lambda value: sha256(f"{seed}:{value}".encode()).hexdigest())
    result = {value: "development" for value in development}
    for index, value in enumerate(ranked):
        result[value] = (
            "train" if index < train_count else
            "test" if index >= len(ranked) - test_count else "development"
        )
    return result


def _shingles(text: str) -> set[str]:
    tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)*", text.casefold())
    return {
        sha256(" ".join(tokens[index:index + 8]).encode()).hexdigest()[:16]
        for index in range(max(0, len(tokens) - 7))
    }


def prepare_evaluation_split(
    profile: str,
    workspace: Path,
    output: Path,
    seed: str = "paper-alchemist-domain-eval-v1",
    audited_sources: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Bind an immutable split to exact PDFs and the current extraction cache.

    This is mechanical preparation, not semantic distillation or an evaluation.
    Borderline overlapping papers require review before a split can be frozen.
    """
    from pypdf import PdfReader

    slug = profile_slug(profile)
    root = state_root(workspace)
    manifest = json.loads((root / "profiles" / slug / "source-manifest.json").read_text(encoding="utf-8"))
    source_documents = manifest["documents"]
    labels = {item["relative_path"] for item in source_documents}
    if not set(audited_sources) <= labels:
        raise ValueError("Every audited source must exist in this corpus")
    entries = []
    fingerprints: dict[str, set[str]] = {}
    parents: dict[str, str] = {}
    for item in source_documents:
        path = Path(item["path"])
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            raise ValueError(f"Source changed since extraction: {item['relative_path']}")
        identifier = item["id"]
        parents[identifier] = identifier
        text_path = root / "cache" / slug / "documents" / identifier / "full.txt"
        text = text_path.read_text(encoding="utf-8")
        metadata = {}
        pages = None
        if path.suffix.casefold() == ".pdf":
            reader = PdfReader(path)
            metadata = reader.metadata or {}
            pages = len(reader.pages)
        raw_title = str(metadata.get("/Title") or "").strip()
        title = raw_title if 10 <= len(raw_title) <= 500 else None
        fingerprints[identifier] = _shingles(text) if item["included"] else set()
        entries.append({
            "id": identifier,
            "source": item["relative_path"],
            "sha256": item["sha256"],
            "text_sha256": sha256(text.encode()).hexdigest(),
            "metadata_title": title,
            "title_status": "metadata-unreviewed" if title else "needs-title-review",
            "pages": pages,
            "filename_year": (re.findall(r"(?:19|20)\d{2}", path.stem) or [None])[-1],
            "language": item["language"],
            "included": item["included"],
            "exclusion_reason": None if item["included"] else item["reason"],
            "recognized_modules": item["recognized_modules"],
            "backend": item["backend"],
            "warnings": item["warnings"],
            "topic_family": None,
            "semantic_review": "pending",
        })

    def find(identifier: str) -> str:
        while parents[identifier] != identifier:
            identifier = parents[identifier]
        return identifier

    def unite(left: str, right: str) -> None:
        parent = min(find(left), find(right))
        parents[find(left)] = parent
        parents[find(right)] = parent

    candidates = []
    grouped_pairs = []
    for index, left in enumerate(entries):
        for right in entries[index + 1:]:
            if left["sha256"] == right["sha256"] or left["text_sha256"] == right["text_sha256"]:
                unite(left["id"], right["id"])
                grouped_pairs.append({"left": left["id"], "right": right["id"], "reason": "exact-duplicate"})
                continue
            first, second = fingerprints[left["id"]], fingerprints[right["id"]]
            if min(len(first), len(second)) < 300:
                continue
            overlap = len(first & second) / len(first | second)
            if overlap >= 0.85:
                unite(left["id"], right["id"])
                grouped_pairs.append({"left": left["id"], "right": right["id"], "reason": "near-duplicate", "shingle_jaccard": round(overlap, 4)})
            elif overlap >= 0.6:
                candidates.append({"left": left["id"], "right": right["id"], "shingle_jaccard": round(overlap, 4)})
    if candidates:
        raise ValueError("Review potentially overlapping paper versions before freezing: " + json.dumps(candidates))
    for entry in entries:
        entry["group"] = find(entry["id"])
    included = [entry for entry in entries if entry["included"]]
    development = {entry["group"] for entry in included if entry["source"] in audited_sources}
    splits = grouped_split([entry["group"] for entry in included], seed, development)
    for entry in entries:
        entry["split"] = splits[entry["group"]] if entry["included"] else "excluded"
    identity = {
        "seed": seed,
        "audited_sources": sorted(audited_sources),
        "sources": sorted((entry["source"], entry["sha256"], entry["text_sha256"], entry["group"], entry["split"]) for entry in entries),
    }
    fingerprint = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    result = {
        "schema_version": 1,
        "status": "frozen-before-semantic-synthesis",
        "profile": slug,
        "seed": seed,
        "split_fingerprint": fingerprint,
        "grouping_method": "PDF/text exact hashes and 8-word shingle Jaccard >= 0.85; 0.6-0.85 requires review",
        "audited_sources": sorted(audited_sources),
        "split_counts": dict(Counter(entry["split"] for entry in entries)),
        "grouped_pairs": grouped_pairs,
        "documents": entries,
        "limitations": [
            "Filename years are labels, not verified publication dates.",
            "PDF metadata titles and topic families require semantic review.",
            "The split does not control exposure in a foundation model's pretraining.",
            "Extraction and a frozen split do not prove writing quality or completed distillation.",
        ],
    }
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        if previous.get("split_fingerprint") != fingerprint:
            raise ValueError("A frozen evaluation split cannot be overwritten with changed evidence")
        return previous
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
