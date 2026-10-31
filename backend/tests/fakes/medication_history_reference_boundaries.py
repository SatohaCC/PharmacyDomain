"""MedicationHistory Applicationが依存する参照境界のフェイク実装。

AGENTS.md「Boundaryの例外契約」が求める「定義だけで raise されない例外を残さない」
を実行可能にするため、各Protocolの ``Raises:`` に書かれた例外をここで実際に送出する。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.application.common.exceptions import AuthorizationError
from app.application.composition.adapters.medication_history_snapshot_mapping import (
    dispensing_source,
)
from app.application.medication_history.errors import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryPatientNotFoundError,
    MedicationHistoryPrescriptionNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
)
from app.application.medication_history.interfaces.references import (
    DispensingReferenceBoundary,
    StaffQualificationBoundary,
    StatutoryRecordSourceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.identifiers import DispensingId
from app.domain.medication_history.value_objects import (
    DispensingSource,
    PharmacistQualification,
    StatutoryPharmacistName,
    StatutoryRecordSource,
)
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.staff.identifiers import StaffId
from app.domain.staff.value_objects import (
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.identifiers import StoreId


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
    ) -> DispensingSource:
        """未登録・別法人の調剤セッションは404相当を送出する。"""
        process = self.processes.get((corporate_id, dispensing_id))
        if process is None:
            raise MedicationHistoryDispensingNotFoundError()
        return dispensing_source(process)


class FakeCounselorQualificationSource(StaffQualificationBoundary):
    """法人ごとに登録されたスタッフの保有資格を返す境界。"""

    def __init__(self) -> None:
        self.qualifications: dict[tuple[CorporateId, StaffId], StaffQualifications] = {}
        self.active_flags: dict[tuple[CorporateId, StaffId], bool] = {}
        self.affiliations: dict[
            tuple[CorporateId, StaffId], tuple[StoreAffiliation, ...] | None
        ] = {}

    def register(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        qualifications: StaffQualifications,
        is_active: bool = True,
        affiliations: tuple[StoreAffiliation, ...] | None = None,
    ) -> None:
        """指定法人にスタッフを在籍させ、保有資格を設定する。"""
        key = (corporate_id, staff_id)
        self.qualifications[key] = qualifications
        self.active_flags[key] = is_active
        self.affiliations[key] = affiliations

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        store_id: StoreId | None = None,
        as_of: date | None = None,
    ) -> PharmacistQualification:
        """未登録・別法人のスタッフは404相当を送出する。

        資格を持たないだけのスタッフは在籍しているので例外にしない。
        """
        key = (corporate_id, staff_id)
        qualifications = self.qualifications.get(key)
        if qualifications is None:
            raise MedicationHistoryStaffNotFoundError()
        if not self.active_flags.get(key, True):
            raise AuthorizationError("停止中のスタッフは業務を実行できません。")
        staff_affiliations = self.affiliations.get(key)
        if (
            staff_affiliations is not None
            and store_id is not None
            and as_of is not None
            and not any(
                aff.store_id == store_id and aff.period.is_active_on(as_of)
                for aff in staff_affiliations
            )
        ):
            raise AuthorizationError("指定された店舗に当日有効な所属がありません。")
        return PharmacistQualification(
            has_pharmacist=qualifications.has(PharmacistProfile)
        )


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
