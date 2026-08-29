"""処方箋のドメインサービスのテスト。

麻薬処方箋の必須事項とリフィル適用除外など、**Domain Service** が担う
集約外の事実を使った検証を固定する。

このファイルの主眼は **fail-closed が本当に効くこと**である。医薬品マスタが
無い状態で「該当しない」と黙って答える実装になっていないかを、``UNKNOWN`` と
「分類が渡されていない」の両方で確かめる。
"""

from __future__ import annotations

import pytest

from app.base.domain.medicine import (
    MedicineIdentifier,
    PublicExpenseBurden,
)
from app.domain.prescription import (
    InquiryPharmacistQualificationError,
    MedicineClassification,
    MedicineClassificationMissingError,
    MedicineClassificationUnknownError,
    MedicineRestrictionFlag,
    NarcoticLicenseNumber,
    NarcoticPrescriptionDetails,
    NarcoticPrescriptionDetailsRequiredError,
    PatientAddressLine,
    PatientPhoneNumber,
    Prescription,
    PrescriptionManagementInfo,
    PublicExpenseBurdenNotCoveredError,
    RefillCount,
    RefillInstruction,
    RefillNotAllowedError,
)
from app.domain.prescription.services import (
    InquiryPharmacistService,
    NarcoticPrescriptionService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.domain.staff.primitives import (
    DietitianProfile,
    DietitianRegistrationNumber,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffQualifications,
)
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_rp,
)

_YES = MedicineRestrictionFlag.YES
_NO = MedicineRestrictionFlag.NO
_UNKNOWN = MedicineRestrictionFlag.UNKNOWN


def _classifications(
    prescription: Prescription,
    *,
    is_narcotic: MedicineRestrictionFlag = _NO,
    has_dosage_limit: MedicineRestrictionFlag = _NO,
    is_refill_restricted_patch: MedicineRestrictionFlag = _NO,
) -> dict[MedicineIdentifier, MedicineClassification]:
    """処方箋の全薬品に同じ分類を割り当てる。"""
    return {
        identifier: MedicineClassification(
            identifier=identifier,
            is_narcotic=is_narcotic,
            has_dosage_limit=has_dosage_limit,
            is_refill_restricted_patch=is_refill_restricted_patch,
        )
        for identifier in prescription.medicine_identifiers
    }


def _narcotic_details() -> NarcoticPrescriptionDetails:
    """麻薬処方箋の必須3項目を組み立てる。"""
    return NarcoticPrescriptionDetails(
        narcotic_license_number=NarcoticLicenseNumber("13-1234"),
        patient_address=PatientAddressLine("東京都千代田区1-2-3"),
        patient_phone_number=PatientPhoneNumber("0312345678"),
    )


