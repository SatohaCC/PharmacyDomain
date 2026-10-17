"""管理薬剤師任命の集約間整合性を確認する。"""

from app.domain.store.lifecycle import StoreStatus
from app.domain.store.manager_assignment import StoreManagerAssignment
from app.domain.store.manager_repository import ManagerAssignmentConflictError
from app.domain.store.manager_source import ManagerStaffSource
from app.domain.store.store import Store


class StoreManagerAssignmentService:
    """任命対象の法人・資格・所属期間を検証する。"""

    def ensure_assignable(
        self,
        assignment: StoreManagerAssignment,
        *,
        store: Store,
        staff: ManagerStaffSource,
    ) -> None:
        """同じ法人の所属・資格が任命を満たすことを要求する。"""
        if (
            assignment.corporate_id != store.corporate_id
            or assignment.corporate_id != staff.corporate_id
            or assignment.store_id != store.id
            or assignment.staff_id != staff.staff_id
        ):
            raise ManagerAssignmentConflictError(
                "任命の法人・店舗・スタッフが一致しません。"
            )
        if (
            store.status == StoreStatus.CLOSED
            or not staff.staff_is_active
            or not staff.has_pharmacist
        ):
            raise ManagerAssignmentConflictError(
                "閉局店舗、退職者、薬剤師資格のないスタッフには任命できません。"
            )
        period = assignment.period
        if not any(
            affiliation.store_id == store.id
            and affiliation.starts_on <= period.starts_on
            and (
                affiliation.ends_on is None
                or (
                    period.ends_on is not None and period.ends_on <= affiliation.ends_on
                )
            )
            for affiliation in staff.affiliations
        ):
            raise ManagerAssignmentConflictError(
                "任命期間の全体を含む店舗所属が必要です。"
            )
