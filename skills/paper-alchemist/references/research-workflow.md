# Research and writing workflow

[简体中文](zh-CN/research-workflow.md)

## Choose the entry point

Use the user's requested stage: plan, research, write, review, revise or
finalize. A complete workflow connects those stages; a request for one section
does not require a new research proposal or a review panel. Existing drafts and
reviewer letters can enter directly at review or revise. Reuse confirmed
decisions and continue work already authorized. Ask only about missing facts,
material research choices or external actions beyond that authorization.

| Request | Useful result | Read next |
| --- | --- | --- |
| Develop a topic or research plan | Question, bounded scope, method options and evidence needed | Planning below |
| Find or compare literature | Search record and claim-to-source evidence matrix | [literature-evidence.md](literature-evidence.md) |
| Draft one section or a paper | Module briefs and grounded academic prose | [generation.md](generation.md) |
| Critique a manuscript | Located findings with evidence and concrete remedies | [review-revision.md](review-revision.md) |
| Address reviewers | Comment-to-change mapping and a supported response | [review-revision.md](review-revision.md) |
| Prepare the final files | Current fact review, reference check and inspected output | Finalization below |

Planning, literature work and reviewing an existing manuscript do not require a
completed style profile. Drafting with corpus guidance still uses the existing
profile-readiness and per-module generation gates. The included library's
domain scope does not become evidence about every discipline. For another
field, identify applicable writing patterns and gaps; use the user's relevant
profile or distill authorized reference papers when different guidance is needed.

## Plan from the available research

Read the provided notes, draft, tables and bibliography before interviewing the
user. Produce a short research brief: the question, boundaries, proposed
contribution, existing evidence, plausible method and the next evidence that
would discriminate between explanations. Label proposals as proposed and
results as observed only when supported by study materials. Preserve doubts
and contrary findings rather than treating the desired contribution as proven.

Adapt the evidence plan to the study. Empirical work may need datasets,
comparators, metrics and uncertainty; theoretical work needs definitions,
assumptions and proof obligations; literature synthesis needs a search and
selection protocol. Do not impose a solver benchmark, statistical test or
experiment on every research question. Explain material method tradeoffs in
terms of the question and available evidence, without inventing work performed.

For an outline, map each intended contribution to the sections and evidence
that will support it. Mark missing support outside the manuscript. A full-paper
request normally authorizes building and using a reasonable outline; seek a
decision only when competing structures change the research interpretation.
Optional user-authored samples can guide tone and terminology, while the
reviewed corpus supplies aggregate rhetorical patterns. Neither supplies facts.

## Keep resumable records proportional to the task

For a long project or a requested audit, keep the research brief, sources,
current study context, draft versions, reviews and next unresolved action at
user-authorized paths. Keep operational notes outside article text. The Agent
creates structured records; do not ask the researcher to hand-edit a schema.
Without permission to write files, return the requested content in chat.

On resume, read the actual current artifacts and compare their hashes with the
record before reusing judgments. Preserve earlier reviewed versions when they
are needed to interpret reviewer comments. Recheck claims affected by changed
facts, sources or wording. Hashes detect changes; they do not make stochastic
model output reproducible or establish that an experiment ran.

## Check evidence and revision bindings locally

Use the optional Agent-authored
[workflow record](../assets/workflow-record.example.yaml) when persistent
traceability is useful. This is separate from the existing source-profile
records and [draft semantic review](draft-audit.md). Run:

```bash
paper-alchemist check-workflow workflow.yaml --draft paper.md --context paper-context.yaml --workspace . --stage review --out workflow.check.json
paper-alchemist check-workflow workflow.yaml --draft paper.md --context paper-context.yaml --workspace . --stage final --out workflow.final.json
```

The command is read-only unless `--out` is supplied. It never fetches sources,
calls a model, launches experiments or modifies the style library. It refuses
to overwrite its input files with a report. Exit zero means that the registered
bindings meet the selected stage's checks; it is not acceptance of the paper.

