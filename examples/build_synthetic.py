"""Build the synthetic example resolve input/output. Synthetic fixtures only."""
import json
from hashlib import sha256
from pathlib import Path
from neuruh_effective_canonical_state_resolver import canonical_json, resolve, sha256_ref

H = sha256_ref
ANCHOR = H("synthetic-lifecycle-entry-A")

def entry(**over):
    d = dict(
        schema_version="neuruh.canonical-state-revision-ledger.v0.1",
        ledger_id="canonical-revision",
        revision_id="synthetic-rev-1",
        sequence=0,
        target_id="synthetic-target",
        lifecycle_anchor_digest=ANCHOR,
        anchor_stage="pilot",
        anchor_state_digest=H("synthetic-canonical-0"),
        revision_authorization_digest=H("synthetic-authorization-1"),
        revision_receipt_digest=H("synthetic-receipt-1"),
        revision_mode="adopt_observed",
        receipt_status="succeeded",
        from_canonical_state_digest=H("synthetic-canonical-0"),
        to_canonical_state_digest=H("synthetic-canonical-1"),
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
    body = {k: v for k, v in d.items() if k != "entry_hash"}
    d["entry_hash"] = sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return d

request = {
    "target_id": "synthetic-target",
    "lifecycle_tips": [{
        "lifecycle_entry_digest": ANCHOR,
        "stage": "pilot",
        "state_digest": H("synthetic-canonical-0"),
        "sequence": 2,
        "target_id": "synthetic-target",
    }],
    "revision_lineages": [[entry()]],
}

resolution = resolve(**request)
here = Path(__file__).parent
(here / "resolve.request.synthetic.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n")
(here / "resolution.synthetic.json").write_text(json.dumps(resolution.to_dict(), indent=2, sort_keys=True) + "\n")
print(resolution.resolution_digest)
