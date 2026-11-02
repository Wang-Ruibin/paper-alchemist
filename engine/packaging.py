"""Create a portable .skill archive from the canonical skill directory."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .installer import find_skill_source
from .skill_validation import validate_skill_bundle


def package_skill(output_dir: Path) -> Path:
    source = find_skill_source()
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "paper-alchemist.skill"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, Path("paper-alchemist") / path.relative_to(source))
    return target


def validate_plugin_bundle(root: Path) -> dict:
    """Check the manifest, in-bundle paths, skill, and offline Python runtime."""
    root = root.resolve()
    errors = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"valid": False, "errors": [f"Invalid Codex manifest: {exc}"], "warnings": []}
    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["Manifest must be an object"], "warnings": []}
    for field in ("name", "version", "description"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            errors.append(f"Missing manifest field: {field}")
    skills_path = manifest.get("skills", "")
    if (not isinstance(skills_path, str) or not skills_path.startswith("./")
            or ".." in Path(skills_path).parts
            or not (root / skills_path).resolve().is_relative_to(root)):
        errors.append("Skills path must start with ./ and remain inside the plugin")
    elif skills_path != "./skills/":
        errors.append("Skills directory must be ./skills/")
    result = validate_skill_bundle(root / "skills" / "paper-alchemist")
    errors.extend(result["errors"])
    for required in ("pyproject.toml", "engine/cli.py", "LICENSE"):
        if not (root / required).is_file():
            errors.append(f"Missing bundled runtime file: {required}")
    return {"valid": not errors, "errors": errors, "warnings": result["warnings"]}


def package_plugin(output_dir: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    result = validate_plugin_bundle(root)
    if not result["valid"]:
        raise ValueError("Invalid plugin: " + "; ".join(result["errors"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "paper-alchemist-plugin.zip"
    paths = [root / name for name in (
        "pyproject.toml", "MANIFEST.in", "LICENSE", "README.md", "README.zh-CN.md",
        ".gitignore", ".gitattributes", ".agents/plugins/marketplace.json",
        "docs/INSTALL.md", "docs/zh-CN/INSTALL.md",
    )]
    paths.append(root / ".codex-plugin" / "plugin.json")
    paths.extend((root / "engine").rglob("*.py"))
    paths.extend(path for path in (root / "skills").rglob("*") if path.is_file())
    paths.extend(path for path in (root / "runtime").glob("*") if path.is_file())
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            if "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(root))
    return target
