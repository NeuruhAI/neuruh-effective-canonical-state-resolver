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

## Install

```bash
git clone https://github.com/NeuruhAI/neuruh-effective-canonical-state-resolver.git
cd neuruh-effective-canonical-state-resolver
python -m venv .venv
source .venv/bin/activate
pip install .
```

Or install a pinned release directly:

```bash
pip install "neuruh-effective-canonical-state-resolver @ git+https://github.com/NeuruhAI/neuruh-effective-canonical-state-resolver.git@v0.1.0-alpha"
```

## Sixty-second example

The repository ships a synthetic request holding one lifecycle tip and one Release 035 revision
lineage anchored to it:

```bash
neuruh-effective-canonical-state-resolver resolve  examples/resolve.request.synthetic.json
neuruh-effective-canonical-state-resolver validate examples/resolution.synthetic.json
neuruh-effective-canonical-state-resolver digest   examples/resolution.synthetic.json
```

`resolve` prints the full resolution. `validate` prints the summary line:

```text
{"effective_source": "revision_tip", "effective_stage": "pilot", "effective_state_digest": "sha256:4a736ede8df2d2464e774214f5e925c36dab43052c589afc138c46dc52d475ca", "mutation_authority": false, "ok": true, "reason_code": "OK", "resolution_status": "resolved"}
sha256:4d0527d481753d2307756fa50b7b81c526f5670a20ca5d24024d6f54dc1be976
```

The lineage in that request is the same fixture Release 035 ships, so the two components can be
checked against each other: the resolver's `lineage_classifications[0].lineage_digest` equals
`neuruh-canonical-state-revision-ledger digest examples/lineage.synthetic.jsonl`
(`sha256:82ba56a7198a60a91662900ac7a02d9dbadb4a86648791070847aed5fbc5e8ce`), and both report the
same `effective_state_digest`.

`examples/build_synthetic.py` regenerates the fixtures from scratch.

## API

| Name | Purpose |
| --- | --- |
| `resolve(*, target_id, lifecycle_tips, revision_lineages=())` | Derive one `EffectiveCanonicalResolution`, or classify it `ambiguous`. |
| `verify_revision_lineage(entries)` | Re-verify one Release 035 lineage; returns a `VerifiedLineage`. |
| `verify_resolution(resolution, **expected)` | Check a resolution against expected field values. |
| `EffectiveCanonicalResolution` | The projection, including source digests and the hard-coded authority flags. |
| `LifecycleTipClaim` | One Release 026 lifecycle tip claim. |
| `VerifiedLineage` | Anchor, entry hashes, effective state digest, and lineage digest. |
| `EffectiveResolutionError` | Raised for structurally invalid evidence. |
| `SCHEMA_VERSION`, `RESOLUTION_STATUSES`, `REASON_CODES`, `CLASSIFICATIONS`, `SOURCES`, `STAGES` | Declared vocabulary. |
| `canonical_json(value)`, `sha256_ref(value)` | Deterministic serialization and hashing helpers. |

The resolution schema is published at
[`schema/effective-canonical-resolution.v0.1.schema.json`](schema/effective-canonical-resolution.v0.1.schema.json).

## Test

```bash
python -m unittest discover -s tests -v
```

## 036 is a resolver, not an authority

036 hard-codes every authority flag false. It does not deploy, execute, repair reality, change lifecycle state, change canonical truth, grant authority, or contact any private production system. Its output surfaces the exact source digests used (`lifecycle_tip_digest`, `revision_tip_hash`, `evidence_digest`) so any consumer can independently re-derive the same truth.

## Safety boundary

The resolver reads evidence and returns a projection. It has no authority flags set, holds no
credentials, contacts no service, and cannot change lifecycle state or canonical truth. A
`resolved` answer means the supplied evidence determines exactly one effective state — it is not
a statement that the evidence is complete, or that reality matches it. Feeding the resolver
partial evidence yields an `ambiguous` result, never a guess.

Only synthetic fixtures ship here; no production lifecycle ledgers, revision history, or state
store. See [`PUBLIC_PRIVATE_BOUNDARY.md`](PUBLIC_PRIVATE_BOUNDARY.md),
[`ARCHITECTURE.md`](ARCHITECTURE.md), [`SECURITY.md`](SECURITY.md), and the
[Neuruh Public Commons boundary](https://github.com/NeuruhAI/public-commons/blob/main/PUBLIC_PRIVATE_BOUNDARY.md).

## License

Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