| Field | Contract |
| --- | --- |
| `schema_version` | Integer `1` |
| `draft_sha256`, `context_sha256` | Current hashes using the same conventions as `audit-draft`; diagnostics emit both |
| `artifacts` | List of unique `id`, workspace-relative `path`, raw-byte `sha256`, and `kind`: `study`, `literature`, `review` or `draft` |
| `claims` | Nonempty list of unique `id`, exact `start`/`end`/`text`, `context_paths`, `assessment` (`supported` or `unresolved`), `rationale` and optional `evidence` |
| `evidence` | Artifact ID, exact inspected `quote`, human-readable `locator`, `relation` (`supports`, `contradicts`, `insufficient`), `rationale` and optional authorized `citation_key` |
| `reviews` | Optional unique review IDs, report `artifact_id`, preserved `draft_artifact_id`, actual `reviewer`/`reviewer_kind`, and `comments` with unique `id`, original `text` and `severity` (`major` or `minor`) |
| `resolutions` | Optional unique `comment_id`, `action` (`revised`, `rebutted`, `deferred`) and `rationale`; closed items also need current draft/context hashes, `verified_by` and `verifier_kind` |

Offsets are zero-based Unicode code points, end exclusive, in the UTF-8 draft
read with universal newlines. Draft hashes cover that decoded text; context
hashes cover canonical parsed JSON with sorted keys, compact separators and
unescaped Unicode. Artifact hashes cover raw bytes, including CRLF. Evidence
quotes use UTF-8 text with universal newlines. For a PDF, retain the original
file hash and printed page/section in a reading note, and register the inspected
text note; this command does not inspect PDF pages or authenticate that note.

Context paths may address populated `research` or `citations` fields, including
list indices. Writing-material availability cannot support research claims.
A supported cited claim needs a `literature` artifact and matching citation key;
a bibliography entry alone is insufficient. An explicitly `unresolved` claim
may carry a known citation without support during review; it blocks final
handoff. Register every cited clause: every recognized citation occurrence
must lie in a registered span, including repeated uses of the same key.
Plain numeric/author-year references need explicit
key mapping and semantic inspection through `audit-draft`; they are not parsed
as citation keys by this helper.

A `revised` resolution needs an exact span in the current draft. For a deletion,
anchor the surrounding revised passage and explain the removed claim. A
`rebutted` resolution needs current context paths or source evidence supporting
the response. An omitted or `deferred` resolution stays open. The review stage
reports unresolved claims/comments as warnings so critique can proceed; the
final stage blocks them. Stale files, malformed records and broken evidence
bindings fail both stages. New draft or context hashes invalidate old closure
judgments even if the root record's hashes have been refreshed.

The helper checks registered spans and comments only. Complete extraction,
source authenticity, entailment and the correctness of reviewer judgments need
an actual semantic reading. An identified Agent is not an authenticated human
or an independent reviewer. Do not turn `traceability_ready` into a quality
score, a peer-review verdict or a submission guarantee.

## Finalize the requested deliverable

Reconcile abstract and body, claim strength, notation, numbers, bibliography,
figures and tables. Apply the existing `audit-draft` workflow to the current
text with a current semantic review; `check-workflow` does not replace it.
When revision records are in scope, run their final check too. Compile and
inspect rendered pages when the requested format and tools support it. Report
unperformed checks plainly, without inventing an acceptance decision or
padding the manuscript with operational notices. Never submit to a journal,
contact reviewers or run an experiment merely because finalization was asked.

## Use available host capabilities

| Capability | Behavior |
| --- | --- |
| Codex-native plugin | Default installation and discovery; use the bundled runtime |
| Other skill-capable host | Workflow text and local Python CLI can be reused; installation and orchestration are untested there |
| No browsing | Work from supplied sources; leave unfetched references and search coverage unresolved |
| No delegation | Perform distinct review readings sequentially and describe them honestly as the same Agent |
| No document renderer | Deliver the requested supported text format and identify the missing visual check |

No specific model, paid resolver, extra LLM API, Claude command, hook or automatic
subagent launch is required. The host's permissions and the user's task scope
govern tool use.

## Design references

Workflow design was informed by Cheng-I Wu's
[Academic Research Skills](https://github.com/Imbad0202/academic-research-skills),
reviewed at commit `6d9388674de1ad0437ad95db3d52f92b92204d84` on 2026-11-08:
its [stage architecture](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/docs/ARCHITECTURE.md),
[handoff contracts](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/shared/handoff_schemas.md)
and [reviewer workflow](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/academic-paper-reviewer/SKILL.md).
That project uses [CC BY-NC 4.0](https://github.com/Imbad0202/academic-research-skills/blob/6d9388674de1ad0437ad95db3d52f92b92204d84/LICENSE).
This implementation and its instructions are independently written; no upstream
code or prompt text is bundled. Its stage-confirmation policy, fixed agent
teams, model routing and review scores are not adopted. Existing Paper
Alchemist evidence boundaries and corpus records remain authoritative here.
