"""Prescriptionコンテキストのプリミティブ・Value Object のテスト。

規格が定める桁数・値集合の境界をここで固定する。**規格ごとに値集合が異なる
ものは、どの規格の話かをテスト名か docstring に書く**。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.base.domain.dosage import (
    DosageCode,
    DosageCodeType,
    DosageInstruction,
    DosageName,
)
from app.base.domain.exceptions import DomainValidationError
from app.domain.prescription import (
    DEFAULT_VALID_DAYS,
    ApplicationSiteCode,
    ApplicationSiteCodeRequiredError,
    DepartmentCode,
    DepartmentCodeRequiredError,
    DepartmentCodeType,
    DepartmentInfo,
    DepartmentName,
    DosageSupplement,
    DosageSupplementCode,
    DosageSupplementCodeRequiredError,
    DosageSupplementText,
    DosageSupplementType,
    GenericSubstitutionRestrictionType,
    InquiryNumber,
    InquiryTimestamp,
    MedicalInstitutionCode,
    MedicalInstitutionPrefectureCode,
    PrescriptionDocumentNumber,
    PrescriptionIssuedDate,
    PrescriptionPeriod,
    PrescriptionPeriodInvertedError,
    PrescriptionStatus,
    PrescriptionValidTo,
    RefillCount,
    SplitCount,
    SplitInstruction,
    SplitIteration,
    SplitIterationOutOfRangeError,
)


class Test医療機関コード:
    """JAHIS レコードNo.1。"""

    def test_7桁なら_受け入れる(self) -> None:
        # Arrange / Act
        actual = MedicalInstitutionCode("1234567")

        # Assert
        assert actual.value == "1234567"

    def test_職域診療所の特例コードも_受け入れる(self) -> None:
        # Arrange / Act
        actual = MedicalInstitutionCode("9999999")

        # Assert
        assert actual.value == "9999999"

    @pytest.mark.parametrize("raw", ["123456", "12345678", "12345AB"])
    def test_7桁の半角数字でなければ_拒否される(self, raw: str) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="医療機関コード"):
            MedicalInstitutionCode(raw)


class Test都道府県コード:
    """JAHIS 別表1 / 処方編 別表2。JIS X 0401 の 01〜47。"""

    @pytest.mark.parametrize("raw", ["01", "13", "47"])
    def test_01から47なら_受け入れる(self, raw: str) -> None:
        # Arrange / Act
        actual = MedicalInstitutionPrefectureCode(raw)

        # Assert
        assert actual.value == raw

    @pytest.mark.parametrize("raw", ["00", "48", "99"])
    def test_範囲外は_拒否される(self, raw: str) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="01から47"):
            MedicalInstitutionPrefectureCode(raw)

    def test_2桁でなければ_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="2桁"):
            MedicalInstitutionPrefectureCode("1")


class Test処方箋ID:
    """引換番号（16桁）・管理サービスUUID（36文字）・紙の番号を1つの型で扱う。"""

    def test_電子処方箋引換番号の16桁を_受け入れる(self) -> None:
        # Arrange / Act
        actual = PrescriptionDocumentNumber("1234567890123456")

        # Assert
        assert len(actual.value) == 16

    def test_UUID形式の36文字を_受け入れる(self) -> None:
        # Arrange / Act
        actual = PrescriptionDocumentNumber("0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b")

        # Assert
        assert len(actual.value) == 36

    def test_37文字以上は_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="36文字"):
            PrescriptionDocumentNumber("a" * 37)


class Test処方期間:
    """保険調剤の理解のために「交付の日を含めて4日以内」。"""

    def test_使用期限が交付日と同じなら_構築できる(self) -> None:
        # Arrange / Act
        actual = PrescriptionPeriod(
            issued_date=PrescriptionIssuedDate(date(2026, 8, 24)),
            valid_to=PrescriptionValidTo(date(2026, 8, 24)),
        )

        # Assert
        assert actual.valid_to.value == date(2026, 8, 24)

    def test_使用期限が交付日より前だと_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(PrescriptionPeriodInvertedError):
            PrescriptionPeriod(
                issued_date=PrescriptionIssuedDate(date(2026, 8, 24)),
                valid_to=PrescriptionValidTo(date(2026, 8, 23)),
            )

    def test_既定の使用期限は_交付日を含めて4日間(self) -> None:
        # Arrange / Act
        actual = PrescriptionPeriod.with_default_validity(
            PrescriptionIssuedDate(date(2026, 8, 24))
        )

        # Assert: 8/24 を1日目として 8/27 が4日目
        assert actual.valid_to.value == date(2026, 8, 27)
        assert DEFAULT_VALID_DAYS == 4

    def test_使用期限の当日は_期限切れではない(self) -> None:
        # Arrange
        period = PrescriptionPeriod.with_default_validity(
            PrescriptionIssuedDate(date(2026, 8, 24))
        )

        # Act / Assert: 使用期限は当日を含む
        assert not period.is_expired_on(date(2026, 8, 27))

    def test_使用期限の翌日は_期限切れ(self) -> None:
        # Arrange
        period = PrescriptionPeriod.with_default_validity(
            PrescriptionIssuedDate(date(2026, 8, 24))
        )

        # Act / Assert
        assert period.is_expired_on(date(2026, 8, 28))

    def test_交付日より前は_期間に含まれない(self) -> None:
        # Arrange
        period = PrescriptionPeriod.with_default_validity(
            PrescriptionIssuedDate(date(2026, 8, 24))
        )

        # Act / Assert
        assert not period.includes(date(2026, 8, 23))


class Test診療科:
    """JAHIS レコードNo.4。フィールドは X6 だが別表の値は2桁。"""

    def test_コード種別が標準なら_コードが必要(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DepartmentCodeRequiredError):
            DepartmentInfo(
                code_type=DepartmentCodeType.STANDARD,
                name=DepartmentName("内科"),
            )

    def test_コード種別がコードなしなら_コードを指定できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DepartmentCodeRequiredError, match="コードなし"):
            DepartmentInfo(
                code_type=DepartmentCodeType.NONE,
                name=DepartmentName("内科"),
                code=DepartmentCode("01"),
            )

    def test_別表の2桁コードを_受け入れる(self) -> None:
        # Arrange / Act
        actual = DepartmentInfo(
            code_type=DepartmentCodeType.STANDARD,
            name=DepartmentName("内科"),
            code=DepartmentCode("01"),
        )

        # Assert
        assert actual.code is not None

    def test_フィールド長の6桁までを_受け入れる(self) -> None:
        """別表の値は2桁だが、フィールド長で検証する（将来の追加を弾かない）。"""
        # Arrange / Act
        actual = DepartmentCode("012345")

        # Assert
        assert actual.value == "012345"

    def test_7桁以上は_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="6文字"):
            DepartmentCode("0123456")


class Test用法:
    """JAHIS レコードNo.111 / 処方編 用法レコード。"""

    def test_コードなし種別で_コードを省略できる(self) -> None:
        # Arrange / Act
        actual = DosageInstruction(
            code_type=DosageCodeType.NONE, name=DosageName("1日3回毎食後")
        )

        # Assert
        assert actual.code is None

    def test_JAMI用法コード種別なら_コードが必要(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="JAMI用法コード"):
            DosageInstruction(
                code_type=DosageCodeType.JAMI, name=DosageName("1日3回毎食後")
            )

    def test_用法コードは16桁(self) -> None:
        # Arrange / Act
        actual = DosageCode("1013044400000000")

        # Assert
        assert len(actual.value) == 16

    @pytest.mark.parametrize("raw", ["101304440000000", "10130444000000000"])
    def test_16桁でない用法コードは_拒否される(self, raw: str) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="16桁"):
            DosageCode(raw)


class Test用法補足:
    """処方編 別表14 / JAHIS レコードNo.181。"""

    def test_JAMI補足用法なら_補足用法コードが必要(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DosageSupplementCodeRequiredError):
            DosageSupplement(
                supplement_type=DosageSupplementType.JAMI_SUPPLEMENT,
                text=DosageSupplementText("1日おき"),
            )

    def test_JAMI部位なら_外用部位コードが必要(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ApplicationSiteCodeRequiredError):
            DosageSupplement(
                supplement_type=DosageSupplementType.JAMI_SITE,
                text=DosageSupplementText("左耳"),
            )

    def test_外用部位コードが揃えば_構築できる(self) -> None:
        # Arrange / Act
        actual = DosageSupplement(
            supplement_type=DosageSupplementType.JAMI_SITE,
            text=DosageSupplementText("左耳"),
            site_code=ApplicationSiteCode("42L"),
        )

        # Assert
        assert actual.site_code is not None

    def test_外用部位コードは3文字(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="3文字"):
            ApplicationSiteCode("42")

    def test_一包化など_コード不要の区分は_そのまま構築できる(self) -> None:
        # Arrange / Act
        actual = DosageSupplement(
            supplement_type=DosageSupplementType.UNIT_DOSE,
            text=DosageSupplementText("一包化"),
        )

        # Assert
        assert actual.code is None

    def test_補足用法コードは8文字以内(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="8文字"):
            DosageSupplementCode("123456789")

    @pytest.mark.parametrize(
        ("supplement_type", "expected"),
        [
            (DosageSupplementType.TAPERING, "1"),
            (DosageSupplementType.UNIT_DOSE, "2"),
            (DosageSupplementType.ALTERNATE_DAY, "3"),
            (DosageSupplementType.CRUSHED, "4"),
            (DosageSupplementType.CONTINUATION, "5"),
            (DosageSupplementType.SITE, "6"),
            (DosageSupplementType.SINGLE_DOSE, "7"),
            (DosageSupplementType.JAMI_SUPPLEMENT, "8"),
            (DosageSupplementType.JAMI_SITE, "9"),
        ],
    )
    def test_レコードコードが_別表14と一致する(
        self, supplement_type: DosageSupplementType, expected: str
    ) -> None:
        # Arrange / Act / Assert
        assert supplement_type.record_code == expected


class Test変更制限:
    """処方編 別表16 の 3〜6・8。"""

    @pytest.mark.parametrize(
        ("restriction_type", "expected"),
        [
            (GenericSubstitutionRestrictionType.NO_GENERIC, "3"),
            (GenericSubstitutionRestrictionType.NO_FORM_CHANGE, "4"),
            (GenericSubstitutionRestrictionType.NO_STRENGTH_CHANGE, "5"),
            (GenericSubstitutionRestrictionType.NO_FORM_OR_STRENGTH_CHANGE, "6"),
            (GenericSubstitutionRestrictionType.BRAND_REQUESTED_BY_PATIENT, "8"),
        ],
    )
    def test_レコードコードが_別表16と一致する(
        self, restriction_type: GenericSubstitutionRestrictionType, expected: str
    ) -> None:
        # Arrange / Act / Assert: 7 は JAMI補足用法なので変更制限には無い
        assert restriction_type.record_code == expected

    @pytest.mark.parametrize(
        "restriction_type",
        [
            GenericSubstitutionRestrictionType.NO_GENERIC,
            GenericSubstitutionRestrictionType.BRAND_REQUESTED_BY_PATIENT,
        ],
    )
    def test_後発品変更を禁じる区分を_判別できる(
        self, restriction_type: GenericSubstitutionRestrictionType
    ) -> None:
        """医師の変更不可指示と患者の先発品希望は、いずれも後発品変更を止める。"""
        # Arrange / Act / Assert
        assert restriction_type.forbids_generic_substitution

    @pytest.mark.parametrize(
        "restriction_type",
        [
            GenericSubstitutionRestrictionType.NO_FORM_CHANGE,
            GenericSubstitutionRestrictionType.NO_STRENGTH_CHANGE,
        ],
    )
    def test_剤形や含量の制限だけなら_後発品変更は禁じない(
        self, restriction_type: GenericSubstitutionRestrictionType
    ) -> None:
        # Arrange / Act / Assert
        assert not restriction_type.forbids_generic_substitution


class Testリフィルと分割:
    """保険調剤の理解のために。"""

    @pytest.mark.parametrize("count", [2, 3])
    def test_リフィル総使用回数は_2回または3回(self, count: int) -> None:
        # Arrange / Act
        actual = RefillCount(count)

        # Assert
        assert actual.value == count

    @pytest.mark.parametrize("count", [1, 4])
    def test_リフィル総使用回数が_2回3回以外だと拒否される(self, count: int) -> None:
        """1回はリフィル処方箋ではなく、4回以上は制度上存在しない。"""
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="2回または3回"):
            RefillCount(count)

    def test_当該分割回が_全分割回数以内なら構築できる(self) -> None:
        # Arrange / Act
        actual = SplitInstruction(
            total_split_count=SplitCount(3), split_iteration=SplitIteration(3)
        )

        # Assert
        assert actual.split_iteration.value == 3

    def test_当該分割回が_全分割回数を超えると拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(SplitIterationOutOfRangeError, match="全分割回数: 2"):
            SplitInstruction(
                total_split_count=SplitCount(2), split_iteration=SplitIteration(3)
            )


class Test疑義照会の連番:
    """調剤編 511 は「複数記録可（最大999）」。"""

    def test_999までは_受け入れる(self) -> None:
        # Arrange / Act
        actual = InquiryNumber(999)

        # Assert
        assert actual.value == 999

    def test_1000以上は_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="999"):
            InquiryNumber(1000)


class Test照会日時:
    """監査に使うので naive な日時を受け付けない。"""

    def test_UTCの日時を_受け入れる(self) -> None:
        # Arrange / Act
        actual = InquiryTimestamp(datetime(2026, 8, 24, 1, 30, tzinfo=UTC))

        # Assert
        assert actual.value.tzinfo is UTC

    def test_タイムゾーンなしの日時は_拒否される(self) -> None:
        """どのタイムゾーンで記録されたか復元できず、監査に使えないため。"""
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="タイムゾーン"):
            InquiryTimestamp(datetime(2026, 8, 24, 1, 30))  # noqa: DTZ001


class Test処方箋の状態:
    def test_終端状態を_判別できる(self) -> None:
        # Arrange / Act / Assert
        assert PrescriptionStatus.DISPENSED.is_terminal
        assert PrescriptionStatus.CANCELLED.is_terminal

    def test_進行中の状態は_終端ではない(self) -> None:
        # Arrange / Act / Assert
        assert not PrescriptionStatus.RECEIVED.is_terminal
        assert not PrescriptionStatus.READY_FOR_DISPENSING.is_terminal

    def test_全状態に_日本語ラベルが定義されている(self) -> None:
        # Arrange / Act / Assert
        assert all(status.label for status in PrescriptionStatus)
