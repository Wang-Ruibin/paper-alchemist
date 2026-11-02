# Reuse a reviewed profile

[简体中文](zh-CN/portable.md)

The installed plugin already includes the reviewed 95-paper corpus. A new user
can write from that guidance directly; importing a separate profile is optional.
Use this workflow to share a custom profile or a library extended with new papers.

## Export the completed profile

Use this workflow when the user wants to write in another project or move a
reviewed profile to another computer. Infer paths from the request; do not ask
the user to assemble internal files. Export only after `validate-profile`
reports generation readiness.

```bash
paper-alchemist export-profile --profile <name> --workspace <source-project> --terminology-registry <registry.json> --out <profile.zip>
```

The archive contains section guidance, integrations, semantic observations,
reading scopes, source identifiers/checksums and an optional terminology
registry/catalogue. It excludes the reference papers, extracted paper prose,
research context, drafts and credentials. Omit `--terminology-registry` when no
registry exists; an already imported profile retains its attached registry.
An existing output archive is preserved rather than overwritten.

For a parent library with active added profiles, the same command exports the
base and every reviewed addition together. An unfinished addition blocks export;
it is never silently omitted. The archive carries each layer's reviewed source
bindings and removes its machine-specific manifest origin. Live folder paths
are reconnected explicitly in the receiving project.

## Import and write in another project

```bash
paper-alchemist import-profile <profile.zip> --workspace <writing-project>
paper-alchemist validate-profile --profile <name> --workspace <writing-project>
```

Import verifies file hashes, source-section bindings, evidence fingerprints and
completed synthesis before installing the profile. It preserves any existing
profile or evidence cache with the same name. Generate ordinary section briefs
in the receiving workspace; its attached terminology is selected automatically
unless an explicit registry is supplied. The normal section and full-paper
writing workflow still applies.

An extended-library import validates all profiles before installing any of them.
It refuses colliding destination profiles/caches and preserves existing state.
In a fresh project, the imported parent becomes the selected writing profile,
including its added module guidance and terminology.

The imported profile is a reviewed snapshot. Keep that provenance in operational
records, outside the manuscript. Source papers need not be copied merely to
reuse writing guidance; a live source-folder check may report the original
folder unavailable without treating its papers as deleted.

## Continue incremental distillation

When the user supplies only new papers, use `distill --extend` for the parent
library as described in [incremental.md](incremental.md). This retains reviewed
guidance without the original source papers. Reconnect an imported added folder
using its existing layer and explicit relocation; do not create duplicate influence.

Check the saved source folder before an update:

```bash
paper-alchemist scan-corpus --profile <name> --workspace <writing-project>
```

When the papers remain in their original location, use the normal authorized
`distill --update` workflow. It rebuilds the local extraction cache, retains
observations whose paper/section content matches, and requests semantic work
only for changed evidence. A new paper still requires source reading and
affected synthesis; importing guidance does not distill additions.

If the corpus moved, inspect the supplied new path before rebinding:

```bash
paper-alchemist scan-corpus --profile <name> --workspace <writing-project> --source <paper-folder>
paper-alchemist distill <paper-folder> --profile <name> --workspace <writing-project> --update --rebind-source
```

Preserve saved extraction and selection policies. Rebinding relocates one
tracked folder; it does not merge unrelated corpora. After actual extraction,
validation uses the recovered section text rather than snapshot hashes. Keep
valid old observations, finish pending reviews/synthesis and integrate as needed.
An imported snapshot is already integrated; do not regenerate its integration
files before reconnecting its source evidence.

## Interpret validation accurately

Checksums establish asset integrity and reproducible source bindings. They do
not establish the truth of the original experiments, independently re-read a
PDF, or certify generated-paper quality. Editing an imported profile or
observation invalidates its snapshot; do not repair this by merely changing
checksums. Apply the source-backed update and review workflow instead.
