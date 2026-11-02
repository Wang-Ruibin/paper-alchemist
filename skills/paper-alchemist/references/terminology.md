# Evidence-Bound Domain Terminology

## Prepare the terminology hint

Use a reviewed registry and confirmed research context:

```bash
paper-alchemist term-brief --registry <registry.json> --context <paper-context.yaml>
```

Read source provenance, variant definitions, confusions, and required context.
A training-provisional registry is not a complete all-source resource.

## Attach it to a section brief

```bash
paper-alchemist brief <module> --profile <name> --language en --format latex --context <paper-context.yaml> --terminology-registry <registry.json>
```

Profile semantic readiness is still required. Terminology hints do not bypass
unfinished observations, stale profiles, missing integration, or missing facts.

## Resolve ambiguity

Full problem names take precedence over short acronyms. `resolved` means a
specific matching entry is available, not that the entire research model has
been confirmed. `needs-expansion`, `ambiguous`, and `unclassified` require a full
name or variant review. An uncatalogued model with a supplied full name,
entities, decisions, objective and constraints is `context-defined`: use that
confirmed context without pretending the registry supplied a verified definition.
Registry coverage is not missing research evidence. Unknown acronyms and
incomplete models still require clarification. Translate actual missing facts
into a concise question or checklist; do not expose internal fields as the user's task.
For structured problem data, inspect `full_name`, `name` and `title` together.
An explicit expansion can resolve a shared acronym; conflicting full names
still require clarification rather than silently selecting one field.

Confirm objective direction, aggregation, constraints, metric definitions, and
certificate status. The same acronym may denote different models in this corpus.
When a complete variant name contains its base name, select the more specific
name if every base-name occurrence is inside that variant name. Separate mentions
of both models still require variant review; identical full aliases remain ambiguous.

## Preserve evidence boundaries

Use definitions as checks against the verified current model. Do not replace
explicit user variants with a corpus default. Never borrow algorithm details,
complexity proofs, numerical results, novelty, or reference claims from a source.
Missing Chinese corpus evidence remains language assistance, not observed style.
