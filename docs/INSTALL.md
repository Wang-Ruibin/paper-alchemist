# Install Paper Alchemist

This guide is for Codex carrying out a user's installation or upgrade request.
Preserve research files, profile choices and unrelated Codex settings.

## Check access and select the edition

Read the repository README and `.agents/plugins/marketplace.json`. The private
`paper-alchemist-private` marketplace includes reviewed guidance; the public
`paper-alchemist` marketplace is empty. Do not substitute one for the other.
Private users must accept their invitation and have working GitHub access.
Reuse authentication; never request tokens in chat. If access is missing,
explain the exact login step.

Check `codex plugin --help`. If commands are missing, help update a supported
Codex client before claiming success. Use a persistent checkout for setup.
A checkout registered as a local marketplace is not a disposable test folder.

## Prepare the private runtime

From the repository root, on Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/setup.ps1
```

On macOS, Linux with glibc, or WSL:

```bash
sh runtime/setup.sh
```

The scripts download pinned uv 0.13.6 from its official GitHub release and
verify recorded SHA256 and size before execution. They reuse Python 3.11–3.14
when available, or prepare private Python 3.12. Pinned dependencies in
`runtime/requirements.txt` install as wheels in an isolated environment. The
plugin's own CLI is checked. No administrator, system Python, shell profile
or system PATH change is required.

Defaults: `%LOCALAPPDATA%/PaperAlchemist/runtime` on Windows;
`${XDG_CACHE_HOME:-~/.cache}/paper-alchemist/runtime` on macOS/Linux. The optional
`PAPER_ALCHEMIST_RUNTIME` overrides this with an absolute directory; preserve
the user's choice in their execution environment. Windows and WSL use separate
runtimes. Setup writes the interpreter location to `runtime.json`; launchers
select the environment using the dependency-file hash. Repeating setup is
supported. Inspect exact paths and running processes before repairing a lock
or an incomplete environment left by interrupted setup.

Only Windows x86-64 and Linux x86-64 have local verification for this release.
The download inventory also covers Windows ARM64, macOS/Linux ARM64 and macOS
x86-64; those combinations still need platform verification. Missing wheels or
unsupported systems are setup failures, not permission to compile or install
system packages silently. PDF/OCR and LaTeX tools are separate optional tasks.
Initial downloads need internet. This is not a complete offline runtime bundle.
Ordinary writing commands never download a runtime.

## Install the native plugin

Private edition:

```bash
codex plugin marketplace add git@github.com:Wang-Ruibin/paper-alchemist-private.git
codex plugin add paper-alchemist@paper-alchemist-private
```

Public empty edition:

```bash
codex plugin marketplace add https://github.com/Wang-Ruibin/paper-alchemist.git
codex plugin add paper-alchemist@paper-alchemist
```

Install only the requested edition. Do not enable both as competing versions
of the same skill. Read the actual installed path from Codex rather than
guessing a cache directory. If a desktop client requires a final plugin-browser
action, guide the user and distinguish that pending step from a completed CLI
installation.

## Verify the installed copy

Check Codex's plugin list, then invoke the installed copy. Windows:

```powershell
& <installed-plugin-root>/runtime/run.ps1 --version
& <installed-plugin-root>/runtime/run.ps1 validate-plugin <installed-plugin-root>
```

macOS/Linux:

```bash
sh <installed-plugin-root>/runtime/run.sh --version
sh <installed-plugin-root>/runtime/run.sh validate-plugin <installed-plugin-root>
```

For the private edition, also run `validate-profile --workspace <temporary-folder>`
with that launcher. Confirm readiness and the source count from the manifest;
original PDFs are unnecessary. For the public edition, confirm the absence of
`skills/paper-alchemist/assets/corpus/` and explain that distillation or import
is needed before writing. Do not create a fake completed profile. Keep checks
outside research/plugin state and remove the exact temporary folder afterwards.

Explain the edition, runtime readiness and any remaining step in plain language.
Start a new conversation to discover `$paper-alchemist`; do not claim the current
session refreshed without checking. For upgrades, refresh the selected
marketplace and replace only this plugin using supported commands. Preserve
the user's profiles and guidance.

Sources: [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins),
[uv installation](https://docs.astral.sh/uv/getting-started/installation/),
[Python environment portability](https://docs.python.org/3/library/venv.html).
