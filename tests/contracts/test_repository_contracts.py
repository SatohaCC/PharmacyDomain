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
from datetime import UTC, date, datetime

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
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.dispensing.primitives import (
    DispensingCancellationReason,
    DispensingId,
)
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.repository import (
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.medicine_catalog.exceptions import (
    MedicineEffectivePeriodConflictError,
)
from app.domain.medicine_catalog.repository import MedicineCatalogRepository
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
)
from app.domain.patient.repository import PatientExternalIdentifierRepository
from app.domain.prescription.exceptions import (
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionId,
    PrescriptionSourceType,
)
from app.domain.prescription.repository import PrescriptionRepository
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_record,
)
from tests.factories.medicine_catalog_factory import (
    create_identifier,
    create_medicine,
)
from tests.factories.prescription_factory import create_prescription

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
_PRESCRIPTION_REPOSITORIES = _implementations(PrescriptionRepository)
_DISPENSING_REPOSITORIES = _implementations(DispensingProcessRepository)
_MEDICATION_HISTORY_REPOSITORIES = _implementations(MedicationHistoryRepository)
_PROFILE_REPOSITORIES = _implementations(PatientMedicalProfileRepository)
_MEDICINE_CATALOG_REPOSITORIES = _implementations(MedicineCatalogRepository)


