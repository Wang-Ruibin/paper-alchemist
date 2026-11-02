# Draft evidence audit

[简体中文](zh-CN/draft-audit.md)

## Check the current draft

Use this workflow after drafting or revising a section or an assembled paper.
Audit the actual returned text against confirmed research facts. The corpus
provides writing conventions, never the current study's results.

```bash
paper-alchemist audit-draft draft.md --context paper-context.yaml --module section --out draft.audit.json
```

Use the actual module for a single section. Optionally add
`--terminology-registry registry.json` and `--corpus-prose permitted-sections/`.
The latter reads permitted extracted `.txt` sections, excludes `full.txt`, and
reports overlaps of at least 13 consecutive normalized English words. Without
that override, the command uses source-bound lexical fingerprints from the
selected profile or the included corpus; use `--profile` and `--workspace` to
select another library. Fingerprints contain hashes and source bindings, not
reference sentences. Active reviewed additions are checked too when their
records are available. The report states actual and expected reference counts.
Do not use held-out prose to tune development drafts. If neither supplied prose
nor fingerprint records are available, copying was not checked.

This is an exact lexical screen within indexed recognized extracted sections
and any separately reviewed decoded PDF variants. It does not establish semantic
originality or check Chinese prose, unrecovered layout or every PDF region.
Preserve these limits and any active encoding uncertainties in the separate
review record; a clean match list is not complete plagiarism clearance.
The report also flags control/replacement glyph uncertainty in reference text;
ordinary word matching can miss overlaps through a damaged word. Resolve those
windows against the source or verified recovery before accepting the copying
gate. A clean overlap list alone does not resolve an encoding warning. The
signal is conservative and may include mathematics; no missing letters are
inferred and no reference prose is emitted in the warning.

The command checks authorized citation keys, numeric literals, required facts,
ambiguous variants, confirmed prohibited expressions and suspicious claims.
It also rejects recognizable assistant prefaces, AI self-description and
evaluation notices in manuscript text. These are limited lexical checks; review
the full article for subtler writing advice, workflow explanations and task
framing. Scientific descriptions of AI methods and relevant study limitations
remain ordinary research content.
Check the basis of negative statements too. Top-level `materials` describes
what the writer has received or checked; it is not evidence that an experiment,
test or audit was absent from the study. A claim ledger supported only by these
authoring fields cannot pass. Preserve confirmed scientific limitations and
resolve material method-state ambiguities against the research facts.
Rendered author-year or numeric references require bibliography mapping. The
same value appearing in the facts does not verify its population, metric,
comparator, direction or unit. Interpret findings against the source facts;
avoid rewriting correct prose merely to satisfy a lexical diagnostic.
Check that a relative percentage has not become a percentage-point difference
or a mean of relative gains a raw-mean dominance claim. A citation must support
the attached clause, including any attributed implementation detail.

Numeric diagnostics accept equivalent decimal padding, thousands separators and
scientific notation without rounding away precision. Percent units remain
distinct; `percent` and `per cent` spellings denote the same unit as `%`, while
percentage points are not aliases for relative percentages. For reviewed numeric displays, a scalar field ending in `_percent`,
or its `value`, `exact`, `display` and `decimal_N` fields, explicitly declares
percent units. A measurement object with `unit: "%"` or `unit: percent` declares
the same units for those measurement fields. A sample count such as `n` in the
same object does not inherit percent units. An unlabelled ratio is never
converted into a percentage, and an unstated rounded value still needs evidence.

In simple Markdown or LaTeX tables, a complete single-number cell inherits an
explicit `%` or `(percent)` unit from its own column header. The unit does not
apply to neighboring columns, surrounding prose or a later table. A count in
the same context cannot validate a percentage with that value. Nested/spanning
headers and mixed numeric annotations do not receive inferred units; supply
explicit units and review their meaning. These format rules do not turn an
unlabelled ratio into a percentage or complete semantic review.

Literal powers of ten inside mathematical markup, such as `\(10^{-9}\)` and
`\(1.23\times10^{-3}\)`, are compared as scientific notation. Their exponents do
not become independent study values. Coefficients, signs and full precision are
retained; general symbolic expressions are not evaluated by this format rule.
When a draft computes an algebraic consequence of supplied data, verify its
operands, units, aggregation and scope before recording it as a calculated fact.
Keep the calculation and original fact bindings outside the manuscript, and
bind subsequent review to the updated context. Never add a value merely because
it appears in the draft or treat a derived difference as a new experiment.

Explicitly keyed LaTeX `\bibitem{key}` entries inside `thebibliography` and
Markdown `[key]` reference paragraphs under a References/Bibliography heading
use that key's authorized citation metadata for numeric checks. A year, volume
or page number from one reference cannot validate another entry or a result in
the article body. Unmapped references still need an explicit bibliography
mapping. These checks do not establish citation entailment or complete semantic
review.

