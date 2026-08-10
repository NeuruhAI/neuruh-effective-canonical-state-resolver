# Neuruh Effective Canonical State Resolver

Public Commons Release 036.

A deterministic, read-only projection answering one question: **what is the effective canonical state now?**

Given the current Release 026 lifecycle tip plus zero or more Release 035 canonical revision lineages, the resolver deterministically derives one effective canonical truth — or fails closed as `ambiguous`.

## Precedence rule

```
Current 026 lifecycle tip
        |
        v
Is there exactly one valid 035 revision lineage
anchored to THIS exact lifecycle tip?

NO  -> effective canonical = the lifecycle tip's stage/state
YES -> effective canonical = the lineage's latest revision state
```

## Supersession rule

A canonical revision is valid only against the lifecycle tip to which it was legitimately anchored. A newer legitimate lifecycle transition supersedes revisions anchored to an older lifecycle tip: they are classified `superseded_stale_anchor`, remain evidence, and can never override the newer tip.

## Fail-closed classification

The resolver rejects (raises) structurally invalid evidence and explicitly classifies everything else:

| Condition | Outcome |
|---|---|
| broken hash chain, tampered entry, wrong predecessor | rejected (error) |
| failed or invalid receipt in lineage | rejected (error) |
| duplicate receipt or authorization in lineage | rejected (error) |
| cross-stage or unknown-stage revision entry | rejected (error) |
| evidence for a different target | rejected (error) |
| no lifecycle tip evidence | `ambiguous` / `MISSING_LIFECYCLE_EVIDENCE` |
| competing distinct lifecycle tips | `ambiguous` / `AMBIGUOUS_COMPETING_TIPS` |
| two diverging lineages on the current tip | `ambiguous` / `FORKED_REVISION_LINEAGE` |
| lineage cites current tip but contradicts its content | `ambiguous` / `LIFECYCLE_ANCHOR_CONTENT_MISMATCH` |
| lineage anchored to an older tip | classified `superseded_stale_anchor` |

There is no silent best guess: an `ambiguous` resolution carries no effective stage, state, or source.

## 036 is a resolver, not an authority

036 hard-codes every authority flag false. It does not deploy, execute, repair reality, change lifecycle state, change canonical truth, grant authority, or contact any private production system. Its output surfaces the exact source digests used (`lifecycle_tip_digest`, `revision_tip_hash`, `evidence_digest`) so any consumer can independently re-derive the same truth.
