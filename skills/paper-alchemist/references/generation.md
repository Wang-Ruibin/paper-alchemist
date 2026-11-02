# Grounded Bilingual Section Generation

## Contents

- Build or confirm the research context
- Build the generation brief
- Fill missing research facts
- Blend bilingual profiles
- Draft the module
- Generate multiple sections or a complete draft
- Validate the output

## Build or confirm the research context

Do not require the user to hand-author YAML. If a usable context file was not supplied, help build one in either of these ways:

1. Read user-named drafts, experiment notes, result tables, and bibliography files. Extract only facts explicitly supported by those materials and keep uncertain or conflicting statements unresolved.
2. If those materials are unavailable or incomplete, interview the user in small groups of easy-to-answer questions.

Determine the requested writing module before collecting facts, then prioritize only its requirements. For example, an abstract needs the problem, gap, method, contributions, and results; a methodology section needs the method; results analysis needs the experiments and results. Optional project metadata may be collected when useful, but do not turn context setup into a requirement to complete every template field.

Before writing a user-requested context path:

- summarize the facts that will be recorded and their supplied source;
- list missing, ambiguous, or contradictory items separately;
- show exact numerical values and units without normalization or reinterpretation;
- list allowed citation keys and what each key may support;
- ask the user to confirm or correct the checklist.

After confirmation, use `assets/paper-context.example.yaml` as the field-shape guide and write only to the exact path the user requested. Keep the file out of version control. When the profile is ready, build the generation brief and use `missing_context_fields` as an internal checklist; ask the user only about remaining facts instead of exposing schema field names unless troubleshooting.

The style corpus never supplies research facts. Do not infer a contribution, result, comparison, significance claim, limitation, or citation authorization from the distilled profile.

If a requested claim needs evidence absent from the supplied context, ask for
that evidence while continuing independently supported sections. A requested
significance claim needs the actual test specification and output, or suitable
paired observations for an authorized analysis; a positive descriptive mean is
insufficient. If a requested comparison changes the recorded budget or run
policy, explain that the available results belong to the executed protocol and
obtain results under the proposed policy before reporting it as performed.
Keep these clarification exchanges outside the article. Missing attachments
alone do not establish that the study omitted the test or experiment.

Keep writing-material status separate from study facts. Put unprovided files,
test outputs or author checks in top-level `materials`; do not turn them into
`research.limitations`. An unattached result does not establish that the study
performed no test. Omit unsupported positive or negative claims, and ask only
when the missing fact is necessary to the requested argument. A publication's
data-availability statement must itself be a confirmed study fact.

## Build the generation brief

When this edition includes `assets/corpus/builtin.json`, omit `--profile` in a
fresh project to use its reviewed guidance and terminology; original papers
and an old cache are unnecessary. The empty edition has no default library:
distill the user's papers or import a completed profile first. Existing
selected/custom profiles are preserved. Run `validate-profile` before writing.

Check the registered corpus once per writing task with `scan-corpus --profile
<name>`. Report new or changed papers and follow [incremental.md](incremental.md)
for the user's update authorization. Do not repeat the scan for every section
or silently claim that a cached profile includes newly detected papers.

Run:

```bash
paper-alchemist brief <module> \
  --profile <name> \
  --language <en|zh> \
  --format <latex|markdown> \
  --context <paper-context.yaml>
```

For a custom section, use module `section` and add `--section-name <name>`.

When a reviewed registry is available, add `--terminology-registry <registry.json>`
and follow [the terminology workflow](terminology.md). Do not silently expand a
shared acronym such as CTSP. Registry definitions check variants; the user's
verified model remains the authority for the current study.

Read every path in `profile_files`. Use the target module first, the secondary-language module second, the target integrated profile third, and the cross-lingual profile fourth. Consult `conflicts.md` before choosing surface wording.

When `additional_module_profiles` is present, also read each matching added
module and its integration. Apply its stated source scope and confidence
alongside the reviewed base. Use the combined language evidence weights and
terminology candidates; all layers remain writing guidance, never a source of
current-study facts, numerical results or citation authorization.

