<div align="center">

# Paper Alchemist

### Turn verified research materials into a professional paper, section by section.

The empty edition provides paper distillation and writing tools without any distilled paper library. Add your own reference papers or import completed guidance before writing.

[![Codex plugin](https://img.shields.io/badge/Codex-native_plugin-blue)](https://developers.openai.com/plugins/build/plugins)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**English** · [简体中文](README.zh-CN.md) · [Get started](#from-installation-to-your-first-paper) · [Installation guide](docs/INSTALL.md)

</div>

## What it can do for you

- Work on the abstract, introduction, related work, problem definition, methodology, experiment setup, results analysis and conclusion separately. Draft one section or assemble a full paper with consistent terminology, notation, numbers and citations.
- Distill section-specific writing guidance from PDF, LaTeX, DOCX, Markdown or text papers, preserving source evidence and the scope of technical definitions.
- Show which papers have been distilled, detect new, modified or renamed papers, and update guidance incrementally.
- Import and export completed guidance for another project or computer without carrying the original papers.
- Check drafts against verified research facts. Keep the manuscript academic and save operational and review records separately.

English writing and Chinese assistance have separate evidence. Guidance helps express and organize research; it does not supply your experimental results or bibliography.

## From installation to your first paper

You need:

- Codex with local plugin and terminal support, plus a project folder for your research materials.
- Internet access for first-time setup. Codex prepares an isolated Python environment; you do not need to install Python, pip or configure PATH yourself.

Copy text labeled “send to Codex” into **Codex's chat input**, not PowerShell. You do not need to edit configuration files yourself.

### 1. Ask Codex to install

Send this to Codex:

```text
Install Paper Alchemist from https://github.com/Wang-Ruibin/paper-alchemist.
Read the repository README and docs/INSTALL.md first. Prepare its isolated runtime
and install it using the native Codex plugin marketplace commands.
Reuse a compatible Python, or prepare a private interpreter if none is available,
without changing system PATH. Preserve my existing configuration and writing materials.
Verify the actual installed plugin and runtime. Tell me whether I need a new
conversation and what I can do next.
```

After installation, start a new Codex conversation and use `$paper-alchemist`. If network access, GitHub permissions or your client version blocks setup, give Codex the full error so it can continue. You do not need to chain installation commands yourself. Downloads happen only during an explicit installation or upgrade.

### 2. Prepare writing guidance

Send this to Codex:

```text
Use $paper-alchemist to help me create writing guidance. Ask where my reference papers
are, check the inventory, and distill, synthesize and integrate their sections.
Show completed and pending papers. Confirm writing readiness only when the required
steps are complete. If I have an exported guidance package, help me import it instead.
```

You are done when Codex confirms that your guidance is ready for writing and explains its actual sources and scope. Extracting text alone is not completed distillation. This edition never brings in a private corpus automatically.

### 3. Write a section or a complete paper

Open your research project in Codex and provide verified method notes, models, result tables and references. Send:

```text
Use $paper-alchemist to write an English paper from the verified research materials
in this project. Check the materials first and ask about missing facts that matter.
Apply the matching guidance to each section separately, write the abstract last,
and reconcile terminology, notation, numbers and citations across the full paper.
Save the manuscript as paper.md and main.tex, with review records in separate files.
Keep only paper content in the manuscript, without an assistant preface, AI notice
or workflow explanation.
```

For one section, say “Write the methodology from these notes; first verify each component's inputs, state changes and outputs.” You can also provide an existing draft for revision.

You are done when the requested section or paper is delivered and its key facts trace to your materials. Exporting a PDF also needs a LaTeX compiler; ask Codex to prepare it separately and check the page layout when needed.

## Add papers or check for changes

Send this to Codex:

```text
Use $paper-alchemist to show the distilled papers and scan the reference folder.
Explain new, modified, renamed or removed papers first. Incrementally distill the
changes I confirm while preserving existing guidance. If my new folder contains
only added papers, attach it as an additional source rather than replacing the library.
```

A scan does not repeat distillation. Added sources contribute to writing after review, synthesis and integration. Changes to original papers require review of guidance that no longer matches.

## Use another project or computer

Install once on a computer, then invoke the plugin in other research projects. To carry your own additions, ask Codex: “Export my complete writing guidance, including added papers, for import on another computer.”

Exports include reviewed writing rules, terminology and source records, without reference-paper prose, current research materials or drafts. Updating original papers later still requires reconnecting their folder.

## Runtime, privacy and scope

- Setup prepares a private runtime; ordinary writing commands do not download one. Windows and WSL use separate environments. No virtual-environment activation is needed.
- The interpreter is downloaded for the current platform, rather than copying a developer's virtual environment into the plugin. An offline computer needs a prepared runtime for the same system and architecture; online setup is not an offline bundle.
- Papers and research materials stay in your project. Local scripts do not call an additional model API; material read by Codex is still processed by the Codex service you use.
- Do not invent methods, data, contributions, significance or references. Copy screening and automated review have limits; verify the research and target journal requirements before submission.

## Troubleshooting

Give Codex the full error and specify Windows, WSL, Linux or macOS. For an unprepared runtime, ask it to follow the [installation guide](docs/INSTALL.md). If the reference folder is unavailable, clarify whether you want to reuse completed guidance or update the original sources.

For an upgrade, say “Update Paper Alchemist, preserve my writing guidance and research files, and verify the updated installation.”

## License

[MIT](LICENSE). Author: Wang-Ruibin. Developer display name: misakimei0331.

---

<div align="center">

If Paper Alchemist helps you express your research, a ⭐ Star would make this little project smile. ✨

[![Star History Chart](https://api.star-history.com/svg?repos=Wang-Ruibin/paper-alchemist&type=Date)](https://star-history.com/#Wang-Ruibin/paper-alchemist&Date)

</div>
