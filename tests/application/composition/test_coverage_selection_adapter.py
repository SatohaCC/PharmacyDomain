"""Coverage台帳とReception境界を接続するアダプタのテスト。

ここだけが本物の ``PatientCoverage`` から ``CoverageSelection`` への変換を通す。
枠がIDと値を束ねているので、再検証は等価比較1本で済むことも合わせて固定する。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.composition.coverage_selection_adapter import (
    CoverageSelectionAdapter,
)
from app.application.reception.exceptions import ReceptionCoverageSelectionError
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import (
    CoverageActivatedOn,
    CoverageActivation,
    CoverageBenefitRatio,
    CoverageCode,
    CoverageDeactivatedOn,
    CoverageInsuredType,
    CoveragePeriod,
    CoveragePriority,
    CoverageSelectionService,
    CoverageSymbol,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    InsuranceCoverageDetails,
    InsurerNumber,
    PatientCoverage,
    PublicExpenseCoverageDetails,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.patient.primitives import PatientId
from app.domain.reception.primitives import CoverageAppliedOn
from tests.fakes.in_memory_patient_coverage_repository import (
    InMemoryPatientCoverageRepository,
)

_VALID_FROM = date(2026, 8, 1)
_VALID_TO = date(2026, 8, 31)
_APPLIED_ON = CoverageAppliedOn(date(2026, 8, 23))


def _create_activation(deactivated_on: date | None = None) -> CoverageActivation:
    """テスト用の台帳行有効区間を生成する。"""
    return CoverageActivation(
        activated_on=CoverageActivatedOn(_VALID_FROM),
        deactivated_on=(
            CoverageDeactivatedOn(deactivated_on)
            if deactivated_on is not None
            else None
        ),
    )


def _create_period() -> CoveragePeriod:
    """テスト用の適用期間を生成する。"""
    return CoveragePeriod(
        valid_from=CoverageValidFrom(_VALID_FROM),
        valid_to=CoverageValidTo(_VALID_TO),
    )


def _create_insurance(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    benefit_ratio: int = 70,
) -> PatientCoverage:
    """テスト用の医療保険資格を生成する。"""
    return PatientCoverage.create(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_type=CoverageType.INSURANCE,
        period=_create_period(),
        activation=_create_activation(),
        priority=CoveragePriority(1),
        insurance_details=InsuranceCoverageDetails(
            insurer_number=InsurerNumber("01130012"),
            insured_symbol=CoverageSymbol("A"),
            insured_number=CoverageCode("456"),
            insured_type=CoverageInsuredType.SELF,
            benefit_ratio=CoverageBenefitRatio(benefit_ratio),
        ),
    )


def _create_public(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    priority: int,
) -> PatientCoverage:
    """テスト用の公費資格を生成する。"""
    return PatientCoverage.create(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        period=_create_period(),
        activation=_create_activation(),
        priority=CoveragePriority(priority),
        public_expense_details=PublicExpenseCoverageDetails(
            payer_number=PublicPayerNumber(f"1234567{priority}"),
            recipient_number=PublicRecipientNumber(f"123456{priority}"),
        ),
    )


def _create_adapter(
    repository: InMemoryPatientCoverageRepository,
) -> CoverageSelectionAdapter:
    """本物の Domain Service を使うアダプタを組み立てる。"""
    return CoverageSelectionAdapter(repository, CoverageSelectionService())


async def test_資格選択アダプタ_医療保険と公費を渡すと_枠ごとに元IDが束ねられる() -> (
    None
):
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    insurance = _create_insurance(corporate_id=corporate_id, patient_id=patient_id)
    public = _create_public(
        corporate_id=corporate_id, patient_id=patient_id, priority=1
    )
    await repository.save(insurance)
    await repository.save(public)

    # Act
    actual = await _create_adapter(repository).build_selection(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_ids=(str(public.id.value), str(insurance.id.value)),
        applied_on=_APPLIED_ON,
    )

    # Assert: 入力順に関わらず、医療保険→公費順位順で導出される
    assert actual.insurance is not None
    assert actual.insurance.source_coverage_id.value == insurance.id.value
    assert actual.source_coverage_ids == (
        actual.insurance.source_coverage_id,
        actual.public_expenses[0].source_coverage_id,
    )
    assert actual.public_expenses[0].source_coverage_id.value == public.id.value


async def test_資格選択アダプタ_同じ資格を再検証すると_選択を再構築してTrueを返す() -> (
    None
):
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    insurance = _create_insurance(corporate_id=corporate_id, patient_id=patient_id)
    await repository.save(insurance)
    adapter = _create_adapter(repository)
    selection = await adapter.build_selection(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_ids=(str(insurance.id.value),),
        applied_on=_APPLIED_ON,
    )

    # Act
    actual = await adapter.is_selection_valid(
        corporate_id=corporate_id,
        patient_id=patient_id,
        selection=selection,
        applied_on=_APPLIED_ON,
    )

    # Assert
    assert actual is True


async def test_資格選択アダプタ_台帳の給付割合が変わると_再検証がFalseになる() -> None:
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    insurance = _create_insurance(corporate_id=corporate_id, patient_id=patient_id)
    await repository.save(insurance)
    adapter = _create_adapter(repository)
    selection = await adapter.build_selection(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_ids=(str(insurance.id.value),),
        applied_on=_APPLIED_ON,
    )
    # 台帳側の値だけを差し替える（IDは同じまま）
    repository.items[insurance.id] = _create_insurance(
        corporate_id=corporate_id, patient_id=patient_id, benefit_ratio=90
    )

    # Act
    actual = await adapter.is_selection_valid(
        corporate_id=corporate_id,
        patient_id=patient_id,
        selection=selection,
        applied_on=_APPLIED_ON,
    )

    # Assert: IDが同じでも値が変われば真正でない
    assert actual is False


async def test_資格選択アダプタ_適用日時点で無効化されていると_再検証がFalseになる() -> (
    None
):
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    insurance = _create_insurance(corporate_id=corporate_id, patient_id=patient_id)
    await repository.save(insurance)
    adapter = _create_adapter(repository)
    selection = await adapter.build_selection(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_ids=(str(insurance.id.value),),
        applied_on=_APPLIED_ON,
    )
    await repository.save(
        insurance.deactivate(CoverageDeactivatedOn(date(2026, 8, 10)))
    )

    # Act
    actual = await adapter.is_selection_valid(
        corporate_id=corporate_id,
        patient_id=patient_id,
        selection=selection,
        applied_on=_APPLIED_ON,
    )

    # Assert
    assert actual is False


async def test_資格選択アダプタ_別法人の資格を指定すると_選択エラーになる() -> None:
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    insurance = _create_insurance(corporate_id=corporate_id, patient_id=patient_id)
    await repository.save(insurance)

    # Act / Assert: 他テナントの資格の存在を漏らさない
    with pytest.raises(ReceptionCoverageSelectionError):
        await _create_adapter(repository).build_selection(
            corporate_id=CorporateId.generate(),
            patient_id=patient_id,
            coverage_ids=(str(insurance.id.value),),
            applied_on=_APPLIED_ON,
        )


async def test_資格選択アダプタ_公費順位が飛んでいると_選択エラーになる() -> None:
    # Arrange
    repository = InMemoryPatientCoverageRepository()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    second_only = _create_public(
        corporate_id=corporate_id, patient_id=patient_id, priority=2
    )
    await repository.save(second_only)

    # Act / Assert: 第一公費が空の組み合わせは凍結前に弾く
    with pytest.raises(ReceptionCoverageSelectionError):
        await _create_adapter(repository).build_selection(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_ids=(str(second_only.id.value),),
            applied_on=_APPLIED_ON,
        )