If the CLI reports an incomplete semantic profile or missing integration artifact, stop. Finish distillation and integration before asking the user for research facts or drafting prose.

## Fill missing research facts

Inspect `missing_context_fields` in the brief. If it is non-empty, ask the user only for those facts. Accept answers interactively and treat them as an in-session extension of the context file. Do not draft until the required facts are available.

Never infer a research result from a style corpus. The corpus answers “how to write”; the context answers “what is true.”

## Blend bilingual profiles

- Use approximately 70% target-language and 30% secondary-language influence.
- Borrow problem framing, gap placement, contribution ordering, experiment logic, comparison structure, and conclusion closure from either language.
- Do not translate distinctive source sentences.
- Realize all syntax, terminology, tense, voice, punctuation, and citation placement naturally in the target language.
- If either source count is zero, assign all corpus influence to the available language and label the result `degraded-single-language`. Missing-language assistance uses Codex's general language ability and must not be reported as observed style evidence.

## Draft the module

Apply the selected module contract:

- `abstract`: problem, gap, method, main evidence, contribution; do not add citations unless the context and venue practice require them.
- `introduction`: importance, precise gap, research response, contributions, and optional paper organization.
- `related-work`: organize cited work by approach or limitation; connect the comparison to the verified gap.
- `problem-definition`: define entities, assumptions, decisions, constraints, and objective without adding unstated assumptions.
- `methodology`: explain design rationale before procedural detail; connect components to the verified problem.
- `experiment-setup`: state datasets or instances, baselines, metrics, parameters, hardware, seeds, and stopping rules only when supplied.
- `results-analysis`: report result, comparison, magnitude, uncertainty or test, explanation, and implication; distinguish observation from interpretation.
- `conclusion`: answer the research problem, summarize verified evidence, state supplied limitations, and avoid unsupported future work.
- `section`: follow the user-provided section purpose while applying the same evidence boundaries.

Use `\cite{key}` for LaTeX and the supplied citation convention for Markdown. Never use a key absent from `allowed_citation_keys`.

Bind each cited clause to the reference's actual support. A benchmark's
configured implementation may be supported by the study context without being
described by the cited publication; separate those statements rather than
letting one citation imply both. Expand the full problem name at first use,
including in an assembled introduction that precedes the formal definition.

For interacting components, identify each input and resulting state. Distinguish
initial construction from refill after removal or repair of an existing object.
Do not make a repeated stage name imply an unstated reset or silently choose a
material procedure when the supplied account is ambiguous.

Deliver a manuscript in the form intended for submission. Return its academic
content directly, without an assistant introduction or appended explanation.
Exclude AI notices, generation descriptions, task framing, instructions about
allowed facts or citation keys, profile status, checklists and placeholders.
Resolve required missing facts before drafting; never hide an unresolved gap
behind a polished invented statement. Keep research-specific assumptions and
limitations in natural academic prose where they affect the argument.

Keep operational review and provenance in separate records. In synthetic
evaluation, record the fictional status in the fixture and artifact manifest,
outside the manuscript and rendered pages. Preserve previously frozen samples
and their original notices as historical evidence. Keep an algorithm's
tie-breaking policy separate from the problem's
objective, and describe comparison subsets by their supplied membership without
inventing difficulty labels.

Calibrate claims with concise, relevant limits. State a limitation where it
changes the interpretation of an actual result; consolidate repeated limits
in the discussion or conclusion. Avoid catalogues of hypothetical claims the
study does not make. A reference-method contrast does not isolate one causal
factor unless the supplied comparison controls the other changes. Preserve
the complete mechanism in compressed summaries: for example, ranking by
profit divided by incremental weight differs from ranking by weight alone.
When a compressed ratio rule admits a zero denominator, retain its supplied
exception in the synopsis or describe the rule without an undefined division.
Do not turn an internal correctness check into advice to the article's reader:
state the model, operation or finding directly and remove explanations that add
no new scientific relationship.
In the final editorial pass, keep a fact where it does useful work: define the
metric/model in its owning section and qualify a result where its scope changes
the inference. The abstract and conclusion can summarize the actual findings
without repeating a catalogue of unavailable materials or already settled
definitions. Remove redundant clauses rather than padding a section to a count.

