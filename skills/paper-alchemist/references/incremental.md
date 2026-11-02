# Paper inventory and incremental distillation

[简体中文](zh-CN/incremental.md)

## Show what has been distilled

In a fresh writing workspace, `list-papers` uses the included reviewed 95-paper
corpus automatically. An existing selected profile takes precedence. No original
PDFs are needed to list or use the included guidance. The Agent selects the
appropriate profile rather than asking the user to configure it.

Run the plugin runtime's `list-papers --profile <name>` from the workspace that
owns the profile. It hashes the registered folder and shows each paper's status.
Use `--json` for source identities, reading scopes, recognized/missing modules
and individual review records. Use `--cached` only when live access is unavailable
or explicitly unnecessary; disclose that file changes were not checked.

Translate the list into the user's language. Distinguish papers awaiting review,
papers whose recognized sections are reviewed but await profile synthesis, and
papers included in an integrated profile. A successful extraction is not a
distilled paper. Recognized-section completion does not certify every PDF line,
and a structurally ready profile does not establish generated-paper quality.

## Check the registered folder

At the start of a corpus-maintenance request, and once before reusing a profile
for a writing task, run:

```bash
paper-alchemist scan-corpus --profile <name>
```

This read-only scan compares content hashes, reports additions, modifications,
renames, deletions and identical copies, and performs no extraction or semantic
review. An unavailable folder is reported as unavailable, not as deleted papers.
Frozen evaluation selections remain limited to their saved sources; files
outside that selection are not silently added to training.

When the user has requested incremental distillation or already authorized the
ongoing corpus upgrade, continue within that authorization. If the request is
only to list/check papers or to write using an existing profile, explain the
changes and obtain the missing update instruction before changing the profile.
Do not repeatedly ask permission during an authorized update. Scanning occurs
when the plugin is invoked; it is not an unattended file watcher or a background
language-model service.

## Review a PDF's text order

If extracted paragraphs mix columns, compare the automatic and content-stream
orders against the original pages:

```bash
paper-alchemist compare-pdf-text <paper.pdf>
```

This creates private, content-hashed candidate files and a comparison receipt.
It does not change a profile, select a preferred order or perform semantic review.
Choose by readable source paragraphs, not by the longer candidate or the number
of detected headings. Figure text and misplaced floats may still need reviewed
section boundaries.

When a contact block or float interrupts a word, verify its fragments against
the original page and use the reviewed section map's `join: word` for that
boundary. It joins existing letter fragments without inserting a space; it does
not guess missing letters or remove hyphens. Default paragraph joins and
`join: continuation` retain their existing separators. Apply the map through
`distill --update --section-map`, reread the affected sections, and record their
new hashes through `record-observations`; unchanged reviews remain reusable and
the last valid changed review is retained in history. The Agent prepares these
maps rather than asking the user to edit them.

The Agent creates the review file from the comparison's actual source hash; do
not require the user to configure JSON. Its schema is:

```json
{
  "schema_version": 1,
  "documents": [{
    "source": "paper.pdf",
    "source_sha256": "<actual source SHA-256 from the comparison>",
    "pdf_text_order": "raw",
    "reviewer_kind": "agent",
    "reviewer": "<identified reviewer>",
    "review_status": "complete",
    "rationale": "Original PDF columns checked; content-stream order keeps the research paragraphs separate."
  }]
}
```

`source` is the canonical paper's path relative to the registered folder. `auto`
retains automatic extraction; `raw` requires Poppler's content-stream extraction
and fails explicitly if that order cannot be obtained. Apply the reviewed choice:

```bash
paper-alchemist distill <registered-folder> --profile <name> --update --pdf-order-map <reviewed-pdf-order.json>
```

Only specified choices change. Later updates preserve a choice for the same
source bytes, including a rename; changed source bytes clear the old preference
and resume automatic extraction until reviewed again. A supplied obsolete hash,
unselected source or noncanonical duplicate is rejected. A changed order
re-extracts that paper and makes affected observations stale while retaining the
last valid review; other current reviews remain reusable. Portable profiles carry
the saved choice for source-backed re-extraction. A completed order review is not
a completed section observation or a ready writing profile.

## Add only new papers to reviewed guidance

For the included corpus, or an imported profile whose original papers are
unavailable, keep the reviewed base and distill the user's new folder separately:

```bash
paper-alchemist distill <only-new-paper-folder> --profile <parent-name> --extend
paper-alchemist review-plan --profile <parent-name>
```

The plugin compares file hashes with the base and other additions, extracts only
new material, and retains the original guidance without rebuilding its source
cache. Exact copies do not add evidence. Follow each queue item's `profile` when
recording observations, synthesizing its modules and running `integrate`. The
parent is ready only after its active additions are complete and integrated.
Generation briefs then include the matching added modules, combined language
counts and source-scoped terminology. A one-paper addition remains low-confidence
evidence and does not automatically overturn a broadly supported pattern.

