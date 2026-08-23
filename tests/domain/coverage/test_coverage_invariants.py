"""Coverageドメインの不変条件テスト。"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import (
    CoverageActivatedOn,
    CoverageActivation,
    CoverageBenefitRatio,
    CoverageBranchNumber,
    CoverageCode,
    CoverageDeactivatedOn,
    CoverageInsuredType,
    CoveragePeriod,
    CoveragePeriodConflictError,
    CoveragePriority,
    CoverageSymbol,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    InsuranceCoverageDetails,
    InsuranceCoveragePriorityError,
    InsurerNumber,
    PatientCoverage,
    PatientCoverageConflictService,
    PublicExpenseCoverageDetails,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.patient.primitives import PatientId
from tests.fakes.in_memory_patient_coverage_repository import (
    InMemoryPatientCoverageRepository,
)

_VALID_FROM = date(2026, 8, 1)
_VALID_TO = date(2026, 8, 31)


def _create_period(
    valid_from: date = _VALID_FROM,
    valid_to: date | None = _VALID_TO,
) -> CoveragePeriod:
    """テスト用の適用期間を生成する。"""
    return CoveragePeriod(
        valid_from=CoverageValidFrom(valid_from),
        valid_to=CoverageValidTo(valid_to) if valid_to is not None else None,
    )


def _create_insurance_details(
    insurer_number: str = "01130012",
) -> InsuranceCoverageDetails:
    """テスト用の医療保険詳細を生成する。"""
    return InsuranceCoverageDetails(
        insurer_number=InsurerNumber(insurer_number),
        insured_symbol=CoverageSymbol("A"),
        insured_number=CoverageCode("456"),
        insured_type=CoverageInsuredType.SELF,
        benefit_ratio=CoverageBenefitRatio(70),
    )


def _create_public_details(priority: int) -> PublicExpenseCoverageDetails:
    """テスト用の公費詳細を生成する。"""
    return PublicExpenseCoverageDetails(
        payer_number=PublicPayerNumber(f"1234567{priority}"),
        recipient_number=PublicRecipientNumber(f"123456{priority}"),
    )


def _create_activation(
    activated_on: date = _VALID_FROM,
    deactivated_on: date | None = None,
) -> CoverageActivation:
    """テスト用の台帳行有効区間を生成する。"""
    return CoverageActivation(
        activated_on=CoverageActivatedOn(activated_on),
        deactivated_on=(
            CoverageDeactivatedOn(deactivated_on)
            if deactivated_on is not None
            else None
        ),
    )


def _create_coverage(
    *,
    coverage_type: CoverageType,
    priority: int,
    corporate_id: CorporateId,
    patient_id: PatientId,
    period: CoveragePeriod | None = None,
    activated_on: date = _VALID_FROM,
    deactivated_on: date | None = None,
) -> PatientCoverage:
    """テスト用の患者資格を生成する。

    ``deactivated_on`` に ``activated_on`` と同日を渡すと実効期間が空になり、
    「無効化済みで競合しない資格」を表す。
    """
    activation = _create_activation(activated_on, deactivated_on)
    if coverage_type is CoverageType.INSURANCE:
        return PatientCoverage.create(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_type=coverage_type,
            period=period if period is not None else _create_period(),
            activation=activation,
            priority=CoveragePriority(priority),
            insurance_details=_create_insurance_details(),
        )
    return PatientCoverage.create(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_type=coverage_type,
        period=period if period is not None else _create_period(),
        activation=activation,
        priority=CoveragePriority(priority),
        public_expense_details=_create_public_details(priority),
    )


def test_資格順位_第一順位と第四順位を指定すると_生成できる() -> None:
    # Arrange / Act
    actual = (CoveragePriority(1), CoveragePriority(4))

    # Assert
    assert tuple(item.value for item in actual) == (1, 4)


@pytest.mark.parametrize("value", [0, 5])
def test_資格順位_範囲外を指定すると_ドメイン検証エラーになる(value: int) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        CoveragePriority(value)


@pytest.mark.parametrize("value", ["011300", "01130012"])
def test_保険者番号_6桁または8桁を指定すると_生成できる(value: str) -> None:
    # Arrange / Act
    actual = InsurerNumber(value)

    # Assert
    assert actual.value == value


@pytest.mark.parametrize(
    "value", ["1", "0113001", "011300123", "あいう xyz", "0113001a"]
)
def test_保険者番号_桁数か文字種が不正だと_ドメイン検証エラーになる(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        InsurerNumber(value)


@pytest.mark.parametrize("value", ["1", "123456789", "1234567a"])
def test_公費負担者番号_8桁の数字以外だと_ドメイン検証エラーになる(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        PublicPayerNumber(value)


@pytest.mark.parametrize("value", ["1", "12345678", "123456a"])
def test_公費受給者番号_7桁の数字以外だと_ドメイン検証エラーになる(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        PublicRecipientNumber(value)


@pytest.mark.parametrize("value", ["1", "123", "1a"])
def test_枝番_2桁の数字以外だと_ドメイン検証エラーになる(value: str) -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        CoverageBranchNumber(value)


def test_適用期間_終了日が開始日より前だと_ドメイン検証エラーになる() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        _create_period(date(2026, 8, 31), date(2026, 8, 1))


def test_適用期間_開始日と終了日が同日なら_生成できる() -> None:
    # Arrange / Act
    actual = _create_period(date(2026, 8, 1), date(2026, 8, 1))

    # Assert
    assert actual.valid_to is not None
    assert actual.valid_from.value == actual.valid_to.value


def test_適用開始日_日時型を指定すると_ドメイン検証エラーになる() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        # naive日時が拒否されることを確認するテストなので、意図的にtzを付けない。
        CoverageValidFrom(datetime(2026, 8, 1, 12, 0))  # noqa: DTZ001


def test_適用終了日_日時型を指定すると_ドメイン検証エラーになる() -> None:
    # Arrange / Act / Assert
    with pytest.raises(DomainValidationError):
        # naive日時が拒否されることを確認するテストなので、意図的にtzを付けない。
        CoverageValidTo(datetime(2026, 8, 31, 12, 0))  # noqa: DTZ001


def test_適用期間_隣接する期間は_重ならない() -> None:
    # Arrange
    august = _create_period(date(2026, 8, 1), date(2026, 8, 31))
    september = _create_period(date(2026, 9, 1), date(2026, 9, 30))

    # Act
    actual = (august.overlaps(september), september.overlaps(august))

    # Assert
    assert actual == (False, False)


def test_適用期間_1日だけ接する期間は_重なる() -> None:
    # Arrange
    august = _create_period(date(2026, 8, 1), date(2026, 8, 31))
    from_last_day = _create_period(date(2026, 8, 31), date(2026, 9, 30))

    # Act
    actual = (august.overlaps(from_last_day), from_last_day.overlaps(august))

    # Assert
    assert actual == (True, True)


def test_適用期間_無期限同士は_重なる() -> None:
    # Arrange
    older = _create_period(date(2020, 1, 1), None)
    newer = _create_period(date(2026, 8, 1), None)

    # Act
    actual = (older.overlaps(newer), newer.overlaps(older))

    # Assert
    assert actual == (True, True)


def test_適用期間_無期限と過去に閉じた期間は_重ならない() -> None:
    # Arrange
    closed_past = _create_period(date(2020, 1, 1), date(2020, 12, 31))
    open_ended = _create_period(date(2026, 8, 1), None)

    # Act
    actual = (closed_past.overlaps(open_ended), open_ended.overlaps(closed_past))

    # Assert
    assert actual == (False, False)


def test_患者資格_医療保険の順位1を指定すると_生成できる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()

    # Act
    actual = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Assert
    assert actual.priority.value == 1


def test_患者資格_医療保険の順位2を指定すると_検証エラーになる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()

    # Act / Assert
    with pytest.raises(InsuranceCoveragePriorityError):
        _create_coverage(
            coverage_type=CoverageType.INSURANCE,
            priority=2,
            corporate_id=corporate_id,
            patient_id=patient_id,
        )


def test_患者資格競合サービス_医療保険が同一期間に重複すると_競合エラーになる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Act / Assert
    with pytest.raises(CoveragePeriodConflictError):
        PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_医療保険の期間が重ならなければ_併用できる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        period=_create_period(date(2026, 7, 1), date(2026, 7, 31)),
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        period=_create_period(date(2026, 8, 1), None),
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_医療保険と公費が同一期間でも_併用できる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.INSURANCE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_同一順位の公費が重複すると_競合エラーになる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Act / Assert
    with pytest.raises(CoveragePeriodConflictError):
        PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_同一順位の公費でも期間が重ならなければ_併用できる() -> (
    None
):
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        period=_create_period(date(2026, 7, 1), date(2026, 7, 31)),
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        period=_create_period(date(2026, 8, 1), None),
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_異なる順位の公費は同一期間でも_併用できる() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=2,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_無効化済みの既存資格は_競合しない() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        deactivated_on=_VALID_FROM,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_候補自身が無効なら_競合しない() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
        deactivated_on=_VALID_FROM,
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


def test_患者資格競合サービス_別患者の同一順位資格は_競合しない() -> None:
    # Arrange
    corporate_id = CorporateId.generate()
    existing = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=PatientId.generate(),
    )
    candidate = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=PatientId.generate(),
    )

    # Act / Assert
    PatientCoverageConflictService().ensure_no_conflict(candidate, [existing])


@pytest.mark.asyncio
async def test_患者資格Repository_別法人を指定すると_資格を返さない() -> None:
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id = CorporateId.generate()
    other_corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    coverage = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_id,
    )
    await repository.save(coverage)

    # Act
    actual = await repository.get(
        corporate_id=other_corporate_id,
        coverage_id=coverage.id,
    )
    listed = await repository.list_by_patient(
        corporate_id=other_corporate_id,
        patient_id=patient_id,
    )

    # Assert
    assert (actual, listed) == (None, [])


@pytest.mark.asyncio
async def test_患者資格Repository_患者を指定すると_対象患者だけを返す() -> None:
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id = CorporateId.generate()
    patient_a_id = PatientId.generate()
    patient_b_id = PatientId.generate()
    coverage_a = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_a_id,
    )
    coverage_b = _create_coverage(
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        priority=1,
        corporate_id=corporate_id,
        patient_id=patient_b_id,
    )
    await repository.save(coverage_a)
    await repository.save(coverage_b)

    # Act
    actual = await repository.list_by_patient(
        corporate_id=corporate_id,
        patient_id=patient_a_id,
    )

    # Assert
    assert [item.id for item in actual] == [coverage_a.id]
