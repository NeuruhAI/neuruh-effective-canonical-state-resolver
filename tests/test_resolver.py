import unittest
from neuruh_effective_canonical_state_resolver import *

H = sha256_ref
TIP_A = H("lifecycle-entry-A")
TIP_B = H("lifecycle-entry-B")
S0 = H("canonical-state-0")
S1 = H("canonical-state-1")
S2 = H("canonical-state-2")
SB = H("canonical-state-B")

def tip(**over):
    d = dict(lifecycle_entry_digest=TIP_A, stage="pilot", state_digest=S0, sequence=3, target_id="t1")
    d.update(over)
    return d

def entry(**over):
    d = dict(
        schema_version="neuruh.canonical-state-revision-ledger.v0.1",
        ledger_id="canonical-revision",
        revision_id="rev-1",
        sequence=0,
        target_id="t1",
        lifecycle_anchor_digest=TIP_A,
        anchor_stage="pilot",
        anchor_state_digest=S0,
        revision_authorization_digest=H("auth-1"),
        revision_receipt_digest=H("receipt-1"),
        revision_mode="adopt_observed",
        receipt_status="succeeded",
        from_canonical_state_digest=S0,
        to_canonical_state_digest=S1,
        recorded_at="2026-08-10T12:00:00Z",
        previous_entry_hash=None,
        lifecycle_ledger_mutated=False,
        lifecycle_transition_authority=False,
        canonical_state_revision_authority=False,
        canonical_state_authority=False,
        execution_authority=False,
        deployment_authority=False,
        reconciliation_authority=False,
        mutation_authority=False,
    )
    d.update(over)
    from hashlib import sha256 as _s
    body = {k: v for k, v in d.items() if k != "entry_hash"}
    d["entry_hash"] = _s(canonical_json(body).encode("utf-8")).hexdigest()
    return d

def chain(*states, anchor=TIP_A, anchor_stage="pilot", anchor_state=S0, suffix=""):
    rows = []
    prev_hash = None
    prev_state = anchor_state
    for i, to_state in enumerate(states):
        rows.append(entry(
            revision_id=f"rev-{suffix}{i + 1}",
            sequence=i,
            lifecycle_anchor_digest=anchor,
            anchor_stage=anchor_stage,
            anchor_state_digest=anchor_state,
            revision_authorization_digest=H(f"auth-{suffix}{i + 1}"),
            revision_receipt_digest=H(f"receipt-{suffix}{i + 1}"),
            from_canonical_state_digest=prev_state,
            to_canonical_state_digest=to_state,
            recorded_at=f"2026-08-10T12:0{i}:00Z",
            previous_entry_hash=prev_hash,
        ))
        prev_hash = rows[-1]["entry_hash"]
        prev_state = to_state
    return rows

