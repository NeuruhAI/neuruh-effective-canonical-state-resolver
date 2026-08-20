# Changelog

## 0.1.0a0 — v0.1.0-alpha

Initial public release of Public Commons Release 036.

- Deterministic read-only projection of effective canonical state from a Release 026 lifecycle tip plus zero or more Release 035 revision lineages.
- Precedence and supersession rules; revisions anchored to an older tip are classified `superseded_stale_anchor` and can never override a newer tip.
- Explicit fail-closed ambiguity classification: `MISSING_LIFECYCLE_EVIDENCE`, `AMBIGUOUS_COMPETING_TIPS`, `FORKED_REVISION_LINEAGE`, `LIFECYCLE_ANCHOR_CONTENT_MISMATCH`. No silent best guess.
- Structurally invalid evidence is rejected rather than classified.
- Every authority flag is hard-coded false; output carries the exact source digests so any consumer can re-derive the same truth.
- Published resolution schema, CLI (`resolve`, `validate`, `digest`), and synthetic examples that cross-check against the Release 035 fixture.
- Apache-2.0 with the complete license text and a `NOTICE` carrying the copyright.
- Continuous integration on Python 3.11, 3.12, and 3.13.
