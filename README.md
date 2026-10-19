<div align="center">

# Paper Alchemist

### Distill how great papers write. Draft with evidence, not invention.

A cross-Agent Skill for learning bilingual academic-writing patterns and drafting from verified research facts.

[![CI](https://github.com/Wang-Ruibin/paper-alchemist/actions/workflows/ci.yml/badge.svg)](https://github.com/Wang-Ruibin/paper-alchemist/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Wang-Ruibin/paper-alchemist)](https://github.com/Wang-Ruibin/paper-alchemist/releases)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-6f42c1)](https://agentskills.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English** · [简体中文](README.zh-CN.md)

</div>

## What it can do for you

Paper Alchemist learns how different sections of reference papers organize ideas, develop arguments, and use academic language, then applies those patterns to your own writing.

- Learn separate patterns for abstracts, introductions, related work, problem definitions, methodologies, experiment setups, results analyses, and conclusions.
- Draft or revise one section at a time, or combine the sections into a complete paper draft.
- Learn from English and Chinese papers while keeping the target language natural.
- Use only research facts and citations that you have confirmed, without copying content from reference papers.
- Process papers and research materials locally without calling an additional LLM API.

Reference papers provide experience about how to write. Your drafts, experiment records, and answers provide the facts to write about.

## Supported Agents

Paper Alchemist supports Codex, Claude Code, OpenCode, Hermes, Pi Agent, and Kimi Code. After installation, describe the papers you want to distill or the section you want to draft.

## From installation to writing

The entire workflow can be completed by talking to your Agent. You do not need to learn commands or prepare configuration files by hand.

### 1. Ask your Agent to install it

Send this to Codex, Claude Code, OpenCode, Hermes, Pi Agent, or Kimi Code:

```text
Install Paper Alchemist from https://github.com/Wang-Ruibin/paper-alchemist and
configure it at user scope for the Agent you are currently running as. Check the
environment, finish the installation, and verify that future sessions can use it.
Do not overwrite an existing installation. Ask before installing or upgrading Python,
PDF tools, or OCR components. Tell me whether I must start a new session when done.
```

Replace “user scope” with “project scope” to enable it only in the current research project.

### 2. Ask your Agent to learn from reference papers

Put the reference papers in a folder such as `./papers/`, then say:

```text
Use Paper Alchemist to learn the writing patterns in ./papers and name the profile
routing-literature. Complete the learning and checks for every paper section; do not
stop after merely reading the files. Keep my papers and research materials out of
version control. When finished, tell me whether the profile is ready for writing,
which papers were used, and any limitations.
```

This may take some time. The Agent continues reading papers, analyzing their sections, and synthesizing writing patterns. It pauses only when it needs a decision from you.

### 3. Wait until the profile is ready

When the profile is usable, you receive a clear summary such as:

> **The `routing-literature` profile is ready for writing.** Eighteen papers were used and two could not be read. English evidence for results analysis is limited, so that section will be generated more cautiously.

If the Agent says only that the papers were read or that some sections remain unfinished, reply: “Continue until the profile is ready for writing, then tell me.”

### 4. Start writing your paper

Tell the Agent which part you want to write first and where to find your existing research materials. These can include a draft, research notes, experiment tables, result files, or a BibTeX library.

```text
Use the routing-literature profile to help me write an English related-work section.
My research materials are in ./draft/, experiment results are in ./results/, and
references are in ./references.bib. Read them first and organize the research facts
and citations that can be used. Ask me about missing or unclear details in a few short
rounds. After confirming the information, draft the section without adding unsupported facts.
```

If your materials are not organized yet, say:

```text
Use the routing-literature profile to help me write an English abstract.
My research materials are not organized yet. Ask me a few easy questions at a time
to confirm the research problem, method, contributions, and results, then draft the abstract.
```

The Agent organizes and confirms only the information needed for the current section before drafting.

## Generate one section or a complete draft

Each section uses its matching writing profile. You can finish only the part you need now and return for other sections later.

| What you want to write | What the Agent will confirm |
|---|---|
| Abstract | Research problem, prior gap, method, contributions, and main results |
| Introduction | Background, precise problem, research gap, and contributions |
| Related work | Research gap, literature groups, comparisons, and allowed citations |
| Problem definition | Entities, assumptions, decisions, constraints, and objective |
| Methodology | Purpose, overall approach, components, and design rationale |
| Experiment setup | Datasets or instances, baselines, metrics, parameters, hardware, and seeds |
| Results analysis | Comparisons, exact values, statistical evidence, explanations, and implications |
| Conclusion | Verified findings, contributions, limitations, and supported next steps |

For one section, simply say “draft the abstract first” or “generate only related work.” You can also give the Agent an existing section to revise using the profile.

For a complete paper draft, say:

```text
Use the routing-literature profile and my research materials to create a complete paper draft.
First confirm the facts and citations needed across the paper. Then draft the introduction,
related work, problem definition, methodology, experiment setup, results analysis,
conclusion, and abstract as separate sections. Keep terminology, contribution statements,
numbers, and citations consistent. Combine everything into one LaTeX file at
./draft/paper.tex. Ask me before proceeding whenever research facts are missing.
```

The Agent applies the matching profile to each section before combining them. The abstract is normally drafted last so that it remains consistent with the body.

## Supported materials

Reference papers may be PDF, LaTeX, DOCX, Markdown, or plain text. Ordinary PDFs can be read directly. Scanned or low-text PDFs may require OCR; the Agent asks before installing extra components.

Your research materials do not need a fixed format. Provide file paths or answer questions in chat. Numbers, units, dataset names, baselines, experiment conditions, and citations must come from those materials or your explicit confirmation.

## What you receive

- A reusable profile containing English and Chinese writing patterns for each paper section.
- A concise distillation summary covering included papers, exclusions, and known limitations.
- One section, several sections, or a complete paper draft according to your request.
- Clear requests for missing information when the reference corpus or research facts are insufficient.

## Writing boundaries

- Reference papers teach organization and expression; they are not evidence for your research.
- The profile does not imitate one author or preserve long source passages.
- Paper Alchemist does not invent contributions, methods, datasets, baselines, parameters, results, significance, limitations, or citations.
- Figures and tables may teach how to introduce and analyze visual evidence, but unlabelled values are never guessed from images.
- Generated text is a paper draft that requires author review, not a replacement for academic judgment or factual verification.

## Troubleshooting

| Situation | What to do |
|---|---|
| The Agent cannot read a scanned PDF | Allow OCR installation and retry, or provide a PDF with a text layer |
| A paper was not included | Ask the Agent whether extraction failed or recognizable sections were missing |
| The profile remains unfinished | Ask the Agent to continue unfinished sections and stop only when your action is required |
| The Agent keeps asking for writing facts | Provide draft, result, and bibliography paths, or confirm the missing facts one by one |
| Generated text omits a result | Confirm that result and its exact value, then regenerate the affected section |

## License

MIT © 2026 Wang-Ruibin. See [LICENSE](LICENSE).

---

<div align="center">

If Paper Alchemist helps your research writing, a Star would make this little alchemist smile. ✨

[![Star History Chart](https://api.star-history.com/svg?repos=Wang-Ruibin/paper-alchemist&type=Date)](https://star-history.com/#Wang-Ruibin/paper-alchemist&Date)

</div>