class Test麻薬処方箋:
    """麻薬処方箋の必須事項をDomain Serviceで検証する。"""

    def test_麻薬を含まなければ_麻薬情報が無くても通る(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act / Assert: 例外を送出しないこと自体が表明
        NarcoticPrescriptionService().ensure_narcotic_details_present(
            prescription, _classifications(prescription, is_narcotic=_NO)
        )

    def test_麻薬を含むのに_麻薬情報が無いと_拒否される(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act / Assert
        with pytest.raises(NarcoticPrescriptionDetailsRequiredError):
            NarcoticPrescriptionService().ensure_narcotic_details_present(
                prescription, _classifications(prescription, is_narcotic=_YES)
            )

    def test_麻薬を含み_麻薬情報が揃っていれば_通る(self) -> None:
        # Arrange
        prescription = create_prescription(
            management_info=PrescriptionManagementInfo(narcotic=_narcotic_details())
        )

        # Act / Assert
        NarcoticPrescriptionService().ensure_narcotic_details_present(
            prescription, _classifications(prescription, is_narcotic=_YES)
        )

    def test_麻薬区分が不明だと_該当しない扱いにせず_拒否される(self) -> None:
        """医薬品マスタが無い状態で「麻薬ではない」と答えないこと（fail-closed）。"""
        # Arrange
        prescription = create_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationUnknownError):
            NarcoticPrescriptionService().ensure_narcotic_details_present(
                prescription, _classifications(prescription, is_narcotic=_UNKNOWN)
            )

    def test_分類が渡されていないと_問題なしにせず_拒否される(self) -> None:
        """マスタ未登録の薬品を素通りさせないこと。"""
        # Arrange
        prescription = create_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationMissingError, match="ノルバスク"):
            NarcoticPrescriptionService().ensure_narcotic_details_present(
                prescription, {}
            )

    def test_複数の剤のうち1つでも麻薬なら_麻薬情報が必要になる(self) -> None:
        # Arrange
        prescription = create_prescription(
            rps=(
                create_rp(rp_number=1, medicines=(create_medicine(line_number=1),)),
                create_rp(
                    rp_number=2,
                    medicines=(
                        create_medicine(line_number=1, code="1111111111", name="薬A"),
                    ),
                ),
            )
        )
        classifications = _classifications(prescription, is_narcotic=_NO)
        narcotic_identifier = prescription.rps[1].medicines[0].identifier
        classifications[narcotic_identifier] = MedicineClassification(
            identifier=narcotic_identifier, is_narcotic=_YES
        )

        # Act / Assert
        with pytest.raises(NarcoticPrescriptionDetailsRequiredError):
            NarcoticPrescriptionService().ensure_narcotic_details_present(
                prescription, classifications
            )

    def test_エラーメッセージに_対象の薬品名が含まれる(self) -> None:
        # Arrange
        prescription = create_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationUnknownError, match="ノルバスク"):
            NarcoticPrescriptionService().ensure_narcotic_details_present(
                prescription, _classifications(prescription, is_narcotic=_UNKNOWN)
            )


class Testリフィル適用除外:
    """リフィル適用除外をDomain Serviceで検証する。

    判定基準は「投与量に限度が定められている医薬品」と「貼付剤」であり、
    「麻薬・向精神薬・湿布薬」という例示ではない。
    """

    @staticmethod
    def _refill_prescription() -> Prescription:
        """リフィル指示付きの処方箋を組み立てる。"""
        return create_prescription(
            management_info=PrescriptionManagementInfo(
                refill=RefillInstruction(total_refill_count=RefillCount(3))
            )
        )

    def test_リフィル指示が無ければ_何も課さない(self) -> None:
        """適用除外の薬品を含んでいても、リフィルでなければ関係ない。"""
        # Arrange
        prescription = create_prescription()

        # Act / Assert: 分類を渡さなくても通る（判定自体が不要なため）
        RefillEligibilityService().ensure_refill_allowed(prescription, {})

    def test_適用除外に当たらなければ_通る(self) -> None:
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        RefillEligibilityService().ensure_refill_allowed(
            prescription,
            _classifications(
                prescription, has_dosage_limit=_NO, is_refill_restricted_patch=_NO
            ),
        )

    def test_投与量に限度がある医薬品は_拒否される(self) -> None:
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        with pytest.raises(RefillNotAllowedError):
            RefillEligibilityService().ensure_refill_allowed(
                prescription,
                _classifications(prescription, has_dosage_limit=_YES),
            )

    def test_貼付剤は_拒否される(self) -> None:
        """麻薬・向精神薬・皮膚疾患用を除いた貼付剤。除外条件はマスタ側で適用済み。"""
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        with pytest.raises(RefillNotAllowedError):
            RefillEligibilityService().ensure_refill_allowed(
                prescription,
                _classifications(prescription, is_refill_restricted_patch=_YES),
            )

    def test_麻薬であること自体は_リフィル可否を決めない(self) -> None:
        """麻薬は「投与量に限度がある」から不可であり、麻薬だから不可ではない。

        判定基準を例示列挙で実装していないことを、この向きで固定する。
        麻薬フラグだけが立ち投与量限度が無い薬品は、この基準では通る。
        """
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert: 例外を送出しないこと自体が表明
        RefillEligibilityService().ensure_refill_allowed(
            prescription,
            _classifications(
                prescription,
                is_narcotic=_YES,
                has_dosage_limit=_NO,
                is_refill_restricted_patch=_NO,
            ),
        )

    def test_投与量限度が不明だと_拒否される(self) -> None:
        """fail-closed。"""
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationUnknownError):
            RefillEligibilityService().ensure_refill_allowed(
                prescription,
                _classifications(prescription, has_dosage_limit=_UNKNOWN),
            )

    def test_貼付剤区分が不明だと_拒否される(self) -> None:
        """fail-closed。"""
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationUnknownError):
            RefillEligibilityService().ensure_refill_allowed(
                prescription,
                _classifications(prescription, is_refill_restricted_patch=_UNKNOWN),
            )

    def test_分類が渡されていないと_拒否される(self) -> None:
        # Arrange
        prescription = self._refill_prescription()

        # Act / Assert
        with pytest.raises(MedicineClassificationMissingError):
            RefillEligibilityService().ensure_refill_allowed(prescription, {})


