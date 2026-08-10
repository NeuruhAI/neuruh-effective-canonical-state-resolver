from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json, re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "neuruh.effective-canonical-state-resolver.v0.1"
REVISION_LEDGER_SCHEMA_VERSION = "neuruh.canonical-state-revision-ledger.v0.1"
STAGES = ("sandbox", "canary", "pilot", "production")
REVISION_MODE = "adopt_observed"
REQUIRED_RECEIPT_STATUS = "succeeded"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

RESOLUTION_STATUSES = ("resolved", "ambiguous")
REASON_CODES = (
    "OK",
    "MISSING_LIFECYCLE_EVIDENCE",
    "AMBIGUOUS_COMPETING_TIPS",
    "FORKED_REVISION_LINEAGE",
    "LIFECYCLE_ANCHOR_CONTENT_MISMATCH",
)
SOURCES = ("lifecycle_tip", "revision_tip")
CLASSIFICATIONS = (
    "applied",
    "superseded_stale_anchor",
    "forked_conflict",
    "anchor_content_mismatch",
    "not_evaluated",
)

class EffectiveResolutionError(ValueError):
    """Fail-closed refusal for malformed, tampered, contradictory, or out-of-contract resolution evidence."""

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

def sha256_ref(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return "sha256:" + sha256(value).hexdigest()

def _nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EffectiveResolutionError(f"{name} must be a non-empty string")
    return value

def _sha(value: Any, name: str) -> str:
    value = _nonempty(value, name)
    if not value.startswith("sha256:") or not HEX64.fullmatch(value[7:]):
        raise EffectiveResolutionError(f"{name} must be sha256:<64 lowercase hex>")
    return value

def _hash64(value: Any, name: str) -> str:
    value = _nonempty(value, name)
    if not HEX64.fullmatch(value):
        raise EffectiveResolutionError(f"{name} must be 64 lowercase hex")
    return value

def _time(value: Any, name: str) -> datetime:
    value = _nonempty(value, name)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EffectiveResolutionError(f"{name} must be RFC3339/ISO-8601") from exc
    if dt.tzinfo is None:
        raise EffectiveResolutionError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc)

def _keys(raw: Mapping[str, Any], required: set[str], context: str) -> None:
    missing = sorted(required - set(raw))
    unknown = sorted(set(raw) - required)
    if missing:
        raise EffectiveResolutionError(f"{context} missing required field(s): {', '.join(missing)}")
    if unknown:
        raise EffectiveResolutionError(f"{context} contains unknown field(s): {', '.join(unknown)}")

# --------------------------------------------------------------------------
# Bounded input: one claimed current Release 026 lifecycle tip.
# --------------------------------------------------------------------------

TIP_CLAIM_FIELDS = {
    "lifecycle_entry_digest", "stage", "state_digest", "sequence", "target_id",
}