class T(unittest.TestCase):
    def bad(self, fn):
        with self.assertRaises(EffectiveResolutionError):
            fn()

    # -- precedence rule
    def test_no_lineage_resolves_lifecycle_tip(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip()])
        self.assertEqual(r.resolution_status, "resolved")
        self.assertEqual(r.effective_source, "lifecycle_tip")
        self.assertEqual(r.effective_stage, "pilot")
        self.assertEqual(r.effective_state_digest, S0)
        self.assertEqual(r.lifecycle_tip_digest, TIP_A)
        self.assertIsNone(r.revision_tip_hash)
        self.assertEqual(r.applied_revision_count, 0)

    def test_anchored_lineage_resolves_revision_tip(self):
        rows = chain(S1, S2)
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows])
        self.assertEqual(r.resolution_status, "resolved")
        self.assertEqual(r.effective_source, "revision_tip")
        self.assertEqual(r.effective_stage, "pilot")
        self.assertEqual(r.effective_state_digest, S2)
        self.assertEqual(r.revision_tip_hash, rows[-1]["entry_hash"])
        self.assertEqual(r.applied_revision_count, 2)
        self.assertEqual(r.lineage_classifications[0]["classification"], "applied")

    # -- supersession rule
    def test_newer_tip_supersedes_stale_anchor(self):
        rows = chain(S1)
        r = resolve(
            target_id="t1",
            lifecycle_tips=[tip(lifecycle_entry_digest=TIP_B, stage="production", state_digest=SB, sequence=4)],
            revision_lineages=[rows],
        )
        self.assertEqual(r.resolution_status, "resolved")
        self.assertEqual(r.effective_source, "lifecycle_tip")
        self.assertEqual(r.effective_stage, "production")
        self.assertEqual(r.effective_state_digest, SB)
        self.assertEqual(r.applied_revision_count, 0)
        self.assertEqual(r.lineage_classifications[0]["classification"], "superseded_stale_anchor")

    def test_b_anchored_lineage_wins_over_stale_a(self):
        stale = chain(S1)
        fresh = chain(H("canonical-state-B2"), anchor=TIP_B, anchor_stage="production", anchor_state=SB, suffix="b")
        r = resolve(
            target_id="t1",
            lifecycle_tips=[tip(lifecycle_entry_digest=TIP_B, stage="production", state_digest=SB, sequence=4)],
            revision_lineages=[stale, fresh],
        )
        self.assertEqual(r.effective_source, "revision_tip")
        self.assertEqual(r.effective_state_digest, H("canonical-state-B2"))
        labels = {c["lineage_digest"]: c["classification"] for c in r.lineage_classifications}
        self.assertIn("superseded_stale_anchor", labels.values())
        self.assertIn("applied", labels.values())

    # -- determinism
    def test_deterministic_replay(self):
        rows = chain(S1, S2)
        a = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows])
        b = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows])
        self.assertEqual(a.resolution_digest, b.resolution_digest)

    def test_order_independent(self):
        stale = chain(S1)
        fresh = chain(H("canonical-state-B2"), anchor=TIP_B, anchor_stage="production", anchor_state=SB, suffix="b")
        t = tip(lifecycle_entry_digest=TIP_B, stage="production", state_digest=SB, sequence=4)
        a = resolve(target_id="t1", lifecycle_tips=[t], revision_lineages=[stale, fresh])
        b = resolve(target_id="t1", lifecycle_tips=[t], revision_lineages=[fresh, stale])
        self.assertEqual(a.resolution_digest, b.resolution_digest)

    def test_duplicate_lineage_deduped(self):
        rows = chain(S1)
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows, rows])
        self.assertEqual(r.resolution_status, "resolved")
        self.assertEqual(len(r.lineage_classifications), 1)

    def test_prefix_lineage_merged_not_forked(self):
        rows = chain(S1, S2)
        prefix = rows[:1]
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows, prefix])
        self.assertEqual(r.resolution_status, "resolved")
        self.assertEqual(r.effective_state_digest, S2)
        self.assertEqual(r.applied_revision_count, 2)

    def test_roundtrip(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[chain(S1)])
        self.assertEqual(EffectiveCanonicalResolution.from_mapping(r.to_dict()), r)

    # -- fail-closed ambiguity
    def test_missing_evidence_ambiguous(self):
        r = resolve(target_id="t1", lifecycle_tips=[])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "MISSING_LIFECYCLE_EVIDENCE")
        self.assertIsNone(r.effective_state_digest)
        self.assertIsNone(r.effective_stage)
        self.assertIsNone(r.effective_source)

    def test_competing_tips_ambiguous(self):
        r = resolve(target_id="t1", lifecycle_tips=[
            tip(),
            tip(lifecycle_entry_digest=TIP_B, stage="production", state_digest=SB, sequence=4),
        ])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "AMBIGUOUS_COMPETING_TIPS")

    def test_same_digest_conflicting_content_ambiguous(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip(), tip(state_digest=S1)])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "AMBIGUOUS_COMPETING_TIPS")

    def test_identical_tips_deduped(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip(), tip()])
        self.assertEqual(r.resolution_status, "resolved")

    def test_forked_lineage_ambiguous(self):
        a = chain(S1, S2)
        b = chain(S1, H("canonical-state-2b"))
        b[1]["revision_id"] = "rev-2b"
        b_fixed = [b[0], entry(
            revision_id="rev-2b",
            sequence=1,
            revision_authorization_digest=H("auth-2b"),
            revision_receipt_digest=H("receipt-2b"),
            from_canonical_state_digest=S1,
            to_canonical_state_digest=H("canonical-state-2b"),
            recorded_at="2026-08-10T12:01:00Z",
            previous_entry_hash=b[0]["entry_hash"],
        )]
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[a, b_fixed])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "FORKED_REVISION_LINEAGE")
        self.assertTrue(all(
            c["classification"] == "forked_conflict" for c in r.lineage_classifications
        ))

    def test_anchor_content_mismatch_ambiguous(self):
        rows = chain(S1, anchor_state=H("wrong-anchor-state"))
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "LIFECYCLE_ANCHOR_CONTENT_MISMATCH")

    def test_anchor_stage_mismatch_ambiguous(self):
        rows = chain(S1, anchor_stage="canary")
        r = resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows])
        self.assertEqual(r.resolution_status, "ambiguous")
        self.assertEqual(r.reason_code, "LIFECYCLE_ANCHOR_CONTENT_MISMATCH")

    # -- structural rejection (raise)
    def test_broken_chain_rejected(self):
        rows = chain(S1, S2)
        rows[1]["previous_entry_hash"] = "0" * 64
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_tampered_entry_rejected(self):
        rows = chain(S1)
        rows[0]["to_canonical_state_digest"] = H("forged")
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_failed_receipt_rejected(self):
        rows = chain(S1)
        rows[0]["receipt_status"] = "failed"
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_duplicate_receipt_rejected(self):
        rows = chain(S1, S2)
        forged = entry(
            revision_id="rev-2",
            sequence=1,
            revision_authorization_digest=H("auth-2"),
            revision_receipt_digest=H("receipt-1"),
            from_canonical_state_digest=S1,
            to_canonical_state_digest=S2,
            recorded_at="2026-08-10T12:01:00Z",
            previous_entry_hash=rows[0]["entry_hash"],
        )
        self.bad(lambda: resolve(
            target_id="t1", lifecycle_tips=[tip()], revision_lineages=[[rows[0], forged]],
        ))

    def test_wrong_predecessor_rejected(self):
        rows = chain(S1, S2)
        forged = entry(
            revision_id="rev-2",
            sequence=1,
            revision_authorization_digest=H("auth-2"),
            revision_receipt_digest=H("receipt-2"),
            from_canonical_state_digest=S0,
            to_canonical_state_digest=S2,
            recorded_at="2026-08-10T12:01:00Z",
            previous_entry_hash=rows[0]["entry_hash"],
        )
        self.bad(lambda: resolve(
            target_id="t1", lifecycle_tips=[tip()], revision_lineages=[[rows[0], forged]],
        ))

    def test_cross_stage_entry_rejected(self):
        rows = chain(S1)
        rows[0]["anchor_stage"] = "warp"
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_authority_claim_rejected(self):
        rows = chain(S1)
        rows[0]["mutation_authority"] = True
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_unknown_field_rejected(self):
        rows = chain(S1)
        rows[0]["deploy_now"] = True
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[rows]))

    def test_wrong_target_lineage_rejected(self):
        rows = chain(S1)
        self.bad(lambda: resolve(target_id="other", lifecycle_tips=[tip(target_id="other")], revision_lineages=[rows]))

    def test_wrong_target_tip_rejected(self):
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip(target_id="other")]))

    def test_empty_lineage_rejected(self):
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[tip()], revision_lineages=[[]]))

    def test_malformed_tip_rejected(self):
        self.bad(lambda: resolve(target_id="t1", lifecycle_tips=[{"lifecycle_entry_digest": "bad"}]))

    # -- resolution object is projection, not power
    def test_no_authority_flags(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip()])
        self.assertFalse(r.lifecycle_ledger_mutated)
        self.assertFalse(r.lifecycle_transition_authority)
        self.assertFalse(r.canonical_state_revision_authority)
        self.assertFalse(r.canonical_state_authority)
        self.assertFalse(r.execution_authority)
        self.assertFalse(r.deployment_authority)
        self.assertFalse(r.reconciliation_authority)
        self.assertFalse(r.mutation_authority)

    def test_authority_claim_on_resolution_rejected(self):
        x = resolve(target_id="t1", lifecycle_tips=[tip()]).to_dict()
        x["mutation_authority"] = True
        self.bad(lambda: EffectiveCanonicalResolution.from_mapping(x))

    def test_tampered_resolution_rejected(self):
        x = resolve(target_id="t1", lifecycle_tips=[tip()]).to_dict()
        x["effective_state_digest"] = S2
        self.bad(lambda: EffectiveCanonicalResolution.from_mapping(x))

    def test_ambiguous_cannot_claim_truth(self):
        x = resolve(target_id="t1", lifecycle_tips=[]).to_dict()
        x["effective_state_digest"] = S1
        self.bad(lambda: EffectiveCanonicalResolution.from_mapping(x))

    def test_verify_resolution(self):
        r = resolve(target_id="t1", lifecycle_tips=[tip()])
        self.assertTrue(verify_resolution(r, effective_state_digest=S0, effective_source="lifecycle_tip"))
        self.bad(lambda: verify_resolution(r, effective_state_digest=S1))

if __name__ == "__main__":
    unittest.main()
