---
name: paper-alchemist
description: Plan academic research, organize source-grounded literature, draft papers with corpus-specific writing guidance, review manuscripts, and trace revisions to reviewer comments. Use for research planning, literature evidence checks, corpus distillation, individual sections, full papers, or review and revision workflows; preserve verified facts without inventing results or references.
---

# Paper Alchemist

Use a deterministic local CLI for extraction and validation. The active Agent performs research, semantic distillation, drafting and review. Native packaging and installation target Codex; workflow records and Python commands do not depend on a particular Agent API. Never call an LLM API from the bundled scripts.

## Lead with the user's outcome

- Check this installation's `assets/corpus/builtin.json` to determine whether it includes reviewed guidance. When present, the first `brief`, `validate-profile`, `list-papers` or `scan-corpus` in a fresh workspace provisions that guidance automatically; original papers are unnecessary. When absent, this is the empty edition: help the user distill their own papers or import a completed profile first. Preserve an existing selected/custom profile and never claim the empty edition contains reviewed papers.
- Accept natural-language requests for installation, corpus profiling, integration, validation, and drafting. Infer command arguments from paths and outcomes the user provides; ask only for choices that materially change the result.
- When the user requests an end-to-end task, carry it through extraction, semantic distillation, integration, validation, and drafting as far as the available evidence allows. Do not make the user relay intermediate CLI commands.
- When the user requests several sections or a complete paper, build and apply the matching module brief to each section separately, then assemble the requested deliverable with consistent terminology, contributions, numbers, and citations. Do not replace module-specific generation with one undifferentiated prompt.
- Deliver submission-form academic content. The manuscript contains only its research argument, equations, figures, tables and references: no assistant preface, AI notice, generation explanation, writing advice, task framing or review checklist. Keep operational records separate and omit an appended status explanation when the user requests manuscript-only output.
- Before reusing a profile for writing, run `scan-corpus` once for its registered folder. Follow [references/incremental.md](references/incremental.md) when changes are detected; preserve an already authorized update scope.
- For a distillation request, extraction and seed creation are only intermediate results. Say that distillation is complete only after semantic synthesis and integration finish and `validate-profile` returns `generation_ready: true`.
- Translate internal status into user outcomes. Lead with “the profile is ready for writing” or “the profile still needs work,” then explain included or excluded papers, limitations, and any action the user must take. Show raw fields or commands only when the user asks, when they are useful for reproducibility or troubleshooting, or when the user must run something the Agent cannot execute.
- Use the Codex-native entrypoint and local Python runtime. Follow the capability fallbacks in [references/research-workflow.md](references/research-workflow.md) when browsing, delegation or rendering is unavailable. Do not require Claude commands, hooks, extra model subscriptions or a multi-agent team.

## Choose the operation

