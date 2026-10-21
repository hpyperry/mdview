# Domain Docs

How the engineering skills should consume this repo's domain documentation.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root.
- **`docs/architecture/adr/`**: read ADRs that touch the area you're about to work in.
  This repo uses `docs/architecture/adr/`, not the default `docs/adr/`.
- `README.md` and `AGENTS.md` for the product surface and code boundaries.

If any of these files don't exist, proceed silently; don't suggest creating them
upfront. The domain-modeling skill creates them lazily when terms or decisions
actually get resolved.

## Layout

Single-context repo:

```text
/
├── GLOSSARY.md
├── docs/architecture/adr/
│   ├── 0001-…
│   └── 0002-…
└── src/
```

There is no `GLOSSARY-MAP.md`; do not invent per-context glossaries unless the repo
actually becomes multi-context.

## Use the glossary's vocabulary

When an issue title, refactor proposal, test name or hypothesis names a domain
concept, use the term defined in `GLOSSARY.md`; don't drift to the `_Avoid_` synonyms.

If a concept isn't in the glossary yet, that's a signal: either you're inventing
language the project doesn't use, or there's a real gap worth recording.

## Flag ADR conflicts

If your proposal contradicts an existing ADR, surface it explicitly rather than
silently overriding it:

> _Contradicts ADR-0007 (…), but worth reopening because…_