class Test医薬品分類:
    """``UNKNOWN`` を明示的に持つ型であることを固定する。"""

    def test_既定値は_すべて不明(self) -> None:
        """マスタを引かずに組み立てた分類が「該当しない」にならないこと。"""
        # Arrange / Act
        actual = MedicineClassification(
            identifier=create_medicine().identifier,
        )

        # Assert
        assert actual.has_unknown_flag
        assert actual.is_narcotic.is_unknown

    def test_投与量限度があれば_リフィル不可と判定される(self) -> None:
        # Arrange / Act
        actual = MedicineClassification(
            identifier=create_medicine().identifier,
            has_dosage_limit=_YES,
            is_refill_restricted_patch=_NO,
        )

        # Assert
        assert actual.forbids_refill

    def test_どちらも該当しなければ_リフィル可と判定される(self) -> None:
        # Arrange / Act
        actual = MedicineClassification(
            identifier=create_medicine().identifier,
            is_narcotic=_NO,
            has_dosage_limit=_NO,
            is_refill_restricted_patch=_NO,
        )

        # Assert
        assert not actual.forbids_refill
        assert not actual.has_unknown_flag

    def test_不明は_リフィル不可とは判定されない(self) -> None:
        """``forbids_refill`` は不明を False にする。呼び出し側が先に不明を弾く。

        この分担を誤ると「不明＝可」になるため、両方のテストで固定する。
        """
        # Arrange / Act
        actual = MedicineClassification(identifier=create_medicine().identifier)

        # Assert
        assert not actual.forbids_refill
        assert actual.has_unknown_flag


class Test疑義照会の実施者資格:
    """資格の判定はDomain Service、資格の取得はApplicationのBoundaryが担う。"""

    def test_薬剤師資格があれば_通る(self) -> None:
        # Arrange
        qualifications = StaffQualifications.from_profiles(
            PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
        )

        # Act / Assert: 例外を送出しないこと自体が表明
        InquiryPharmacistService().ensure_pharmacist(qualifications)

    def test_資格なしのスタッフは_拒否される(self) -> None:
        """医療事務・調剤補助が疑義照会の実施者になってはならない。"""
        # Arrange / Act / Assert
        with pytest.raises(InquiryPharmacistQualificationError):
            InquiryPharmacistService().ensure_pharmacist(StaffQualifications.empty())

    def test_管理栄養士だけでは_薬剤師と認めない(self) -> None:
        """「何らかの資格があれば通る」実装になっていないことを固定する。"""
        # Arrange
        qualifications = StaffQualifications.from_profiles(
            DietitianProfile(registration_number=DietitianRegistrationNumber("12345"))
        )

        # Act / Assert
        with pytest.raises(InquiryPharmacistQualificationError):
            InquiryPharmacistService().ensure_pharmacist(qualifications)

    def test_薬剤師を含む複数資格でも_通る(self) -> None:
        # Arrange
        qualifications = StaffQualifications.from_profiles(
            DietitianProfile(registration_number=DietitianRegistrationNumber("12345")),
            PharmacistProfile(license_number=PharmacistLicenseNumber("1234567")),
        )

        # Act / Assert
        InquiryPharmacistService().ensure_pharmacist(qualifications)


