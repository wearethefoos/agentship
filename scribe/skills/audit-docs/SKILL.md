---
name: audit-docs
description: Audit existing project documentation - verify all links (including external URLs), check docs structure and staleness against the code. Use when the user says "check the docs", "audit documentation", "are the docs up to date", "fix broken links", or after large refactors/renames.
---

# Audit docs

## 1. Link check (mechanical)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/check_links" docs --external
```

- Reports `file:line: problem` for missing files, dead anchors, undefined
  reference labels, unclosed/invalid mermaid fences, and (with `--external`)
  unreachable URLs.
- Fix every finding. For external links: prefer updating to the current URL;
  delete only if the resource is truly gone. Transient network failures — retry
  once before touching the link.
- Exit 0 means clean.

## 2. Structure check

- `docs/README.md` exists and links (directly or transitively) to every other
  doc file. Orphans: link them from the index or ask whether to delete.
- One topic per file; files > ~300 lines are split candidates.
- Flows/hierarchies explained in prose only → add a mermaid diagram
  (see the `write-docs` skill for style and diagram-type rules).

## 3. Staleness check (sample, don't boil the ocean)

For each doc, spot-check its strongest claims against the code:

- Referenced paths, commands, config keys, env vars still exist (grep).
- Setup instructions match the current tooling (lockfiles, scripts, CI).
- Diagrams still reflect the real component/flow structure.

Fix what's wrong, flag what's uncertain to the user with file:line references.

## Report

End with: number of link problems fixed, docs updated, orphans found, and any
claims you could not verify.
