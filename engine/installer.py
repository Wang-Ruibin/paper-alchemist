"""Install the Codex skill for local development; native plugins use a marketplace."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

AGENTS = {"codex"}


@dataclass(slots=True)
class InstallResult:
    agent: str
    scope: str
    installed: list[str]
    notes: list[str]
    dry_run: bool


def find_skill_source() -> Path:
    override = os.environ.get("PAPER_ALCHEMIST_SKILL_SOURCE")
    if override:
        candidates = [Path(override).expanduser().resolve()]
    else:
        candidates = [
            Path(__file__).resolve().parents[1] / "skills" / "paper-alchemist",
            Path(sys.prefix) / "share" / "paper-alchemist" / "skills" / "paper-alchemist",
        ]
    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise FileNotFoundError(
        "Cannot find the Codex skill resources. Reinstall Paper Alchemist or set "
        "PAPER_ALCHEMIST_SKILL_SOURCE to the packaged skill directory."
    )


def install(
    agent: str,
    scope: str,
    project_root: Path,
    home: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    if agent != "codex":
        raise ValueError("Paper Alchemist supports Codex only")
    if scope not in {"user", "project"}:
        raise ValueError("scope must be user or project")
    home = (home or Path.home()).expanduser().resolve()
    project_root = project_root.expanduser().resolve()
    source = find_skill_source()
    scope_root = home if scope == "user" else project_root
    target = scope_root / ".agents" / "skills" / "paper-alchemist"
    if target.is_symlink():
        raise ValueError("Refusing to replace a symlinked skill destination")
    if not target.resolve().is_relative_to(scope_root):
        raise ValueError("Skill destination escapes the selected installation scope")
    if target.exists() and not force:
        raise FileExistsError(f"Install target already exists: {target}. Pass --force to replace it.")
    if not dry_run:
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
    return InstallResult(
        agent="codex",
        scope=scope,
        installed=[str(target)],
        notes=[
            "Codex development skill installed; invoke $paper-alchemist.",
            "For the native plugin, install the repository marketplace entry in Codex.",
        ],
        dry_run=dry_run,
    )
