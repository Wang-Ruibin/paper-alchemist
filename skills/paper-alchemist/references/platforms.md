# Codex installation and invocation

## Install or upgrade

For an explicitly requested installation or upgrade, follow the repository's
[installation guide](../../../docs/INSTALL.md). Prepare the private runtime and
install the requested native marketplace edition. Keep research, selected
profiles and unrelated settings. The private edition includes reviewed guidance;
the public edition requires distillation or import before writing.

## Invoke the installed copy

Find the actual plugin root through Codex. Windows:

```powershell
& <plugin-root>/runtime/run.ps1 --version
```

macOS/Linux:

```bash
sh <plugin-root>/runtime/run.sh --version
```

Replace `paper-alchemist` in reference examples with that launcher, or use the
prepared Python with `skills/paper-alchemist/scripts/run.py`. The plugin's own
engine takes priority over unrelated installed packages. Runtime preparation
belongs to installation; ordinary writing does not download it. PDF/OCR and
LaTeX tools are separate optional tasks.

## Verify readiness

Check the actual version and `validate-plugin`. For included, imported or
user-distilled guidance, run `validate-profile` in the research workspace.
The public edition can be correctly installed while still needing papers.
Start a new conversation to discover the updated skill; do not confuse runtime
checks with refreshed session discovery.
