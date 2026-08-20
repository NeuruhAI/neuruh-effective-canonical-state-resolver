from importlib.metadata import PackageNotFoundError, version as _metadata_version

from .core import (
    CLASSIFICATIONS,
    REASON_CODES,
    REQUIRED_RECEIPT_STATUS,
    RESOLUTION_STATUSES,
    REVISION_LEDGER_SCHEMA_VERSION,
    REVISION_MODE,
    SCHEMA_VERSION,
    SOURCES,
    STAGES,
    EffectiveCanonicalResolution,
    EffectiveResolutionError,
    LifecycleTipClaim,
    VerifiedLineage,
    canonical_json,
    resolve,
    sha256_ref,
    verify_resolution,
    verify_revision_lineage,
)

__all__ = [
    "CLASSIFICATIONS",
    "REASON_CODES",
    "REQUIRED_RECEIPT_STATUS",
    "RESOLUTION_STATUSES",
    "REVISION_LEDGER_SCHEMA_VERSION",
    "REVISION_MODE",
    "SCHEMA_VERSION",
    "SOURCES",
    "STAGES",
    "EffectiveCanonicalResolution",
    "EffectiveResolutionError",
    "LifecycleTipClaim",
    "VerifiedLineage",
    "canonical_json",
    "resolve",
    "sha256_ref",
    "verify_resolution",
    "verify_revision_lineage",
]

try:
    __version__ = _metadata_version("neuruh-effective-canonical-state-resolver")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "unknown"