def test_契約テストの対象実装が_1件以上見つかる() -> None:
    """自動列挙が壊れると全契約テストが空振りするため、件数自体を固定する。"""
    # Arrange / Act / Assert
    assert _EXTERNAL_IDENTIFIER_REPOSITORIES != []
    assert _PATIENT_COVERAGE_REPOSITORIES != []
    assert _PRESCRIPTION_REPOSITORIES != []
    assert _DISPENSING_REPOSITORIES != []
    assert _MEDICATION_HISTORY_REPOSITORIES != []
    assert _PROFILE_REPOSITORIES != []
    assert _MEDICINE_CATALOG_REPOSITORIES != []


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


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋保存_電子処方箋の引換番号が重複すると_エラーになる(
    repository_type: type[PrescriptionRepository],
) -> None:
    """引換番号は電子処方箋管理サービスが発行する一意な番号。重複は二重取り込み。"""
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    await repository.save(
        create_prescription(
            corporate_id=corporate_id,
            source_type=PrescriptionSourceType.ELECTRONIC,
            document_number="1234567890123456",
        )
    )

    # Act / Assert
    with pytest.raises(PrescriptionDocumentNumberAlreadyExistsError):
        await repository.save(
            create_prescription(
                corporate_id=corporate_id,
                source_type=PrescriptionSourceType.ELECTRONIC,
                document_number="1234567890123456",
            )
        )


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋保存_紙処方箋の番号は_重複してもエラーにならない(
    repository_type: type[PrescriptionRepository],
) -> None:
    """紙の番号は医療機関ごとの採番なので、別の医療機関が同じ番号を採番しうる。

    ここで一意性を課すと正当な処方箋を拒否することになる。
    """
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    await repository.save(
        create_prescription(
            corporate_id=corporate_id,
            source_type=PrescriptionSourceType.PAPER_QR,
            document_number="0001",
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        create_prescription(
            corporate_id=corporate_id,
            source_type=PrescriptionSourceType.PAPER_QR,
            document_number="0001",
        )
    )


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋保存_別法人なら_同じ引換番号でもエラーにならない(
    repository_type: type[PrescriptionRepository],
) -> None:
    """一意性は法人境界の内側でのみ課す。"""
    # Arrange
    repository = repository_type()
    await repository.save(
        create_prescription(
            corporate_id=CorporateId.generate(),
            source_type=PrescriptionSourceType.ELECTRONIC,
            document_number="1234567890123456",
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        create_prescription(
            corporate_id=CorporateId.generate(),
            source_type=PrescriptionSourceType.ELECTRONIC,
            document_number="1234567890123456",
        )
    )


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋保存_同じ集約IDの状態変更は_自己衝突しない(
    repository_type: type[PrescriptionRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    prescription = create_prescription(
        corporate_id=corporate_id,
        source_type=PrescriptionSourceType.ELECTRONIC,
        document_number="1234567890123456",
    )
    await repository.save(prescription)

    # Act
    await repository.save(prescription.ready_for_dispensing())

    # Assert
    stored = await repository.get(
        corporate_id=corporate_id, prescription_id=prescription.id
    )
    assert stored is not None
    assert stored.status.name == "READY_FOR_DISPENSING"


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋取得_別法人の処方箋は_存在しないものとして扱われる(
    repository_type: type[PrescriptionRepository],
) -> None:
    """他テナントのデータは403ではなく404相当に畳む（存在を漏らさない）。"""
    # Arrange
    repository = repository_type()
    prescription = create_prescription(corporate_id=CorporateId.generate())
    await repository.save(prescription)

    # Act
    actual = await repository.get(
        corporate_id=CorporateId.generate(), prescription_id=prescription.id
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type", _PRESCRIPTION_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_処方箋の引換番号検索_別法人の処方箋は_見つからない(
    repository_type: type[PrescriptionRepository],
) -> None:
    # Arrange
    repository = repository_type()
    await repository.save(
        create_prescription(
            corporate_id=CorporateId.generate(),
            source_type=PrescriptionSourceType.ELECTRONIC,
            document_number="1234567890123456",
        )
    )

    # Act
    actual = await repository.get_by_document_number(
        corporate_id=CorporateId.generate(),
        document_number=PrescriptionDocumentNumber("1234567890123456"),
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤保存_同一処方箋に同じ回数のセッションがあると_拒否される(
    repository_type: type[DispensingProcessRepository],
) -> None:
    """同じ回が二重登録されると、調剤基本料の算定も薬歴の記録も二重になる。"""
    # Arrange
    repository = repository_type()
    corporate_id, prescription_id = CorporateId.generate(), PrescriptionId.generate()
    await repository.save(
        create_dispensing(
            corporate_id=corporate_id, prescription_id=prescription_id, iteration=1
        )
    )

    # Act / Assert
    with pytest.raises(DispensingAlreadyExistsError):
        await repository.save(
            create_dispensing(
                corporate_id=corporate_id, prescription_id=prescription_id, iteration=1
            )
        )


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤保存_回数が異なれば_同一処方箋でも保存できる(
    repository_type: type[DispensingProcessRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, prescription_id = CorporateId.generate(), PrescriptionId.generate()
    await repository.save(
        create_dispensing(
            corporate_id=corporate_id, prescription_id=prescription_id, iteration=1
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        create_dispensing(
            corporate_id=corporate_id, prescription_id=prescription_id, iteration=2
        )
    )


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤保存_別法人なら_同じ回数でも競合しない(
    repository_type: type[DispensingProcessRepository],
) -> None:
    # Arrange
    repository = repository_type()
    prescription_id = PrescriptionId.generate()
    await repository.save(
        create_dispensing(
            corporate_id=CorporateId.generate(),
            prescription_id=prescription_id,
            iteration=1,
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        create_dispensing(
            corporate_id=CorporateId.generate(),
            prescription_id=prescription_id,
            iteration=1,
        )
    )


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤保存_同じセッションの状態変更は_自分自身と競合しない(
    repository_type: type[DispensingProcessRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    process = create_dispensing(corporate_id=corporate_id)
    await repository.save(process)

    # Act
    await repository.save(
        process.cancel(DispensingCancellationReason("患者都合により中止した。"))
    )

    # Assert
    stored = await repository.get(corporate_id=corporate_id, dispensing_id=process.id)
    assert stored is not None
    assert stored.status.name == "CANCELLED"


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤一覧_調剤回数の昇順で返る(
    repository_type: type[DispensingProcessRepository],
) -> None:
    """呼び出し側が並べ替えを再実装しなくて済むよう、順序を契約にする。"""
    # Arrange
    repository = repository_type()
    corporate_id, prescription_id = CorporateId.generate(), PrescriptionId.generate()
    for iteration in (3, 1, 2):
        await repository.save(
            create_dispensing(
                corporate_id=corporate_id,
                prescription_id=prescription_id,
                iteration=iteration,
            )
        )

    # Act
    actual = await repository.list_by_prescription(
        corporate_id=corporate_id, prescription_id=prescription_id
    )

    # Assert
    assert [item.iteration.value for item in actual] == [1, 2, 3]


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤一覧_別法人のセッションは_含まれない(
    repository_type: type[DispensingProcessRepository],
) -> None:
    # Arrange
    repository = repository_type()
    prescription_id = PrescriptionId.generate()
    await repository.save(
        create_dispensing(
            corporate_id=CorporateId.generate(), prescription_id=prescription_id
        )
    )

    # Act
    actual = await repository.list_by_prescription(
        corporate_id=CorporateId.generate(), prescription_id=prescription_id
    )

    # Assert
    assert actual == []


@pytest.mark.parametrize(
    "repository_type", _DISPENSING_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_調剤取得_別法人のセッションは_存在しないものとして扱われる(
    repository_type: type[DispensingProcessRepository],
) -> None:
    """他テナントのデータは403ではなく404相当に畳む（存在を漏らさない）。"""
    # Arrange
    repository = repository_type()
    process = create_dispensing(corporate_id=CorporateId.generate())
    await repository.save(process)

    # Act
    actual = await repository.get(
        corporate_id=CorporateId.generate(), dispensing_id=process.id
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴保存_同一調剤に確定済が2件目だと_拒否される(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    """1回の調剤への指導記録が二重になると、算定も頭書きの投影も二重になる。"""
    # Arrange
    repository = repository_type()
    corporate_id, dispensing_id = CorporateId.generate(), DispensingId.generate()
    await repository.save(
        create_record(corporate_id=corporate_id, dispensing_id=dispensing_id).finalize()
    )

    # Act / Assert
    with pytest.raises(MedicationHistoryAlreadyExistsError):
        await repository.save(
            create_record(
                corporate_id=corporate_id, dispensing_id=dispensing_id
            ).finalize()
        )


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴保存_下書きは_同一調剤に複数あってよい(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    """書きかけを複数持つのは正当。制限すると入力途中の記録を作れなくなる。"""
    # Arrange
    repository = repository_type()
    corporate_id, dispensing_id = CorporateId.generate(), DispensingId.generate()
    await repository.save(
        create_record(corporate_id=corporate_id, dispensing_id=dispensing_id)
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        create_record(corporate_id=corporate_id, dispensing_id=dispensing_id)
    )


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴保存_同じ薬歴の確定は_自分自身と競合しない(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id = CorporateId.generate()
    record = create_record(corporate_id=corporate_id)
    await repository.save(record)

    # Act
    await repository.save(record.finalize())

    # Assert
    stored = await repository.get(corporate_id=corporate_id, record_id=record.id)
    assert stored is not None
    assert stored.is_finalized


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴の調剤検索_下書きは_返らない(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    """確定済だけが調剤に対する正式な指導記録である。"""
    # Arrange
    repository = repository_type()
    corporate_id, dispensing_id = CorporateId.generate(), DispensingId.generate()
    await repository.save(
        create_record(corporate_id=corporate_id, dispensing_id=dispensing_id)
    )

    # Act
    actual = await repository.get_by_dispensing(
        corporate_id=corporate_id, dispensing_id=dispensing_id
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴一覧_指導日時の降順で返る(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    """画面は新しい順に見る。頭書きの再構築側が昇順へ並べ替えるので依存しない。"""
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    for day in (1, 20, 10):
        await repository.save(
            create_record(
                corporate_id=corporate_id,
                patient_id=patient_id,
                counseled_at=datetime(2026, 8, day, 5, 0, tzinfo=UTC),
            )
        )

    # Act
    actual = await repository.list_by_patient(
        corporate_id=corporate_id, patient_id=patient_id
    )

    # Assert
    assert [item.counseled_at.value.day for item in actual] == [20, 10, 1]


@pytest.mark.parametrize(
    "repository_type",
    _MEDICATION_HISTORY_REPOSITORIES,
    ids=lambda cls: cls.__name__,
)
async def test_薬歴取得_別法人の薬歴は_存在しないものとして扱われる(
    repository_type: type[MedicationHistoryRepository],
) -> None:
    """他テナントのデータは403ではなく404相当に畳む（存在を漏らさない）。"""
    # Arrange
    repository = repository_type()
    record = create_record(corporate_id=CorporateId.generate())
    await repository.save(record)

    # Act
    actual = await repository.get(
        corporate_id=CorporateId.generate(), record_id=record.id
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type", _PROFILE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_頭書き保存_同一患者に2件目は_拒否される(
    repository_type: type[PatientMedicalProfileRepository],
) -> None:
    """頭書きが2件あると、どちらが投影結果かが決まらなくなる。"""
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    await repository.save(
        PatientMedicalProfile.empty_for(
            corporate_id=corporate_id, patient_id=patient_id
        )
    )

    # Act / Assert
    with pytest.raises(PatientMedicalProfileAlreadyExistsError):
        await repository.save(
            PatientMedicalProfile.empty_for(
                corporate_id=corporate_id, patient_id=patient_id
            )
        )


@pytest.mark.parametrize(
    "repository_type", _PROFILE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_頭書き保存_別法人なら_同じ患者でも競合しない(
    repository_type: type[PatientMedicalProfileRepository],
) -> None:
    # Arrange
    repository = repository_type()
    patient_id = PatientId.generate()
    await repository.save(
        PatientMedicalProfile.empty_for(
            corporate_id=CorporateId.generate(), patient_id=patient_id
        )
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(
        PatientMedicalProfile.empty_for(
            corporate_id=CorporateId.generate(), patient_id=patient_id
        )
    )


@pytest.mark.parametrize(
    "repository_type", _PROFILE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_頭書き保存_同じ頭書きの更新は_自分自身と競合しない(
    repository_type: type[PatientMedicalProfileRepository],
) -> None:
    # Arrange
    repository = repository_type()
    corporate_id, patient_id = CorporateId.generate(), PatientId.generate()
    profile = PatientMedicalProfile.empty_for(
        corporate_id=corporate_id, patient_id=patient_id
    )
    await repository.save(profile)
    record = create_record(
        corporate_id=corporate_id,
        patient_id=patient_id,
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),)),
    ).finalize()

    # Act
    await repository.save(profile.apply(record))

    # Assert
    stored = await repository.get_by_patient(
        corporate_id=corporate_id, patient_id=patient_id
    )
    assert stored is not None
    assert len(stored.allergies) == 1


@pytest.mark.parametrize(
    "repository_type", _PROFILE_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_頭書き取得_未投影の患者は_Noneが返る(
    repository_type: type[PatientMedicalProfileRepository],
) -> None:
    """``None`` は欠損ではなく「まだ投影されていない」を意味する。"""
    # Arrange
    repository = repository_type()

    # Act
    actual = await repository.get_by_patient(
        corporate_id=CorporateId.generate(), patient_id=PatientId.generate()
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ保存_同じ薬品コードで期間が重なると_拒否される(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    """重なると、ある日付で引いたときに2行返り「その日のマスタ」が定まらない。"""
    # Arrange
    repository = repository_type()
    await repository.save(
        create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
    )

    # Act / Assert
    with pytest.raises(MedicineEffectivePeriodConflictError):
        await repository.save(
            create_medicine(listed_on=date(2026, 3, 31), withdrawn_on=None)
        )


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ保存_期間が隣接するだけなら_保存できる(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    """改定で行が入れ替わるとき、旧行の期限翌日から新行が始まる。"""
    # Arrange
    repository = repository_type()
    await repository.save(
        create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
    )

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(create_medicine(listed_on=date(2026, 4, 1)))


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ保存_別の薬品コードなら_期間が重なってよい(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    # Arrange
    repository = repository_type()
    await repository.save(create_medicine())

    # Act / Assert: 例外を送出しないこと自体が表明
    await repository.save(create_medicine(code="1124017F1030", name="別の薬"))


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ検索_適用日で_返る行が変わる(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    """麻薬指定も経過措置も時点で変わる。「今」で引くと過去の処方を誤判定する。"""
    # Arrange
    repository = repository_type()
    await repository.save(
        create_medicine(
            listed_on=date(2020, 4, 1),
            withdrawn_on=date(2026, 3, 31),
            has_dosage_limit=False,
        )
    )
    await repository.save(
        create_medicine(listed_on=date(2026, 4, 1), has_dosage_limit=True)
    )
    identifier = create_identifier()

    # Act
    before = await repository.find_effective(
        identifier=identifier, as_of=date(2026, 3, 31)
    )
    after = await repository.find_effective(
        identifier=identifier, as_of=date(2026, 4, 1)
    )

    # Assert
    assert before is not None
    assert after is not None
    assert not before.has_dosage_limit
    assert after.has_dosage_limit


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ検索_収載前の日付では_見つからない(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    # Arrange
    repository = repository_type()
    await repository.save(create_medicine(listed_on=date(2026, 4, 1)))

    # Act
    actual = await repository.find_effective(
        identifier=create_identifier(), as_of=date(2026, 3, 31)
    )

    # Assert
    assert actual is None


@pytest.mark.parametrize(
    "repository_type", _MEDICINE_CATALOG_REPOSITORIES, ids=lambda cls: cls.__name__
)
async def test_医薬品マスタ一覧_収載日の昇順で返る(
    repository_type: type[MedicineCatalogRepository],
) -> None:
    # Arrange
    repository = repository_type()
    await repository.save(create_medicine(listed_on=date(2026, 4, 1)))
    await repository.save(
        create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
    )

    # Act
    actual = await repository.list_versions(create_identifier())

    # Assert
    assert [item.effective_period.listed_on.value for item in actual] == [
        date(2020, 4, 1),
        date(2026, 4, 1),
    ]