Use conventional mathematical typesetting for supplied notation. Formatting
`S_i` as `\(S_i\)` or `Pi` as `\(\Pi\)` preserves its meaning; literal escaped
underscores are appropriate for code identifiers, not mathematical subscripts.
Keep percentage scales consistent: a ratio equals `r\%`, or 100 times that ratio
equals the numerical percentage `r`. Do not combine the factor 100 with `r\%`
in the same equality. Parenthesize the numerator difference in prose formulas.
Distinguish relative percentages from percentage-point differences, and retain
the defined aggregation in summaries: a mean of per-instance relative gains
does not establish dominance of pooled or raw mean objective values. In method
explanations, distinguish the eligibility filter from the ranking score; a
capacity-dependent candidate set does not make the score capacity-dependent.

For a material formal expression, check that it implements the stated model;
a small feasible/infeasible example can expose a sign or indexing conflict.
Keep the check in the audit. Resolve contradictory intent before presenting
a validated formulation, and do not silently change experimental claims to
match a repaired equation. A cited source is evidence to inspect, not a
guarantee that every printed formula is correct.

When profiles include figure/table patterns, transfer only their rhetorical function: how a visual is introduced, what comparison is foregrounded, and how observations are separated from explanations. Use a figure number, table number, caption claim, or numeric value only when it appears in the verified context or the user explicitly supplies it. Never estimate a value from chart pixels.

## Generate multiple sections or a complete draft

When the user requests several sections, run the full generation workflow separately for each requested module. Reuse confirmed research context, but build a distinct brief and apply the matching module profile for every section.

For a long module, outline its subsections and paragraph purposes before
drafting smaller units. Each unit keeps the module's brief and the same
verified facts, terminology, notation and citation mapping. Update that shared
record when a fact changes, then revisit every affected unit. Check component
interfaces and transitions when joining paragraphs; splitting the work does
not make its factual assumptions independent.

For a complete draft, normally work in this order:

1. introduction;
2. related work;
3. problem definition;
4. methodology;
5. experiment setup;
6. results analysis;
7. conclusion;
8. abstract.

Draft the abstract last so it reflects the verified body, then place it at the beginning of the assembled document. Preserve terminology, notation, contribution statements, numeric values, and citation keys across sections. Remove accidental repetition between the introduction, methodology, results, and conclusion.

Check directional references such as “above”, “below” and section numbers after
assembly. Include a readable local reference list or the user's working
bibliography mapping when a complete standalone manuscript uses citation keys;
authorized keys alone are not a finished reference presentation.

The user may request one combined file or separate section files. Write only to the exact path or paths they provide. If required facts are missing, ask for them before drafting the affected section; do not fill gaps merely to make the document appear complete.

## Validate the output

Before returning:

1. Match every factual sentence to the context or an explicit user answer.
2. Match every citation to `allowed_citation_keys`.
3. Remove source-like phrasing and single-author imitation.
4. Confirm target-language fluency and module structure.
5. Check that all returned prose belongs in the manuscript; keep profile-language and review status in separate records.
6. Return in chat unless the user explicitly supplied `out`; write only to that exact path.

Apply [draft-audit.md](draft-audit.md) to the actual text. Keep a hash-bound
sentence/claim review when the user requested an audit or the evaluation task
requires review artifacts. Numeric occurrence and citation-key checks cannot
certify entailment, technical validity or writing quality. Resolve findings,
then inspect the module organization and assembled-paper consistency before
reporting completion.

For LaTeX, compile the actual standalone output when a compiler is available,
then inspect every rendered page, including references. Resolve
overfull lines, literal-text notation and unreadable references. Every cited key
needs a human-readable reference entry using supplied bibliographic facts; label
fictional fixture references in the separate evaluation record rather than
inventing authors or dates or adding evaluation notices to the article.
Preserve original generated samples and record repairs during evaluation. A
successful compilation does not by itself establish polished layout or accurate
mathematics.