Later invocations scan each registered added folder. Repeat `distill --extend`
for changes to that folder; saved extraction policies and matching observations
remain reusable. Missing folders retain their reviewed guidance. Confirmed
removals leave the active added evidence, while the base remains intact. A folder
with no remaining unique papers is still watched for later arrivals. `--cached`
does not inspect live folders. These checks run on invocation, without a daemon.

To reconnect an added folder after moving computers, the Agent identifies its
existing layer, inspects the new location, and applies:

```bash
paper-alchemist distill <relocated-added-folder> --profile <parent-name> --extend --addition-profile <added-profile> --rebind-source
```

Do not use a sparse added folder to replace the reviewed base with `--update`.
Use the parent's [portable export](portable.md) to share the base and all active
reviewed additions together. Study facts and drafts remain separate.

## Update a source-backed custom corpus

Additions belong in the profile's registered paper folder, including its
subfolders. Infer its path from the existing manifest instead of asking the user
to edit configuration. Run:

```bash
paper-alchemist distill <registered-folder> --profile <name> --update
paper-alchemist review-plan --profile <name>
```

Updates preserve the saved language, OCR, minimum-text and evaluation-selection
settings unless explicitly changed. Unchanged content reuses extraction and
current source observations. Identical file copies are listed but do not add
corpus influence. Renames reuse content evidence and update its source labels;
affected source labels still require profile refresh. Modified sources receive
new identities and reviews. Removed papers leave the active evidence set; a
single previous reviewed observation per source/module/language remains in the
private observation history. Source papers are never modified or deleted.

`review-plan` lists pending, stale or missing source-section reviews and module
profiles needing synthesis. Complete only those reviews, while consulting valid
old observations when combining the updated corpus. For a missing template,
rerun `distill --update` to restore it. Read the actual section and inspect PDF
pages when layout is ambiguous; write the five semantic fields and the actual
reading scope. Persist the authored JSON annotations through the plugin:

```bash
paper-alchemist record-observations --profile <name> --annotations <agent-authored.json> --reviewer <reviewer-name>
```

Each annotation names the included source, language, module and exact section
hash, plus `reading_scope`, `rhetorical_moves`, `language_and_stance`,
`evidence_introduction`, `transferable_pattern` and `risks_and_exceptions`.
An optional source hash must also match. The command validates the whole batch
before recording it, identifies the reviewer and timestamp, and never invents
semantic findings. See [workflow.md](workflow.md) for reading and synthesis.
`reading_scope` may be prose or a structured record with current section length,
ordered half-open character intervals, actual coverage, mode and interpretation.
A partial interval set cannot be labelled a complete-section review.

Correcting an existing observation's interpretation or reading scope also
invalidates its completed module synthesis and the integrated profile, even
when the paper bytes have not changed. The previous reviewed observation is
retained before replacement or boundary rebinding; repeated unreviewed boundary
changes do not replace that last valid record. Submitting the same observation
again with the same reviewer preserves its file and timestamp.

Review and re-synthesize affected modules, preserving useful existing guidance
and explaining new variation. Zero-source language assistance must also refresh
when its source-language evidence changes. When evidence in a previously absent
language appears, or the last evidence in a language disappears, refresh guidance
that described its availability; valid observations in the other language remain
reusable. Then integrate and validate through
the plugin, inspect the paper list, and run the relevant writing regression:

```bash
paper-alchemist integrate --profile <name>
paper-alchemist validate-profile --profile <name>
paper-alchemist list-papers --profile <name>
```

Do not report completion while source reviews, synthesis or integration are
pending. Explain which papers changed, which old work was retained, which
sections were updated, and any remaining source or writing-test limitations.

## Relocation and reviewed boundaries

Passing a different folder to `distill --update` does not merge corpora and is
rejected by default. Use `scan-corpus --source <new-folder>` to inspect a possible
relocation first. Only for an explicitly requested folder relocation, pass
`--rebind-source` after checking the same-content/missing/new files. Separate
unrelated folders require an explicitly arranged common corpus or separate
profiles; do not silently replace the original corpus with the new folder.

Saved reviewed section maps whose source or raw text changed are invalidated,
reported and removed from active use. Inspect their recovered boundaries before
authoring new observations. An explicitly supplied obsolete map is rejected.
For a localized role correction, the Agent can use the schema's selected-module
mapping to preserve the exact automatic text of unaffected modules. Explicitly
name all changed or cleared roles and rereview their changed evidence; an
unchanged paper does not make a new boundary interpretation automatically valid.
Hashes and private update history support reproducibility; they do not perform
semantic distillation or prove that source paragraphs were read.