class Test公費負担の裏付け:
    """裏付けの無い公費負担を凍結させない。"""

    @staticmethod
    def _prescription_with_burden(burden: PublicExpenseBurden) -> Prescription:
        """指定の負担区分を持つ薬品1件の処方箋を組み立てる。"""
        return create_prescription(
            rps=(create_rp(medicines=(create_medicine(burden=burden),)),)
        )

    def test_負担区分が無い薬品には_何も課さない(self) -> None:
        """レコードNo.231 は全薬品出力か全薬品未出力。未出力は公費負担なし。"""
        # Arrange
        prescription = create_prescription()

        # Act / Assert: 枠が1つも無い資格でも通る
        PublicExpenseBurdenService().ensure_burden_is_covered(
            prescription, PublicExpenseBurden()
        )

    def test_資格に存在する枠なら_通る(self) -> None:
        # Arrange
        prescription = self._prescription_with_burden(PublicExpenseBurden(first=True))

        # Act / Assert
        PublicExpenseBurdenService().ensure_burden_is_covered(
            prescription, PublicExpenseBurden(first=True, second=True)
        )

    def test_資格に無い枠へ負担を割り当てると_拒否される(self) -> None:
        # Arrange
        prescription = self._prescription_with_burden(PublicExpenseBurden(second=True))

        # Act / Assert
        with pytest.raises(PublicExpenseBurdenNotCoveredError, match="第二公費"):
            PublicExpenseBurdenService().ensure_burden_is_covered(
                prescription, PublicExpenseBurden(first=True)
            )

    def test_負担しないとした枠は_資格に無くても通る(self) -> None:
        """検証対象は「負担あり」の枠だけ。"""
        # Arrange
        prescription = self._prescription_with_burden(
            PublicExpenseBurden(first=True, second=False)
        )

        # Act / Assert
        PublicExpenseBurdenService().ensure_burden_is_covered(
            prescription, PublicExpenseBurden(first=True)
        )

    def test_特殊公費は_資格側で表せなければ拒否される(self) -> None:
        """特殊公費の負担者番号は ``N20`` で Claim の8桁制約を満たせない。

        表せない枠を ``True`` で埋めない限り、この向きで必ず落ちる。
        """
        # Arrange
        prescription = self._prescription_with_burden(PublicExpenseBurden(special=True))

        # Act / Assert
        with pytest.raises(PublicExpenseBurdenNotCoveredError, match="特殊公費"):
            PublicExpenseBurdenService().ensure_burden_is_covered(
                prescription,
                PublicExpenseBurden(first=True, second=True, third=True),
            )

    def test_複数薬品のうち1件でも裏付けが無ければ_拒否される(self) -> None:
        # Arrange
        prescription = create_prescription(
            rps=(
                create_rp(
                    medicines=(
                        create_medicine(
                            line_number=1, burden=PublicExpenseBurden(first=True)
                        ),
                        create_medicine(
                            line_number=2,
                            code="1111111111",
                            name="薬A",
                            burden=PublicExpenseBurden(third=True),
                        ),
                    )
                ),
            )
        )

        # Act / Assert
        with pytest.raises(PublicExpenseBurdenNotCoveredError, match="薬A"):
            PublicExpenseBurdenService().ensure_burden_is_covered(
                prescription, PublicExpenseBurden(first=True)
            )
