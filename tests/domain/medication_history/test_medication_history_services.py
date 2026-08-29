"""薬歴のドメインサービスのテスト。

``okf/ddd/medication_history.md`` §5 で守り手が **Domain Service** / **Repository契約**
になっている不変条件（#1 指導者の資格 / #9 #10 一意性）を固定する。

#8（調剤セッションとの一致）はここに無い。薬歴の法人・患者・処方箋IDは
UseCase が調剤セッションからそのまま取るため、食い違う組み合わせを構築できない。
構築の形は ``tests/application/medication_history`` 側が固定する。
"""

from __future__ import annotations

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    CounselorQualificationError,
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfile,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medication_history.services import (
    CounselorQualificationService,
    MedicationHistoryUniquenessService,
    PatientMedicalProfileUniquenessService,
)
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import (
    DietitianProfile,
    DietitianRegistrationNumber,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
)
from tests.factories.medication_history_factory import create_record


class Test服薬指導者の資格:
    """不変条件 #1。薬剤師法第25条の2。"""

    def test_薬剤師資格があれば_通る(self) -> None:
        # Arrange
        qualifications = StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        CounselorQualificationService().ensure_pharmacist(qualifications)

    def test_資格なしのスタッフは_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(CounselorQualificationError):
            CounselorQualificationService().ensure_pharmacist(
                StaffQualifications.empty()
            )

    def test_管理栄養士だけでは_薬剤師と認めない(self) -> None:
        """「何らかの資格があれば通る」実装になっていないことを固定する。"""
        # Arrange
        qualifications = StaffQualifications.from_profiles(
            DietitianProfile(registration_number=DietitianRegistrationNumber("12345"))
        )

        # Act / Assert
        with pytest.raises(CounselorQualificationError):
            CounselorQualificationService().ensure_pharmacist(qualifications)


class Test薬歴の一意性:
    """不変条件 #10。1回の調剤に確定済の指導記録は1件以下。"""

    def test_同一調剤に確定済が2件だと_拒否される(self) -> None:
        # Arrange
        corporate_id = CorporateId.generate()
        first = create_record(corporate_id=corporate_id).finalize()
        second = create_record(
            corporate_id=corporate_id, dispensing_id=first.dispensing_id
        ).finalize()

        # Act / Assert
        with pytest.raises(MedicationHistoryAlreadyExistsError):
            MedicationHistoryUniquenessService().ensure_no_conflict(second, [first])

    def test_下書きどうしは_競合しない(self) -> None:
        """書きかけを複数持つのは正当。"""
        # Arrange
        corporate_id = CorporateId.generate()
        first = create_record(corporate_id=corporate_id)
        second = create_record(
            corporate_id=corporate_id, dispensing_id=first.dispensing_id
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        MedicationHistoryUniquenessService().ensure_no_conflict(second, [first])

    def test_確定済と下書きは_競合しない(self) -> None:
        # Arrange
        corporate_id = CorporateId.generate()
        finalized = create_record(corporate_id=corporate_id).finalize()
        draft = create_record(
            corporate_id=corporate_id, dispensing_id=finalized.dispensing_id
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        MedicationHistoryUniquenessService().ensure_no_conflict(draft, [finalized])

    def test_既存が下書きなら_別の薬歴を確定できる(self) -> None:
        """同じ調剤に書きかけが残っていても、確定を妨げてはならない。

        判定対象は**確定済どうし**だけ。既存の下書きまで競合させると、
        書きかけを消さない限り確定できなくなる。
        """
        # Arrange
        corporate_id = CorporateId.generate()
        draft = create_record(corporate_id=corporate_id)
        finalized = create_record(
            corporate_id=corporate_id, dispensing_id=draft.dispensing_id
        ).finalize()

        # Act / Assert: 例外を送出しないこと自体が表明
        MedicationHistoryUniquenessService().ensure_no_conflict(finalized, [draft])

    def test_自分自身とは_競合しない(self) -> None:
        # Arrange
        record = create_record().finalize()

        # Act / Assert: 例外を送出しないこと自体が表明
        MedicationHistoryUniquenessService().ensure_no_conflict(record, [record])

    def test_別法人なら_同じ調剤IDでも競合しない(self) -> None:
        # Arrange
        first = create_record(corporate_id=CorporateId.generate()).finalize()
        second = create_record(
            corporate_id=CorporateId.generate(), dispensing_id=first.dispensing_id
        ).finalize()

        # Act / Assert: 例外を送出しないこと自体が表明
        MedicationHistoryUniquenessService().ensure_no_conflict(second, [first])


class Test頭書きの一意性:
    """不変条件 #9。頭書きが2件あると、どちらが投影結果かが決まらない。"""

    def test_同一患者に2件目は_拒否される(self) -> None:
        # Arrange
        corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
        first = PatientMedicalProfile.empty_for(
            corporate_id=corporate_id, patient_id=patient_id
        )
        second = PatientMedicalProfile.empty_for(
            corporate_id=corporate_id, patient_id=patient_id
        )

        # Act / Assert
        with pytest.raises(PatientMedicalProfileAlreadyExistsError):
            PatientMedicalProfileUniquenessService().ensure_no_conflict(second, [first])

    def test_自分自身とは_競合しない(self) -> None:
        # Arrange
        profile = PatientMedicalProfile.empty_for(
            corporate_id=CorporateId.generate(), patient_id=PatientId.generate()
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        PatientMedicalProfileUniquenessService().ensure_no_conflict(profile, [profile])

    def test_別患者どうしは_競合しない(self) -> None:
        # Arrange
        corporate_id = CorporateId.generate()
        first = PatientMedicalProfile.empty_for(
            corporate_id=corporate_id, patient_id=PatientId.generate()
        )
        second = PatientMedicalProfile.empty_for(
            corporate_id=corporate_id, patient_id=PatientId.generate()
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        PatientMedicalProfileUniquenessService().ensure_no_conflict(second, [first])
