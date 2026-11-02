# Corpus Distillation Workflow

## Contents

- Prepare the corpus
- Review private packets
- Complete module profiles
- Integrate bilingual profiles
- Confirm completion
- Update an existing profile
- Privacy and failure handling

## Prepare the corpus

Run from the research project where `.paper-alchemist/` should live:

```bash
paper-alchemist distill <paper-folder> --profile <name> --language auto --ocr auto
```

Use `--language en` or `--language zh` only when the user explicitly wants to override detection. For an existing profile, follow [incremental.md](incremental.md), scan the registered folder and use `--update` within the user's current update authorization.

Use `--ocr auto` to OCR only low-text PDFs, `--ocr always` for image-heavy pages whose text layer is incomplete, or `--ocr never` to disable OCR. OCR requires `pdftoppm` and `tesseract`; Chinese OCR also requires the `chi_sim` language pack. Do not install those tools silently.

Read the JSON result and inspect `.paper-alchemist/profiles/<name>/source-manifest.json`. Report excluded files and their reasons. Check `content_mode`, `ocr_used`, and extraction warnings. Do not claim that a scanned or low-text PDF was distilled when OCR was unavailable or unsuccessful.

Before synthesis, verify section boundaries against the paper. Column order,
diagram labels, page numbers, contribution lists and publisher sidebars can
create plausible but incorrect headings. Recognized module counts do not prove
that the prose is correctly classified. For ambiguous sources, record reviewed
spans using the section-map contract in [schemas.md](schemas.md), then refresh
with `--section-map <reviewed-map.json>`. Maps bind to source and raw-text hashes
and persist across updates. Exclude administrative blocks and restore split
paragraphs by verified reading order. Keep unresolved layout/font material out
of linguistic conclusions; unfiltered PDF averages are not drafting targets.
Control/replacement-glyph warnings also apply to reused PDF caches. Check the
affected word against the original page and, where needed, its exact font
mapping. Preserve raw extraction and source hashes; do not globally replace a
control code or guess missing letters from a plausible sentence. Exclude an
unresolved window from linguistic conclusions and record that reading limit.

The command creates:

- private extracted text and batch packets under `.paper-alchemist/cache/<name>/`;
- one private observation record per paper and recognized module under `.paper-alchemist/cache/<name>/observations/`;
- deterministic seed profiles under `.paper-alchemist/profiles/<name>/<lang>/modules/`;
- source and quality manifests under `.paper-alchemist/profiles/<name>/`.

## Review private packets

Process one language and module at a time. Read packet files under:

`.paper-alchemist/cache/<name>/packets/<lang>/<module>/batch-*.md`

For each source in a packet, complete its matching private observation record under:

`.paper-alchemist/cache/<name>/observations/<lang>/<module>/<document-id>.md`

Author source-bound semantic annotations and persist them through the plugin's
`record-observations` command described in [incremental.md](incremental.md).
Use its `review-plan` to find remaining work. Use completed observations, rather
than raw passages, when merging corpus-level findings.

Record `reading_scope`: a complete short section or exact representative
windows plus targeted checks. Do not call windowed reading a line-by-line
review of a long section. Explain embedded sections and remaining nonprose or
font limitations. Scripts may locate evidence and persist decisions; they do
not perform semantic review.

For each packet, record only aggregate observations:

- rhetorical moves and their typical order;
- paragraph roles and transitions;
- stance, voice, tense, hedging, and claim strength;
- citation and quantitative-evidence placement;
- figure/table introduction, cross-reference, comparison, and interpretation patterns;
- module-specific comparison or analysis patterns;
- reusable checks and failure modes.

Do not create phrase banks from the papers. Do not quote long passages. Treat filenames as evidence labels, not as author personas.

## Complete module profiles

Edit `.paper-alchemist/profiles/<name>/<lang>/modules/<module>.md` using the quantitative `.seed.md` file as evidence. Preserve YAML fields and every required H2 heading listed in [schemas.md](schemas.md).

Replace all `Pending Agent synthesis` markers with corpus-level findings. Set:

`synthesis_status: complete`

Keep claims proportional to `source_count` and `confidence`. For fewer than three sources, label findings tentative. When sources disagree, describe the variation instead of forcing a false rule.

Complete all eight modules for both languages. A zero-source module must remain low-confidence and explicitly state that no corpus evidence is available.

## Integrate bilingual profiles

After module profiles are complete, run:

```bash
paper-alchemist integrate --profile <name>
paper-alchemist validate-profile --profile <name>
```

`integrate` must refuse any module whose `synthesis_status` is `pending`, `stale`, missing, or invalid. Complete the listed modules and retry; never treat the quantitative seed as a semantic profile.

Review and refine the generated files:

- `en/integrated.md`
- `zh/integrated.md`
- `bilingual/cross-lingual.md`
- `bilingual/conflicts.md`

Align only high-level functions across languages. Keep target-language surface conventions dominant. Preserve conflict notes when English and Chinese corpora favor different paragraph lengths, voice, directness, or citation placement.

## Confirm completion

Run `paper-alchemist validate-profile --profile <name>` after integration. Extraction output, generated seed files, or `valid: true` alone do not mean distillation is complete. The profile is ready for generation only when the validation result contains:

```json
{
  "valid": true,
  "semantic_complete": true,
  "integration_complete": true,
  "generation_ready": true,
  "incomplete_profiles": [],
  "errors": []
}
```

If `generation_ready` is false, continue the modules named in `incomplete_profiles` and resolve `errors` before integrating and validating again. Warnings do not always block generation, but explain their practical effect to the user, especially low-confidence or single-language evidence.

Use these fields as the internal completion gate. In the user-facing report, clearly say whether the named profile is ready for writing, summarize source coverage and limitations in plain language, and provide raw validation values only when requested or troubleshooting.

## Update an existing profile

Follow [incremental.md](incremental.md) for the live paper list, read-only scan,
saved policy, exact-copy handling and pending review queue. Run the complete
plugin workflow for additions and modifications; an extraction update alone
does not finish incremental semantic distillation.

The CLI fingerprints evidence per language and module. It preserves completed profiles and integration artifacts when the relevant evidence is unchanged, and marks affected profiles `stale` when evidence changes.

Never overwrite a completed semantic profile with a quantitative seed without reviewing it.

## Privacy and failure handling

- Keep `.paper-alchemist/cache/` out of version control.
- Do not copy source papers into the profile or skill.
- Retain figure/table-heavy PDFs when extraction yields sufficient text. If they lack conventional sections, use their evidence only for `results-analysis` observations and explicitly note limited prose evidence.
- Stop and report password-protected, corrupt, unsupported, or still-low-text files after the selected OCR policy runs.
- Treat OCR as text recovery, not as authorization to infer unlabelled values from chart geometry or images.
- If extraction yields fewer than two recognizable paper modules, exclude it as insufficient structure unless it is classified as a figure/table-heavy visual supplement; visual supplements contribute only to `results-analysis`.
- If one corpus language is missing, finish the available language and mark bilingual integration as degraded.