Markdown reference labels may also use list markers or bold keys such as
`- **key.**`. Unicode minus signs retain their negative value. TeX double
hyphens between numbers denote ranges in ordinary text and bibliography entries;
the same characters inside mathematical expressions retain their arithmetic
meaning. Recognized table-width, spacing and orphan-control penalty commands are layout, while numeric
table cells and the same values in prose remain subject to fact checks. None
of these formatting rules completes semantic review.

## Recover reference encodings

For a reference PDF with uncertain glyphs, the Agent prepares a private candidate:

```bash
paper-alchemist prepare-copy-evidence paper.pdf --workspace .
```

Inspect affected words and their actual source fonts against original pages.
When explicit source/font/encoded-glyph mappings are necessary, pass the
identified review through `--font-reviews reviewed-fonts.json`. The review binds
each mapping to the PDF hash and font object, with rendered-image evidence.
Never replace a control code globally or infer a missing letter from context.
The candidate and receipt remain private; preparation alone performs no semantic
review and does not accept a manuscript.

After checking the complete decoded text and resolving all reported glyph
warnings, register its receipt for the exact included source:

```bash
paper-alchemist register-copy-evidence --profile library --source paper.pdf --receipt candidate-receipt.json --reviewer "identified reviewer" --review-scope "All PDF pages decoded and source-bound glyph recovery checked; this review covers English lexical evidence only." --workspace .
```

The Agent supplies these paths and the actual review scope. A batch may use
`--batch source-receipts.json` instead of one source/receipt pair; valid earlier
registrations survive a later error. Registration verifies original PDF bytes,
page count, exact candidate bytes and current section bindings. It adds hashes
without changing raw text, observations or integrated guidance. Original
fingerprints and warnings remain available. A matching reviewed decoder variant
resolves that source's active encoding signal for this bounded lexical screen;
changed source or section hashes invalidate its reuse.

Portable exports carry the reviewed hashes, not the decoded prose. Updated
included assets can supply matching copy evidence to an existing library without
rewriting its snapshot. Chinese and semantic-originality review still need their
own evidence.

## Complete the semantic review

Review every factual and citation-bearing sentence. Record its exact draft
span, applicable context paths, supported/unsupported judgment and reason.
Check equations, assumptions, conditional definitions and reasoning, including
changes in aggregation or denominators. Revise unsupported content or obtain
the missing fact from the user.

The review JSON contains `draft_sha256`, `context_sha256`, `reviewer_kind`
(`agent` or `human`), `reviewer`, and `coverage` set to
`all-factual-and-citation-bearing-sentences`. Use hashes from the diagnostic
report. Its `checks` must explicitly judge `factual_entailment`,
`terminology_and_notation`, `citation_entailment`, `claim_calibration`,
`cross_section_consistency`, `copying`, and `format`. Use `pass` only after
performing the relevant review; otherwise keep the draft unfinished.

Each `claims` entry needs `text`, `context_paths`, `judgment: supported` and a
substantive `rationale`. Paths may identify mappings or list indices, such as
`research.results.0`. Account for remaining prose through justified
`non_claim_spans`; do not approve one sentence and leave the rest unreviewed.
For a derived count, provide `derived_values` with exact `claim_text`, `value`,
`operation: sum`, and at least two fact-bound `operands`, each with a
`context_path` and explicit numeric `literal`. Arithmetic verification does
not establish that the populations can legitimately be combined.

```bash
paper-alchemist audit-draft draft.md --context paper-context.yaml --module section --semantic-review draft.review.json --out draft.audit.json
```

A changed draft or context invalidates the old review. Recheck affected claims
and regenerate the hash-bound record. Exit code zero requires mechanical and
recorded semantic gates to pass; diagnostics without a completed review return
an incomplete result. Save review artifacts only in a path authorized by the
user or evaluation task.

## Assess writing quality

Evidence checks do not measure elegance, organization or corpus alignment.
Also inspect the matching module's rhetorical roles, professional wording,
term/notation consistency, calibrated interpretations, repetitions and
transitions. The deliverable must read as a submission-form article, with review
records and operational explanations outside the manuscript. Full papers need a separate cross-section reading, including the
abstract against the body. An Agent review is not human expert review or a
guarantee of journal acceptance. In a development checkout, use the frozen
`evaluation/PROTOCOL.md` for systematic comparisons; the packaged runtime does
not require repository evaluation data.

After fact review, perform a distinct editorial reading of the assembled
article in publication order. State the method and reporting rules directly:
replace authoring-input language such as “supplied rounding” with the actual
display convention, and remove hypothetical transcription or audit corrections.
Keep supported scientific qualifications where they change interpretation,
consolidating repeated limits elsewhere. Expand an abbreviation at its first
use in the abstract and main text separately. Place each table with the argument
that uses it, recheck numbering and directional references, and keep displayed
equations with their lead-in text after floats. Apply substantive corrections
to both formats and affected section files; retain their fact, citation and
notation bindings. Recompile and inspect every changed rendered page. Record
this editorial check outside the article; an earlier draft's review cannot
accept the revised text.
