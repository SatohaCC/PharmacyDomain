"""MedicationHistory Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。
"""

from __future__ import annotations

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
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId


class FakeMedicationHistoryStoreReference(StoreReferenceBoundary):
    """法人ごとに登録された店舗IDだけを存在として扱う境界。"""

    def __init__(self) -> None:
        self.registered: set[tuple[CorporateId, StoreId]] = set()

    def register(self, *, corporate_id: CorporateId, store_id: StoreId) -> None:
        """指定法人に店舗を存在させる。"""
        self.registered.add((corporate_id, store_id))

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """店舗が存在しない、または別法人の場合は404相当を送出する。"""
        if (corporate_id, store_id) not in self.registered:
            raise MedicationHistoryStoreNotFoundError()


class FakeDispensingSource(DispensingReferenceBoundary):
    """調剤セッション集約を保持して返す境界。"""

    def __init__(self) -> None:
        self.processes: dict[tuple[CorporateId, DispensingId], DispensingProcess] = {}

    def register(self, process: DispensingProcess) -> None:
        """調剤セッションを登録する。"""
        self.processes[(process.corporate_id, process.id)] = process

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess:
        """未登録・別法人の調剤セッションは404相当を送出する。"""
        process = self.processes.get((corporate_id, dispensing_id))
        if process is None:
            raise MedicationHistoryDispensingNotFoundError()
        return process


class FakeCounselorQualificationSource(StaffQualificationBoundary):
    """法人ごとに登録されたスタッフの保有資格を返す境界。"""

    def __init__(self) -> None:
        self.qualifications: dict[tuple[CorporateId, StaffId], StaffQualifications] = {}

    def register(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        qualifications: StaffQualifications,
    ) -> None:
        """指定法人にスタッフを在籍させ、保有資格を設定する。"""
        self.qualifications[(corporate_id, staff_id)] = qualifications

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """未登録・別法人のスタッフは404相当を送出する。

        資格を持たないだけのスタッフは在籍しているので例外にしない。
        """
        qualifications = self.qualifications.get((corporate_id, staff_id))
        if qualifications is None:
            raise MedicationHistoryStaffNotFoundError()
        return qualifications