- For research planning, an end-to-end research/writing task or resuming an existing project, start with [references/research-workflow.md](references/research-workflow.md). Enter at the requested stage, preserve existing decisions and continue authorized work without routine stage-by-stage approval prompts.
- For finding literature, checking references, building an evidence matrix or a systematic-review request, read [references/literature-evidence.md](references/literature-evidence.md). Literature discovery does not add papers to the style library or authorize study claims automatically.
- For manuscript critique, reviewer reports, response letters or revisions, read [references/review-revision.md](references/review-revision.md). Review the actual version and account for every supplied comment; use `check-workflow` when persistent evidence/revision records are requested.
- For `distill`, read [references/workflow.md](references/workflow.md) and execute the complete corpus workflow.
- When a PDF's paragraphs mix columns or other layout blocks, use `compare-pdf-text` and inspect its candidates against original pages. Choose the coherent order from source evidence, create the reviewed source-hash map described in [references/incremental.md](references/incremental.md), and apply it through `distill --update --pdf-order-map`. Recheck section boundaries before semantic review; neither candidate length nor comparison success establishes distillation completion.
- To show distilled papers, detect folder changes, or add papers to an existing profile, read [references/incremental.md](references/incremental.md). Use the plugin's inventory, review queue and semantic-recording commands; scanning alone is not distillation.
- To add a folder containing only new papers to the included or imported guidance, use `distill --extend` for the parent library. Complete the queue using each item's indicated profile, synthesize and integrate that added profile, then validate the parent. Preserve the reviewed base and its source counts; never replace it with the sparse new folder.
- For `integrate`, validate completed module profiles, then run the integration workflow in [references/workflow.md](references/workflow.md).
- To reuse a completed profile in another project or move it between computers, read [references/portable.md](references/portable.md). Export/import the reviewed guidance and attached terminology without copying reference-paper prose; continue incremental updates through the normal source-backed workflow.
- For `abstract`, `introduction`, `related-work`, `problem-definition`, `methodology`, `experiment-setup`, `results-analysis`, `conclusion`, or `section`, read [references/generation.md](references/generation.md).
- For multiple sections or a complete draft, read [references/generation.md](references/generation.md) and follow its multi-section orchestration rules.
- For profile and context file fields, read [references/schemas.md](references/schemas.md).
- When a reviewed domain terminology registry is available, read [references/terminology.md](references/terminology.md) and attach it to the section brief. Expand ambiguous acronyms before applying model-specific definitions.
- After drafting or revising, apply [references/draft-audit.md](references/draft-audit.md). Check the actual output and complete a fact-bound semantic review; automatic checks alone cannot accept an article.
- When copy evidence reports damaged source glyphs, use the source-bound recovery workflow in [references/draft-audit.md](references/draft-audit.md#recover-reference-encodings). Keep original semantic evidence intact and export only reviewed hashes, never recovered reference prose.
- For Codex plugin installation and invocation, read [references/platforms.md](references/platforms.md).

## Run the local CLI

Use the prepared runtime with this installed plugin's own launcher. On Windows:

```powershell
& <plugin-root>/runtime/run.ps1 --version
```

On macOS or Linux (including WSL):

```bash
sh <plugin-root>/runtime/run.sh --version
```

Replace `paper-alchemist` in reference examples with this launcher, or invoke `skills/paper-alchemist/scripts/run.py` with the prepared interpreter. Never resolve an older globally installed package in preference to this plugin. For an explicitly requested installation or upgrade, follow the repository's `docs/INSTALL.md`: prepare the private runtime, register the marketplace, install the native plugin, and verify the actual installed copy. Setup reuses compatible Python or prepares a private interpreter; it does not change system PATH. Ordinary commands do not download anything. Optional PDF/OCR or LaTeX system components require their own task scope. If setup was not requested and the runtime is missing, explain the missing step.

## Preserve the bilingual contract

Keep English and Chinese evidence separate during extraction and module distillation. During generation, use both languages:

1. Apply the target-language module profile at approximately 70% influence.
2. Apply the secondary-language module profile at approximately 30% influence.
3. Transfer rhetorical functions and organization across languages.
4. Keep grammar, wording, terminology, voice, and citation punctuation under the target-language profile.
5. If either language lacks evidence, give the available language all corpus influence and record the missing language as assistance, not observed corpus style. Explain that profile limitation outside the manuscript when relevant; it is not part of the article.

## Enforce evidence boundaries

- Use the corpus only to infer aggregate writing patterns. Do not copy long source passages or imitate a single author.
- Use `paper-context.yaml` and explicit user answers as the only sources of research facts.
- If the user has no context file, do not make them author YAML manually. Read user-supplied drafts, notes, tables, and bibliography files when available; otherwise conduct a short guided interview. Collect only module-required facts, ask in small groups, distinguish missing or ambiguous claims, and present a fact checklist for confirmation before writing a user-requested context path.
- Ask only for module-required missing facts before drafting. Never turn an unknown answer into a guessed value.
- Never invent contributions, methods, datasets, baselines, parameter values, numerical results, statistical significance, limitations, or citations.
- Separate confirmed study facts from writing-material availability. Record unattached files, unprovided test outputs and unperformed author checks under top-level `materials`, outside `research`. Those gaps do not establish what the study did not do and do not belong in the manuscript. Use `research.limitations` only for confirmed scientific limitations; published data-availability statements also need confirmed research facts.
- Make component interfaces explicit: which state a stage receives, changes and returns. Resolve a material ambiguity such as refilling the residual selection versus restarting empty before describing it as the method.
- Resolve an ambiguous problem acronym by confirming its full name, entities, objective and defining constraints. A shared abbreviation does not select a model. Expand a confirmed acronym at first use in the assembled paper.
- Use only citation keys listed in the context file or supplied explicitly by the user.
- Return content in chat by default. Write a file only when the user explicitly provides an output path.

## Validate completion

- Run `paper-alchemist validate-profile --profile <name>` after distillation or integration.
- Treat `pending` and `stale` module profiles as incomplete. Never bypass the integration or generation gate.
- If `generation_ready` is false, use `incomplete_profiles` and `errors` internally to continue any work that can be completed safely. Tell the user only what remains, why the Agent cannot continue, or what user action is required; never describe the profile as ready for generation.
- Confirm every used profile path and source count from the generation brief.
- Read matching `additional_module_profiles` when present, including their integrations and conflicts. Keep each layer's confidence and evidence scope; an additional paper supplies writing guidance, not facts or citations for the current study. Export/import the parent library to carry all active additions together.
- For a completed profile, summarize its writing readiness, source coverage and material limitations in plain language. For a requested manuscript, return the manuscript itself; keep language/profile status, validation details and review notes outside its content and provide them only when requested or needed to resolve a blocking issue.
