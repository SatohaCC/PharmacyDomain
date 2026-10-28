"""Applicationのmanagementを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.domain.store.entities import StoreManagerAssignment


@dataclass(frozen=True, kw_only=True)
class ManagerAssignmentDto:
    """任命履歴の公開値。"""

    id: str
    corporate_id: str
    store_id: str
    staff_id: str
    starts_on: date
    ends_on: date | None
    status: str

    @classmethod
    def from_entity(cls, assignment: StoreManagerAssignment) -> ManagerAssignmentDto:
        """集約の期間と参照を公開値へ変換する。"""
        return cls(
            id=str(assignment.id.value),
            corporate_id=str(assignment.corporate_id.value),
            store_id=str(assignment.store_id.value),
            staff_id=str(assignment.staff_id.value),
            starts_on=assignment.period.starts_on,
            ends_on=assignment.period.ends_on,
            status=assignment.status.value,
        )
