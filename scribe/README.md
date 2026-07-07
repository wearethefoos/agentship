# scribe

Project documentation discipline for Claude Code. Pure Python stdlib.

## What it enforces

- All project docs live under `./docs`, indexed from `docs/README.md`.
- Clean markdown: one H1, sentence-case headings, language-tagged fences,
  relative links.
- Mermaid diagrams whenever a flow or hierarchy is explained.
- Links verified after every docs edit; breakage fed straight back to Claude
  to fix.

## Pieces

- **`bin/check_links`** — markdown link checker. Validates relative paths,
  anchors (GitHub slug rules, duplicate-heading aware), reference-style
  labels, mermaid fence sanity. `--external` also probes http(s) URLs
  (HEAD with GET fallback). `file:line: problem` output; exit 1 on findings.

  ```bash
  check_links docs                # relative links + anchors + mermaid
  check_links docs --external     # full sweep including URLs
  check_links docs/setup.md       # single file
  ```

- **PostToolUse hook** — after any Write/Edit to `docs/**/*.md`, checks the
  whole docs tree (catches inbound links broken by renames/deleted headings)
  and blocks with the finding list so Claude repairs them immediately.
  External URLs are skipped here for speed.

- **Skills** — `write-docs` (house style: layout, markdown rules, mermaid
  diagram-type guide), `audit-docs` (full link sweep with `--external`,
  orphan detection, staleness spot-checks).

## Install

```
/plugin marketplace add /home/wouter/Work/agentship
/plugin install scribe@agentship
```
