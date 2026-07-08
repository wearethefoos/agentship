---
name: sea-trial
description: Shipwright phase 6 - prove the Rust port behaves like the original. Runs the parity suite against both implementations, diffs everything, adversarially hunts drift, and writes the final report with all deliberate behavior changes. Use after rebuild, or when the user says "verify the port", "sea trial", "compare old and new".
---

# Sea trial — the same questions, both ships

The parity suite asks identical questions of the original and the port.
Every difference must map to a findings-ledger entry decided `fix`; an
unexplained difference is a defect in the port, even when the new answer
looks better. This phase ends with evidence, not confidence.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the SessionStart hook's
path). Start with:

```bash
shipwright status && shipwright phase start sea-trial
```

## Steps

1. **Re-baseline the oracle.** Run the full parity suite against the
   ORIGINAL once more; it must be green. If it is not, the original moved or
   the suite rotted — fix that first, nothing else is meaningful.
2. **Run against the port.** Same suite, switched to the Rust app. Flip
   `shipwright feature set <id> e2e-new on` per passing feature. For each
   failure, classify: port defect (back to a porter, with the diff), suite
   assumption (fix the test, note why), or covered behavior change (must
   already carry its finding id — verify the env-switched expectation from
   the blueprint phase is what passed, not a weakened assertion).
3. **Adversarial sweep (Opus, parallel).** The suite only asks planned
   questions; drift hides in unplanned ones. Fan out `sea-trial-judge`
   agents across subsystems to feed both implementations unplanned inputs —
   edge cases, error paths, exact error messages, ordering, encoding,
   concurrent access — and to audit remaining `TODO(port)` markers, `unsafe`
   blocks, and Cargo.toml against the blueprint. Repair loop as in rebuild
   (two failures → escalate to Fable).
4. **Non-functional sanity.** Not a benchmark suite, but catch regressions
   an agent flattened: rough latency/throughput/startup comparison
   appropriate to the app kind; `PERF(port)` markers are the checklist.
   Material regressions become findings (`--kind perf`) — the user decides
   whether they block.
5. **Final report.** `shipwright report` gives the matrix and ledger; wrap
   it into `docs/rewrite/sea-trial.md`: verification method, suite results
   old vs new, the complete **deliberate behavior changes** list (finding
   id, old behavior, new behavior — the report's fix-decisions section is
   the source), adversarial findings and their resolutions, perf notes, and
   known gaps (surviving TODO(port) markers, untested areas) stated plainly.
   Mirror the behavior-changes list into the new repo's docs (release-notes
   material). If the memory plugin is active, save the outcome.

## Checkpoint

```bash
shipwright phase complete sea-trial
```

(The gate requires `e2e-new` on every feature.) Report the final picture:
suite results, behavior changes shipped, known gaps — and recommend a
cutover approach: strangler-fig (route traffic incrementally, original stays
the oracle) for live services; direct switch is defensible only for small
tools with total golden coverage. The parity suite and `docs/rewrite/` stay
in the original repo as the port's provenance record.
