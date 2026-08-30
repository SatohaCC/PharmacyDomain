"""Dispensingの参照境界を各Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from app.application.composition.reference_support import load_store_in_corporate
from app.application.dispensing.exceptions import (
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
)
from app.application.dispensing.reference import (
    PrescriptionCompletionBoundary,
    PrescriptionReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import PrescriptionId, PrescriptionStatus
from app.domain.prescription.repository import PrescriptionRepository
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


class DispensingStoreReferenceAdapter(StoreReferenceBoundary):
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
            raise DispensingStoreNotFoundError()


class PrescriptionSourceAdapter(
    PrescriptionReferenceBoundary, PrescriptionCompletionBoundary
):
    """処方箋Repositoryを包み、参照と調剤済への遷移の両方を提供する。

    2つのProtocolを1クラスで満たすのは、読みと書きが**同じ処方箋の同じ行**を
    指すからである。別インスタンスに分けると、読んだ世代を書き側が知らないまま
    保存することになり、楽観ロックの単位が割れる。
    """

    def __init__(self, repository: PrescriptionRepository) -> None:
        self._repository = repository

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription:
        """未存在・別法人の処方箋を、存在を隠す404相当へ畳む。"""
        prescription = await self._repository.get(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
        )
        if prescription is None:
            raise DispensingPrescriptionNotFoundError()
        return prescription

    async def complete_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> None:
        """処方箋を調剤済へ遷移させ、既に調剤済なら冪等に終了する。

        分割・リフィルの各回が同じ処方箋を完了しうるので、2回目以降を状態遷移
        エラーにしない。
        """
        prescription = await self._repository.get(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
        )
        if prescription is None:
            raise DispensingPrescriptionNotFoundError()
        if prescription.status is PrescriptionStatus.DISPENSED:
            return
        await self._repository.save(prescription.complete_dispensing())


class DispensingStaffQualificationAdapter(StaffQualificationBoundary):
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

        薬剤師かどうかの判定は ``DispensingPharmacistService`` の責務であり、
        ここでは行わない。資格が空でも在籍しているので例外にしない。
        """
        staff = await self._repository.get(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        if staff is None:
            raise DispensingStaffNotFoundError()
        return staff.qualifications
