# Data Schemas

## Contents

- Source manifest
- Module profile
- Profile validation
- Paper context
- Generation brief
- Confidence

## Source manifest

Each document records its hash, format, detected language, inclusion decision, extraction backend, warnings, and recognized modules. PDF-specific audit fields are:

- `content_mode`: `prose` or `figure-or-table-heavy`;
- `ocr_used`: whether OCR text replaced the text-layer result;
- root-level `ocr_mode`: `auto`, `never`, or `always` for the run.

`figure-or-table-heavy` is descriptive, not an exclusion reason. A visual supplement with enough recovered text but no conventional headings is routed only to `results-analysis`; it is not treated as a complete paper narrative.

## Module profile

Keep this YAML frontmatter:

```yaml
profile: profile-slug
language: en
module: abstract
source_count: 8
visual_source_count: 0
confidence: high
synthesis_status: complete
```

`visual_source_count` reports how many sources in this module are figure/table-heavy. It is normally nonzero only for `results-analysis`; treat those sources as evidence about visual presentation, not as factual evidence for generated claims.

Status values:

- `pending`: deterministic seed exists, but Agent semantic synthesis has not been completed;
- `stale`: the underlying module evidence changed after the last synthesis;
- `complete`: semantic findings match the current module evidence.

Only `complete` profiles may be integrated or used for generation.

Keep these H2 headings exactly:

1. `Rhetorical moves`
2. `Organization`
3. `Language and stance`
4. `Evidence and citations`
5. `Cross-lingual transferable patterns`
6. `Do`
7. `Avoid`
8. `Generation checklist`

## Profile validation

`validate-profile` distinguishes structural validity from readiness for generation:

- `valid`: all required files, frontmatter fields, and headings are structurally valid;
- `semantic_complete`: every English and Chinese module has current Agent synthesis;
- `integration_complete`: all four language and cross-language integration artifacts exist;
- `generation_ready`: all three conditions above are true;
- `incomplete_profiles`: module identifiers that are `pending`, `stale`, missing, or invalid;
- `errors` and `warnings`: blocking structural problems and non-blocking quality cautions.

Use `generation_ready`, not `valid`, as the single completion signal before drafting.

## Paper context

Use `assets/paper-context.example.yaml` as the template. The stable top-level fields are:

```yaml
project: {}
research: {}
citations: {}
```

`research` may contain `problem`, `gap`, `contributions`, `method`, `experiments`, `results`, and `limitations`. Preserve numerical values and units exactly. Store citations by citation key; their descriptions provide grounding but do not authorize invented claims.

## Generation brief

The CLI emits:

- target module and secondary module paths;
- target integrated, cross-lingual, and conflict paths;
- target/secondary source counts and 70/30 weights when both languages have evidence, or 100/0 weights for the available language when one is absent;
- validated context data and missing required fields;
- allowed citation keys;
- optional evidence-labelled terminology candidates and clarification requirements;
- `complete` or `degraded-single-language` status.

Treat the brief as a routing artifact, not generated prose.

## Confidence

- `high`: at least eight qualifying sources for the language/module.
- `medium`: three to seven sources.
- `low`: zero to two sources.

Low confidence permits generation but requires a visible caveat. It never permits inventing patterns or facts.

## Reviewed section maps

Use a JSON object with `schema_version: 1` and a `documents` list. Each record
contains its relative `source`, original `source_sha256`, normalized cached
`text_sha256`, `reviewer_kind` (`agent` or `human`), `reviewer`,
`review_status: complete`, a source-supported `rationale`, and `spans`.
Pending boundary decisions cannot replace automatic sections.

A span contains `module` (one of the eight modules or `exclude`), integer
`start`/`end` character offsets in the current full-text string, `scope` and
`notes`. Offsets must be ordered, disjoint and inside the exact hash-bound
text. Multiple regions may belong to one module. Optional `module_order`
orders those regions within the reconstructed section, and `join: continuation`
joins a paragraph split by a verified float/column break; otherwise paragraphs
stay separate. Never move a region solely to make coverage look complete.

For a word visibly split around an omitted block, `join: word` concatenates the
reviewed fragments without adding a separator. It applies in the module's
logical reading order and requires an earlier retained fragment, a nonempty next
fragment and a letter on both sides of the boundary. It cannot apply to an
`exclude` span. Verify the complete word on the original page; this mode adds no
letters, performs no OCR and does not remove hyphens. Ordinary joins still keep
their paragraph or single-space separators, and source/raw-text hashes still
bind the map. Reread and record affected observations after applying a repair.

Omitting `replace_modules` reconstructs the entire document from the reviewed
spans. For a localized repair, set `replace_modules` to a nonempty, unique list
of affected module names. Every non-excluded span must belong to that list.
Only those modules are reconstructed; all other automatic modules retain their
exact text. A named module without a sufficiently long retained span is cleared,
so this can explicitly remove a false role. Include every affected role in the
list: `exclude` does not erase text from an unlisted automatic module. The same
source/raw-text identity and review requirements apply to both map forms.

Provide maps through `distill --section-map <path>`. They are retained in the
profile cache for subsequent updates. A source/raw-text change invalidates
the map and requires rereview; maps cannot include documents outside an
explicit evaluation partition. Boundary completion does not imply that every
raw token is suitable prose or that semantic module synthesis is complete.

## Draft audit records

Use the evidence and sentence-review contract in [draft-audit.md](draft-audit.md).
Top-level `materials` is reserved for writing-input availability and authoring
checks, separate from `research`. It may record missing attachments or test
outputs without asserting that the study lacked those artifacts or tests.
Research claims cannot be supported solely by such authoring metadata.
Structural profile validity does not return CLI success until
`generation_ready` is true. Draft audits likewise require completed,
hash-bound semantic gates for acceptance.
