"""MedicationHistory集約に関わるドメインサービス。

無状態（Stateless）であり、**本物の集約・値オブジェクトを引数で受け取る**。
薬歴単独では判定できない指導者の資格などを検証する。
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.staff.primitives import PharmacistProfile, StaffQualifications


class CounselorQualificationService:
    """服薬指導を行った者が薬剤師資格を持つかを検証する。

    薬剤師法第25条の2は情報の提供及び指導の義務を薬剤師に課している。
    薬剤師かどうかは Staff 集約が持つ事実であり、``MedicationHistoryRecord`` は
    ``StaffId`` しか持たないため、Application層の資格 Boundary が取り出した
    **本物の ``StaffQualifications``** をこのサービスが受け取る。
    """

    def ensure_pharmacist(self, qualifications: StaffQualifications) -> None:
        """薬剤師資格を保有していることを検証する。

        Raises:
            CounselorQualificationError: 薬剤師資格が無い場合。
        """
        if not qualifications.has(PharmacistProfile):
            raise CounselorQualificationError()


class MedicationHistoryUniquenessService:
    """同一調剤セッションに確定済の薬歴が2件以上無いことを検証する。"""

    def ensure_no_conflict(
        self,
        record: MedicationHistoryRecord,
        existing_records: Iterable[MedicationHistoryRecord],
    ) -> None:
        """確定済薬歴の重複を検証する。

        **下書きは制限しない。** 書きかけを複数持つのは正当であり、
        制限すると入力途中の記録を作れなくなる。判定対象は確定済どうしだけ。

        同じ集約IDの現在行は候補から除外し、自身の状態変更を妨げない。
        """
        if not record.is_finalized:
            return
        for existing in existing_records:
            if existing.id == record.id or not existing.is_finalized:
                continue
            if (
                existing.corporate_id == record.corporate_id
                and existing.dispensing_id == record.dispensing_id
            ):
                raise MedicationHistoryAlreadyExistsError()


class PatientMedicalProfileUniquenessService:
    """患者ごとに頭書きが1件であることを検証する。"""

    def ensure_no_conflict(
        self,
        profile: PatientMedicalProfile,
        existing_profiles: Iterable[PatientMedicalProfile],
    ) -> None:
        """同一法人・同一患者の頭書きが重複していないことを検証する。

        頭書きが2件あると、どちらが投影結果かが決まらなくなる。
        同じ集約IDの現在行は候補から除外する。
        """
        for existing in existing_profiles:
            if existing.id == profile.id:
                continue
            if (
                existing.corporate_id == profile.corporate_id
                and existing.patient_id == profile.patient_id
            ):
                raise PatientMedicalProfileAlreadyExistsError()
