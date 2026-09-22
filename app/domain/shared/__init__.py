"""所有者のいない語彙と複数コンテキストで共有する規則（Shared Kernel）。"""

from app.domain.shared.preservation import (
    OverlappingPreservationPolicyError,
    PreservationPolicy,
    PreservationPolicyCatalog,
    PreservationPolicyNotFoundError,
    PreservationPolicyPeriodInvertedError,
    RetentionYears,
)

__all__ = [
    "OverlappingPreservationPolicyError",
    "PreservationPolicy",
    "PreservationPolicyCatalog",
    "PreservationPolicyNotFoundError",
    "PreservationPolicyPeriodInvertedError",
    "RetentionYears",
]
