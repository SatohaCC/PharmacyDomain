"""MedicationHistory Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。
"""

from __future__ import annotations

from dataclasses import replace

from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryPatientNotFoundError,
    MedicationHistoryPrescriptionNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
)
from app.application.medication_history.reference import (
    DispensingReferenceBoundary,
    StaffQualificationBoundary,
    StatutoryRecordSourceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.value_objects import (
    StatutoryPharmacistName,
    StatutoryRecordSource,
)
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId
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


class FakeStatutoryRecordSource(StatutoryRecordSourceBoundary):
    """登録されたスナップショットを、スタッフの解決だけ絞り込んで返す境界。

    氏名を引けるスタッフは ``resolvable`` で制御する。**未登録のスタッフは
    例外にせず結果から落とす**（Protocolの契約どおり）。
    """

    def __init__(self) -> None:
        self.sources: dict[
            tuple[CorporateId, PrescriptionId], StatutoryRecordSource
        ] = {}
        self.missing_patients: set[tuple[CorporateId, PatientId]] = set()
        self.resolvable: set[StaffId] | None = None
        self.requested_staff_ids: list[frozenset[StaffId]] = []

    def register(
        self,
        *,
        corporate_id: CorporateId,
        source: StatutoryRecordSource,
    ) -> None:
        """指定法人の処方箋に対するスナップショットを登録する。"""
        self.sources[(corporate_id, source.prescription_id)] = source

    def hide_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定患者を解決できない状態にする。"""
        self.missing_patients.add((corporate_id, patient_id))

    async def build(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        prescription_id: PrescriptionId,
        staff_ids: frozenset[StaffId],
    ) -> StatutoryRecordSource:
        """未登録の患者・処方箋は404相当を送出し、スタッフは落とすだけにする。"""
        self.requested_staff_ids.append(staff_ids)
        if (corporate_id, patient_id) in self.missing_patients:
            raise MedicationHistoryPatientNotFoundError()
        source = self.sources.get((corporate_id, prescription_id))
        if source is None:
            raise MedicationHistoryPrescriptionNotFoundError()
        return replace(
            source,
            pharmacist_names=self._resolve(source.pharmacist_names, staff_ids),
        )

    def _resolve(
        self,
        names: tuple[StatutoryPharmacistName, ...],
        staff_ids: frozenset[StaffId],
    ) -> tuple[StatutoryPharmacistName, ...]:
        """問い合わせ対象のうち、氏名を引けるスタッフだけを残す。"""
        allowed = self.resolvable
        return tuple(
            name
            for name in names
            if name.staff_id in staff_ids
            and (allowed is None or name.staff_id in allowed)
        )