@dataclass(frozen=True)
class LifecycleTipClaim:
    lifecycle_entry_digest: str
    stage: str
    state_digest: str
    sequence: int
    target_id: str

    def validate(self) -> None:
        _sha(self.lifecycle_entry_digest, "lifecycle_entry_digest")
        _sha(self.state_digest, "state_digest")
        _nonempty(self.target_id, "target_id")
        if self.stage not in STAGES:
            raise EffectiveResolutionError("stage must be a known lifecycle stage")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise EffectiveResolutionError("sequence must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "lifecycle_entry_digest": self.lifecycle_entry_digest,
            "stage": self.stage,
            "state_digest": self.state_digest,
            "sequence": self.sequence,
            "target_id": self.target_id,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LifecycleTipClaim":
        _keys(raw, TIP_CLAIM_FIELDS, "lifecycle tip claim")
        obj = cls(**{k: raw[k] for k in TIP_CLAIM_FIELDS})
        obj.validate()
        return obj

# --------------------------------------------------------------------------
# Bounded input: a Release 035 revision lineage, independently re-verified.
# The resolver trusts no producer: chain, threading, anchoring, consumption
# uniqueness and content hashes are all rechecked here against the exact
# Release 035 v0.1 schema.
# --------------------------------------------------------------------------

REVISION_ENTRY_FIELDS = {
    "schema_version", "ledger_id", "revision_id", "sequence", "target_id",
    "lifecycle_anchor_digest", "anchor_stage", "anchor_state_digest",
    "revision_authorization_digest", "revision_receipt_digest", "revision_mode", "receipt_status",
    "from_canonical_state_digest", "to_canonical_state_digest", "recorded_at",
    "previous_entry_hash", "lifecycle_ledger_mutated", "lifecycle_transition_authority",
    "canonical_state_revision_authority", "canonical_state_authority", "execution_authority",
    "deployment_authority", "reconciliation_authority", "mutation_authority", "entry_hash",
}

def _revision_entry_body(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {k: raw[k] for k in REVISION_ENTRY_FIELDS if k != "entry_hash"}

def _verify_revision_entry(raw: Mapping[str, Any], line: int) -> None:
    ctx = f"revision entry {line}"
    _keys(raw, REVISION_ENTRY_FIELDS, ctx)
    if raw["schema_version"] != REVISION_LEDGER_SCHEMA_VERSION:
        raise EffectiveResolutionError(f"{ctx}: unsupported revision-ledger schema_version")
    for name in ("ledger_id", "revision_id", "target_id"):
        _nonempty(raw[name], f"{ctx}.{name}")
    for name in (
        "lifecycle_anchor_digest", "anchor_state_digest", "revision_authorization_digest",
        "revision_receipt_digest", "from_canonical_state_digest", "to_canonical_state_digest",
    ):
        _sha(raw[name], f"{ctx}.{name}")
    if raw["anchor_stage"] not in STAGES:
        raise EffectiveResolutionError(f"{ctx}: cross-stage or unknown anchor_stage")
    if raw["revision_mode"] != REVISION_MODE:
        raise EffectiveResolutionError(f"{ctx}: invalid revision_mode")
    if raw["receipt_status"] != REQUIRED_RECEIPT_STATUS:
        raise EffectiveResolutionError(f"{ctx}: failed or invalid receipt cannot appear in revision lineage")
    if raw["from_canonical_state_digest"] == raw["to_canonical_state_digest"]:
        raise EffectiveResolutionError(f"{ctx}: revision must change canonical state")
    _time(raw["recorded_at"], f"{ctx}.recorded_at")
    seq = raw["sequence"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise EffectiveResolutionError(f"{ctx}: sequence must be a non-negative integer")
    for name in (
        "lifecycle_ledger_mutated", "lifecycle_transition_authority",
        "canonical_state_revision_authority", "canonical_state_authority",
        "execution_authority", "deployment_authority", "reconciliation_authority",
        "mutation_authority",
    ):
        if raw[name] is not False:
            raise EffectiveResolutionError(f"{ctx}: revision lineage cannot carry authority ({name})")
    _hash64(raw["entry_hash"], f"{ctx}.entry_hash")
    calculated = sha256(canonical_json(_revision_entry_body(raw)).encode("utf-8")).hexdigest()
    if raw["entry_hash"] != calculated:
        raise EffectiveResolutionError(f"{ctx}: entry_hash mismatch (tampered revision entry)")

@dataclass(frozen=True)
class VerifiedLineage:
    anchor_digest: str
    anchor_stage: str
    anchor_state_digest: str
    target_id: str
    entry_hashes: tuple[str, ...]
    effective_state_digest: str
    lineage_digest: str

def verify_revision_lineage(entries: Sequence[Mapping[str, Any]]) -> VerifiedLineage:
    if not entries:
        raise EffectiveResolutionError("revision lineage cannot be empty")
    rows = [dict(e) for e in entries]
    for i, raw in enumerate(rows):
        _verify_revision_entry(raw, i)

    if len({r["ledger_id"] for r in rows}) != 1:
        raise EffectiveResolutionError("revision lineage ledger_id must remain constant")
    if len({r["target_id"] for r in rows}) != 1:
        raise EffectiveResolutionError("revision lineage target_id must remain constant")
    anchors = {(r["lifecycle_anchor_digest"], r["anchor_stage"], r["anchor_state_digest"]) for r in rows}
    if len(anchors) != 1:
        raise EffectiveResolutionError("revision lineage is bound to exactly one lifecycle anchor")
    if [r["sequence"] for r in rows] != list(range(len(rows))):
        raise EffectiveResolutionError("revision lineage sequence must be contiguous from zero")

    ids = [r["revision_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise EffectiveResolutionError("revision_id values must be unique")
    receipts = [r["revision_receipt_digest"] for r in rows]
    if len(receipts) != len(set(receipts)):
        raise EffectiveResolutionError("duplicate revision receipt consumption in lineage")
    authorizations = [r["revision_authorization_digest"] for r in rows]
    if len(authorizations) != len(set(authorizations)):
        raise EffectiveResolutionError("duplicate revision authorization use in lineage")

    for i, raw in enumerate(rows):
        expected_previous = None if i == 0 else rows[i - 1]["entry_hash"]
        if raw["previous_entry_hash"] != expected_previous:
            raise EffectiveResolutionError("broken previous_entry_hash chain in revision lineage")
        expected_from = raw["anchor_state_digest"] if i == 0 else rows[i - 1]["to_canonical_state_digest"]
        if raw["from_canonical_state_digest"] != expected_from:
            raise EffectiveResolutionError("revision does not begin from the previous effective canonical state")
        if i > 0 and _time(raw["recorded_at"], "recorded_at") < _time(rows[i - 1]["recorded_at"], "previous recorded_at"):
            raise EffectiveResolutionError("revision records must be non-decreasing in time")

    head = rows[0]
    return VerifiedLineage(
        anchor_digest=head["lifecycle_anchor_digest"],
        anchor_stage=head["anchor_stage"],
        anchor_state_digest=head["anchor_state_digest"],
        target_id=head["target_id"],
        entry_hashes=tuple(r["entry_hash"] for r in rows),
        effective_state_digest=rows[-1]["to_canonical_state_digest"],
        lineage_digest=sha256_ref(canonical_json(rows)),
    )

# --------------------------------------------------------------------------
# Resolution output: a sealed, content-bound, authority-free projection.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EffectiveCanonicalResolution:
    target_id: str
    resolution_status: str
    reason_code: str
    effective_source: str | None
    effective_stage: str | None
    effective_state_digest: str | None
    lifecycle_tip_digest: str | None
    revision_tip_hash: str | None
    applied_revision_count: int
    lineage_classifications: tuple[Mapping[str, str], ...]
    evidence_digest: str

    lifecycle_ledger_mutated: bool = False
    lifecycle_transition_authority: bool = False
    canonical_state_revision_authority: bool = False
    canonical_state_authority: bool = False
    execution_authority: bool = False
    deployment_authority: bool = False
    reconciliation_authority: bool = False
    mutation_authority: bool = False
    resolution_digest: str | None = None

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "target_id": self.target_id,
            "resolution_status": self.resolution_status,
            "reason_code": self.reason_code,
            "effective_source": self.effective_source,
            "effective_stage": self.effective_stage,
            "effective_state_digest": self.effective_state_digest,
            "lifecycle_tip_digest": self.lifecycle_tip_digest,
            "revision_tip_hash": self.revision_tip_hash,
            "applied_revision_count": self.applied_revision_count,
            "lineage_classifications": [dict(c) for c in self.lineage_classifications],
            "evidence_digest": self.evidence_digest,
            "lifecycle_ledger_mutated": False,
            "lifecycle_transition_authority": False,
            "canonical_state_revision_authority": False,
            "canonical_state_authority": False,
            "execution_authority": False,
            "deployment_authority": False,
            "reconciliation_authority": False,
            "mutation_authority": False,
        }

    def calculated_digest(self) -> str:
        return sha256_ref(canonical_json(self.body_dict()))

    def validate(self, *, check_digest: bool = True) -> None:
        _nonempty(self.target_id, "target_id")
        _sha(self.evidence_digest, "evidence_digest")
        if self.resolution_status not in RESOLUTION_STATUSES:
            raise EffectiveResolutionError("unknown resolution_status")
        if self.reason_code not in REASON_CODES:
            raise EffectiveResolutionError("unknown reason_code")
        if isinstance(self.applied_revision_count, bool) or not isinstance(self.applied_revision_count, int) \
                or self.applied_revision_count < 0:
            raise EffectiveResolutionError("applied_revision_count must be a non-negative integer")

        for c in self.lineage_classifications:
            if set(c) != {"lineage_digest", "anchor_digest", "classification"}:
                raise EffectiveResolutionError("malformed lineage classification")
            _sha(c["lineage_digest"], "lineage_digest")
            _sha(c["anchor_digest"], "anchor_digest")
            if c["classification"] not in CLASSIFICATIONS:
                raise EffectiveResolutionError("unknown lineage classification")

        if self.resolution_status == "resolved":
            if self.reason_code != "OK":
                raise EffectiveResolutionError("resolved resolution must carry reason_code OK")
            if self.effective_source not in SOURCES:
                raise EffectiveResolutionError("resolved resolution requires an effective source")
            if self.effective_stage not in STAGES:
                raise EffectiveResolutionError("resolved resolution requires a known effective stage")
            _sha(self.effective_state_digest, "effective_state_digest")
            _sha(self.lifecycle_tip_digest, "lifecycle_tip_digest")
            if self.effective_source == "revision_tip":
                _hash64(self.revision_tip_hash, "revision_tip_hash")
                if self.applied_revision_count < 1:
                    raise EffectiveResolutionError("revision-derived truth requires applied revisions")
            else:
                if self.revision_tip_hash is not None:
                    raise EffectiveResolutionError("lifecycle-tip truth cannot cite a revision tip")
                if self.applied_revision_count != 0:
                    raise EffectiveResolutionError("lifecycle-tip truth cannot count applied revisions")
        else:
            if self.reason_code == "OK":
                raise EffectiveResolutionError("ambiguous resolution requires a failure reason")
            if any(v is not None for v in (
                self.effective_source, self.effective_stage, self.effective_state_digest, self.revision_tip_hash,
            )):
                raise EffectiveResolutionError("ambiguous resolution cannot assert effective canonical truth")
            if self.applied_revision_count != 0:
                raise EffectiveResolutionError("ambiguous resolution cannot count applied revisions")

        for value, name in [
            (self.lifecycle_ledger_mutated, "lifecycle_ledger_mutated"),
            (self.lifecycle_transition_authority, "lifecycle_transition_authority"),
            (self.canonical_state_revision_authority, "canonical_state_revision_authority"),
            (self.canonical_state_authority, "canonical_state_authority"),
            (self.execution_authority, "execution_authority"),
            (self.deployment_authority, "deployment_authority"),
            (self.reconciliation_authority, "reconciliation_authority"),
            (self.mutation_authority, "mutation_authority"),
        ]:
            if value is not False:
                raise EffectiveResolutionError(f"resolution is a projection, not an authority: {name} must be false")

        if check_digest:
            _sha(self.resolution_digest, "resolution_digest")
            if self.resolution_digest != self.calculated_digest():
                raise EffectiveResolutionError("resolution_digest mismatch")

    def seal(self) -> "EffectiveCanonicalResolution":
        self.validate(check_digest=False)
        obj = EffectiveCanonicalResolution(**{
            **self.__dict__,
            "lifecycle_ledger_mutated": False,
            "lifecycle_transition_authority": False,
            "canonical_state_revision_authority": False,
            "canonical_state_authority": False,
            "execution_authority": False,
            "deployment_authority": False,
            "reconciliation_authority": False,
            "mutation_authority": False,
            "resolution_digest": None,
        })
        obj = EffectiveCanonicalResolution(**{**obj.__dict__, "resolution_digest": obj.calculated_digest()})
        obj.validate()
        return obj

    def to_dict(self) -> dict[str, Any]:
        obj = self.seal()
        out = obj.body_dict()
        out["resolution_digest"] = obj.resolution_digest
        return out

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EffectiveCanonicalResolution":
        required = set(cls.__dataclass_fields__) | {"schema_version"}
        if set(raw) != required:
            raise EffectiveResolutionError("unknown or missing fields")
        if raw["schema_version"] != SCHEMA_VERSION:
            raise EffectiveResolutionError("unsupported schema_version")
        fields = {k: raw[k] for k in cls.__dataclass_fields__}
        fields["lineage_classifications"] = tuple(dict(c) for c in fields["lineage_classifications"])
        obj = cls(**fields)
        obj.validate()
        return obj

# --------------------------------------------------------------------------
# Deterministic resolution.
# --------------------------------------------------------------------------

def _is_prefix(shorter: tuple[str, ...], longer: tuple[str, ...]) -> bool:
    return len(shorter) <= len(longer) and longer[: len(shorter)] == shorter

def resolve(
    *,
    target_id: str,
    lifecycle_tips: Sequence[Mapping[str, Any] | LifecycleTipClaim],
    revision_lineages: Sequence[Sequence[Mapping[str, Any]]] = (),
) -> EffectiveCanonicalResolution:
    _nonempty(target_id, "target_id")

    claims = []
    for raw in lifecycle_tips:
        claim = raw if isinstance(raw, LifecycleTipClaim) else LifecycleTipClaim.from_mapping(raw)
        claim.validate()
        if claim.target_id != target_id:
            raise EffectiveResolutionError("lifecycle tip claim is evidence for a different target")
        claims.append(claim)

    verified: list[VerifiedLineage] = []
    for entries in revision_lineages:
        lineage = verify_revision_lineage(entries)
        if lineage.target_id != target_id:
            raise EffectiveResolutionError("revision lineage is evidence for a different target")
        verified.append(lineage)

    # Content-bound identity of the exact evidence considered (order-independent).
    evidence_digest = sha256_ref(canonical_json({
        "target_id": target_id,
        "lifecycle_tips": sorted((c.to_dict() for c in claims), key=canonical_json),
        "revision_lineages": sorted(
            [[dict(e) for e in entries] for entries in revision_lineages],
            key=lambda rows: canonical_json(rows),
        ),
    }))

    # Deduplicate identical lineages; merge chains where one is a strict
    # prefix of another (same chain observed at different lengths).
    unique: dict[str, VerifiedLineage] = {}
    for lineage in verified:
        unique.setdefault(lineage.lineage_digest, lineage)
    merged: list[VerifiedLineage] = []
    for lineage in sorted(unique.values(), key=lambda v: -len(v.entry_hashes)):
        if any(
            kept.anchor_digest == lineage.anchor_digest and _is_prefix(lineage.entry_hashes, kept.entry_hashes)
            for kept in merged
        ):
            continue
        merged.append(lineage)
    merged.sort(key=lambda v: v.lineage_digest)

    def classifications(mapping: Mapping[str, str]) -> tuple[dict[str, str], ...]:
        return tuple(
            {"lineage_digest": v.lineage_digest, "anchor_digest": v.anchor_digest,
             "classification": mapping.get(v.lineage_digest, "not_evaluated")}
            for v in merged
        )

    def ambiguous(reason: str, mapping: Mapping[str, str], tip_digest: str | None) -> EffectiveCanonicalResolution:
        return EffectiveCanonicalResolution(
            target_id=target_id,
            resolution_status="ambiguous",
            reason_code=reason,
            effective_source=None,
            effective_stage=None,
            effective_state_digest=None,
            lifecycle_tip_digest=tip_digest,
            revision_tip_hash=None,
            applied_revision_count=0,
            lineage_classifications=classifications(mapping),
            evidence_digest=evidence_digest,
        ).seal()

    distinct_tips = {c.to_dict()["lifecycle_entry_digest"]: c for c in claims}
    if not claims:
        return ambiguous("MISSING_LIFECYCLE_EVIDENCE", {}, None)
    if len({canonical_json(c.to_dict()) for c in claims}) > 1:
        return ambiguous("AMBIGUOUS_COMPETING_TIPS", {}, None)
    tip = next(iter(distinct_tips.values()))

    labels: dict[str, str] = {}
    current: list[VerifiedLineage] = []
    for lineage in merged:
        if lineage.anchor_digest != tip.lifecycle_entry_digest:
            labels[lineage.lineage_digest] = "superseded_stale_anchor"
        elif lineage.anchor_stage != tip.stage or lineage.anchor_state_digest != tip.state_digest:
            labels[lineage.lineage_digest] = "anchor_content_mismatch"
        else:
            current.append(lineage)

    if any(v == "anchor_content_mismatch" for v in labels.values()):
        return ambiguous("LIFECYCLE_ANCHOR_CONTENT_MISMATCH", labels, tip.lifecycle_entry_digest)

    if len(current) > 1:
        for lineage in current:
            labels[lineage.lineage_digest] = "forked_conflict"
        return ambiguous("FORKED_REVISION_LINEAGE", labels, tip.lifecycle_entry_digest)

    if current:
        applied = current[0]
        labels[applied.lineage_digest] = "applied"
        return EffectiveCanonicalResolution(
            target_id=target_id,
            resolution_status="resolved",
            reason_code="OK",
            effective_source="revision_tip",
            effective_stage=tip.stage,
            effective_state_digest=applied.effective_state_digest,
            lifecycle_tip_digest=tip.lifecycle_entry_digest,
            revision_tip_hash=applied.entry_hashes[-1],
            applied_revision_count=len(applied.entry_hashes),
            lineage_classifications=classifications(labels),
            evidence_digest=evidence_digest,
        ).seal()

    return EffectiveCanonicalResolution(
        target_id=target_id,
        resolution_status="resolved",
        reason_code="OK",
        effective_source="lifecycle_tip",
        effective_stage=tip.stage,
        effective_state_digest=tip.state_digest,
        lifecycle_tip_digest=tip.lifecycle_entry_digest,
        revision_tip_hash=None,
        applied_revision_count=0,
        lineage_classifications=classifications(labels),
        evidence_digest=evidence_digest,
    ).seal()

def verify_resolution(r: EffectiveCanonicalResolution, **expected) -> bool:
    r.validate()
    for field, value in expected.items():
        if not hasattr(r, field) or getattr(r, field) != value:
            raise EffectiveResolutionError(f"resolution binding mismatch: {field}")
    return True
