"""MedicationHistoryの参照境界を各Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from app.application.composition.reference_support import load_store_in_corporate
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
)
from app.application.medication_history.reference import (
    DispensingReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class MedicationHistoryStoreReferenceAdapter(StoreReferenceBoundary):
    """店舗の存在と法人境界だけを確認し、店舗集約は渡さない。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を、存在を隠す404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store is None:
            raise MedicationHistoryStoreNotFoundError()


class DispensingSourceAdapter(DispensingReferenceBoundary):
    """調剤セッション集約を取り出す。

    ここだけは他コンテキストの集約そのものを返す。法人・患者・店舗の一致は
    IDでは判定できず、Domain Service が本物の集約を必要とするため。
    """

    def __init__(self, repository: DispensingProcessRepository) -> None:
        self._repository = repository

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess:
        """未存在・別法人の調剤セッションを、存在を隠す404相当へ畳む。"""
        process = await self._repository.get(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
        )
        if process is None:
            raise MedicationHistoryDispensingNotFoundError()
        return process


class CounselorQualificationAdapter(StaffQualificationBoundary):
    """スタッフの保有資格だけを取り出し、Staff集約は渡さない。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """未存在・別法人のスタッフを404相当へ畳み、資格をそのまま返す。

        薬剤師かどうかの判定は ``CounselorQualificationService`` の責務であり、
        ここでは行わない。資格が空でも在籍しているので例外にしない。
        """
        staff = await self._repository.get(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        if staff is None:
            raise MedicationHistoryStaffNotFoundError()
        return staff.qualifications
