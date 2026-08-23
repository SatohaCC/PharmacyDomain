"""Repository Protocol の `save()` 契約を、全実装に対して検証する契約テスト。

`tools/check_fake_conformance.py` は「メンバが実装されているか」しか見ない。
実装済みだが docstring に書かれた契約を無視している `save()` は素通りするため、
契約そのものはここで固定する。

実装クラスは `tests/fakes/` を走査して**自動列挙**する。新しいフェイクを足すと
登録を忘れようがなく検査対象になり、契約を満たさなければ pytest が落ちる。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from datetime import date

import pytest

import tests.fakes
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.primitives import (
    CoverageActivatedOn,
    CoverageActivation,
    CoverageDeactivatedOn,
    CoveragePeriod,
    CoveragePriority,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    PublicExpenseCoverageDetails,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
)
from app.domain.patient.repository import PatientExternalIdentifierRepository

_VALID_FROM = date(2026, 8, 1)
_VALID_TO = date(2026, 8, 31)


def _implementations(protocol: type[object]) -> list[type[object]]:
    """tests/fakes/ 配下から、その Protocol を明示継承した実装クラスを列挙する。

    `issubclass` は `@runtime_checkable` でない Protocol に使えないため、
    MRO に Protocol が含まれるかで判定する。明示継承していることは
    `tools/check_fake_conformance.py` が別途強制している。
    """
    found: list[type[object]] = []
    for module_info in pkgutil.walk_packages(
        tests.fakes.__path__, prefix=f"{tests.fakes.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for cls in vars(module).values():
            if not inspect.isclass(cls) or cls.__module__ != module_info.name:
                continue
            if getattr(cls, "_is_protocol", False):
                continue
            if protocol in cls.__mro__:
                found.append(cls)
    return found


_EXTERNAL_IDENTIFIER_REPOSITORIES = _implementations(
    PatientExternalIdentifierRepository
)
_PATIENT_COVERAGE_REPOSITORIES = _implementations(PatientCoverageRepository)


def test_契約テストの対象実装が_1件以上見つかる() -> None:
    """自動列挙が壊れると全契約テストが空振りするため、件数自体を固定する。"""
    # Arrange / Act / Assert
    assert _EXTERNAL_IDENTIFIER_REPOSITORIES != []
    assert _PATIENT_COVERAGE_REPOSITORIES != []


def _create_identifier(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId | None = None,
    external_patient_id: str = "EXT-001",
) -> PatientExternalIdentifier:
    """テスト用の外部患者ID対応付けを生成する。"""
    return PatientExternalIdentifier.create(
        corporate_id=corporate_id,
        patient_id=patient_id if patient_id is not None else PatientId.generate(),
        system_name=ExternalSystemName("レセコンA"),
        external_patient_id=ExternalPatientId(external_patient_id),
    )


def _create_coverage(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    priority: int = 1,
    valid_from: date = _VALID_FROM,
    valid_to: date | None = _VALID_TO,
    deactivated_on: date | None = None,
) -> PatientCoverage:
    """テスト用の公費資格を生成する。"""
    return PatientCoverage.create(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_type=CoverageType.PUBLIC_EXPENSE,
        period=CoveragePeriod(
            valid_from=CoverageValidFrom(valid_from),
            valid_to=CoverageValidTo(valid_to) if valid_to is not None else None,
        ),
        activation=CoverageActivation(
            activated_on=CoverageActivatedOn(valid_from),
            deactivated_on=(
                CoverageDeactivatedOn(deactivated_on)
                if deactivated_on is not None
                else None
            ),
        ),
        priority=CoveragePriority(priority),
        public_expense_details=PublicExpenseCoverageDetails(
            payer_number=PublicPayerNumber(f"1234567{priority}"),
            recipient_number=PublicRecipientNumber(f"123456{priority}"),
        ),
    )


@pytest.mark.parametrize(
    "repository_type", _EXTERNAL_IDENTIFIER_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_外部患者ID保存_有効行が既にあると_重複エラーになる(
    repository_type: type[PatientExternalIdentifierRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    await repository.save(_create_identifier(corporate_id=corporate_id))

    # Act / Assert
    with pytest.raises(PatientExternalIdentifierAlreadyExistsError):
        await repository.save(_create_identifier(corporate_id=corporate_id))


@pytest.mark.parametrize(
    "repository_type", _EXTERNAL_IDENTIFIER_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_外部患者ID保存_無効化済みの行は_衝突扱いにならない(
    repository_type: type[PatientExternalIdentifierRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    wrong = _create_identifier(corporate_id=corporate_id)
    await repository.save(wrong)
    await repository.save(wrong.deactivate())

    # Act
    correct = _create_identifier(corporate_id=corporate_id)
    await repository.save(correct)

    # Assert: 誤った患者から正しい患者へ付け替えられる
    assert (
        await repository.get_active_by_source(
            corporate_id=corporate_id,
            system_name=ExternalSystemName("レセコンA"),
            external_patient_id=ExternalPatientId("EXT-001"),
        )
    ) == correct


@pytest.mark.parametrize(
    "repository_type", _EXTERNAL_IDENTIFIER_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_外部患者ID保存_同じ集約IDの再保存は_自己衝突しない(
    repository_type: type[PatientExternalIdentifierRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    identifier = _create_identifier(corporate_id=corporate_id)
    await repository.save(identifier)

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(identifier)


@pytest.mark.parametrize(
    "repository_type", _EXTERNAL_IDENTIFIER_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_外部患者ID保存_別法人の同じ外部IDは_衝突しない(
    repository_type: type[PatientExternalIdentifierRepository],
) -> None:
    # Arrange
    repository = repository_type()
    await repository.save(_create_identifier(corporate_id=CorporateId.generate()))

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(_create_identifier(corporate_id=CorporateId.generate()))


@pytest.mark.parametrize(
    "repository_type", _PATIENT_COVERAGE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_患者資格保存_同一順位の実効期間が重なると_競合エラーになる(
    repository_type: type[PatientCoverageRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    await repository.save(
        _create_coverage(corporate_id=corporate_id, patient_id=patient_id)
    )

    # Act / Assert
    with pytest.raises(CoveragePeriodConflictError):
        await repository.save(
            _create_coverage(corporate_id=corporate_id, patient_id=patient_id)
        )


@pytest.mark.parametrize(
    "repository_type", _PATIENT_COVERAGE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_患者資格保存_異なる順位の公費は_競合しない(
    repository_type: type[PatientCoverageRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    await repository.save(
        _create_coverage(corporate_id=corporate_id, patient_id=patient_id, priority=1)
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        _create_coverage(corporate_id=corporate_id, patient_id=patient_id, priority=2)
    )


@pytest.mark.parametrize(
    "repository_type", _PATIENT_COVERAGE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_患者資格保存_同じ集約IDの期間変更は_自己衝突しない(
    repository_type: type[PatientCoverageRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    coverage = _create_coverage(corporate_id=corporate_id, patient_id=patient_id)
    await repository.save(coverage)

    # Act
    extended = coverage.change_period(
        CoveragePeriod(
            valid_from=CoverageValidFrom(_VALID_FROM),
            valid_to=CoverageValidTo(date(2026, 9, 30)),
        )
    )
    await repository.save(extended)

    # Assert
    stored = await repository.get(corporate_id=corporate_id, coverage_id=coverage.id)
    assert stored is not None
    assert stored.period.valid_to is not None
    assert stored.period.valid_to.value == date(2026, 9, 30)


@pytest.mark.parametrize(
    "repository_type", _PATIENT_COVERAGE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_患者資格保存_無効化済みの既存資格とは_競合しない(
    repository_type: type[PatientCoverageRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    await repository.save(
        _create_coverage(
            corporate_id=corporate_id,
            patient_id=patient_id,
            deactivated_on=_VALID_FROM,
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        _create_coverage(corporate_id=corporate_id, patient_id=patient_id)
    )
