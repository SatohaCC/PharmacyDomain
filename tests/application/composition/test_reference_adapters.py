"""参照Boundaryの実アダプタのテスト。

主眼は2つ。

1. **他テナントを「存在しない」へ畳むこと。** 別法人のデータで
   ``AuthorizationError`` を出すと、その法人にそのIDが在ることが漏れる。
   店舗だけは Repository が法人IDを取らないので、比較の書き漏らしが
   そのままテナント境界の穴になる。全コンテキスト分を等しく確かめる。
2. **資格台帳の公費順位と処方箋の公費枠が別軸であること。** 対応表を持たない
   枠（特殊公費・第四公費）を安全側へ倒せているかは、実装を見ても分からない。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.composition.coverage_references import (
    CoveragePatientReferenceAdapter,
)
from app.application.composition.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.medication_history_references import (
    CounselorQualificationAdapter,
    DispensingSourceAdapter,
    MedicationHistoryStoreReferenceAdapter,
)
from app.application.composition.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStaffQualificationAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.composition.reception_references import (
    ReceptionPatientReferenceAdapter,
    ReceptionStoreReferenceAdapter,
)
from app.application.coverage.exceptions import CoveragePatientNotFoundError
from app.application.dispensing.exceptions import (
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
)
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
)
from app.application.prescription.exceptions import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionPharmacistNotFoundError,
    PrescriptionStoreNotFoundError,
)
from app.application.reception.exceptions import (
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
)
from app.domain.claim import (
    ClaimCoveragePriority,
    ClaimPublicPayerNumber,
    ClaimPublicRecipientNumber,
    PublicExpenseCoverageSnapshot,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.primitives import PrescriptionId, PrescriptionStatus
from app.domain.reception import (
    CoverageAppliedOn,
    CoverageRecordedAt,
    CoverageSelection,
    CoverageSelectionRecord,
    CoverageSelectionRecordId,
    OperatorPrincipalId,
    SelectedPublicExpenseSource,
    SourceCoverageId,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import create_prescription
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.in_memory_dispensing_process_repository import (
    InMemoryDispensingProcessRepository,
)
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository
from tests.fakes.in_memory_prescription_repository import InMemoryPrescriptionRepository
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository

_STORE_ADAPTERS = [
    pytest.param(
        PrescriptionStoreReferenceAdapter, PrescriptionStoreNotFoundError, id="処方箋"
    ),
    pytest.param(
        DispensingStoreReferenceAdapter, DispensingStoreNotFoundError, id="調剤"
    ),
    pytest.param(
        MedicationHistoryStoreReferenceAdapter,
        MedicationHistoryStoreNotFoundError,
        id="薬歴",
    ),
    pytest.param(ReceptionStoreReferenceAdapter, ReceptionStoreNotFoundError, id="受付"),
]

_PATIENT_ADAPTERS = [
    pytest.param(
        PrescriptionPatientReferenceAdapter,
        PrescriptionPatientNotFoundError,
        id="処方箋",
    ),
    pytest.param(
        ReceptionPatientReferenceAdapter, ReceptionPatientNotFoundError, id="受付"
    ),
    pytest.param(
        CoveragePatientReferenceAdapter, CoveragePatientNotFoundError, id="資格台帳"
    ),
]

_STAFF_ADAPTERS = [
    pytest.param(
        PrescriptionStaffQualificationAdapter,
        PrescriptionPharmacistNotFoundError,
        id="処方箋",
    ),
    pytest.param(
        DispensingStaffQualificationAdapter, DispensingStaffNotFoundError, id="調剤"
    ),
    pytest.param(
        CounselorQualificationAdapter, MedicationHistoryStaffNotFoundError, id="薬歴"
    ),
]


@pytest.mark.parametrize(("adapter_type", "error_type"), _STORE_ADAPTERS)
async def test_店舗参照_自法人の店舗なら_例外にならない(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """存在する自法人の店舗は通す。"""
    # Arrange
    corporate_id = CorporateId.generate()
    store = create_store(corporate_id=corporate_id)
    repository = InMemoryStoreRepository()
    await repository.save(store)

    # Act
    await adapter_type(repository).require_exists(
        corporate_id=corporate_id, store_id=store.id
    )

    # Assert
    del error_type


@pytest.mark.parametrize(("adapter_type", "error_type"), _STORE_ADAPTERS)
async def test_店舗参照_別法人の店舗は_存在しないものとして扱う(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """``StoreRepository.get()`` は法人IDを取らないので、比較を落とすと漏れる。"""
    # Arrange
    store = create_store(corporate_id=CorporateId.generate())
    repository = InMemoryStoreRepository()
    await repository.save(store)

    # Act & Assert
    with pytest.raises(error_type):
        await adapter_type(repository).require_exists(
            corporate_id=CorporateId.generate(), store_id=store.id
        )


@pytest.mark.parametrize(("adapter_type", "error_type"), _STORE_ADAPTERS)
async def test_店舗参照_未登録の店舗は_同じ例外になる(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """未存在と別法人を別の例外へ分けると、他テナントの存在が漏れる。"""
    # Arrange
    repository = InMemoryStoreRepository()

    # Act & Assert
    with pytest.raises(error_type):
        await adapter_type(repository).require_exists(
            corporate_id=CorporateId.generate(), store_id=StoreId.generate()
        )


@pytest.mark.parametrize(("adapter_type", "error_type"), _PATIENT_ADAPTERS)
async def test_患者参照_自法人の患者なら_例外にならない(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """存在する自法人の患者は通す。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient = create_patient(corporate_id=corporate_id)
    repository = InMemoryPatientRepository()
    await repository.save(patient)

    # Act
    await adapter_type(repository).require_exists(
        corporate_id=corporate_id, patient_id=patient.id
    )

    # Assert
    del error_type


@pytest.mark.parametrize(("adapter_type", "error_type"), _PATIENT_ADAPTERS)
async def test_患者参照_別法人の患者は_存在しないものとして扱う(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """他テナントの患者IDの存在を漏らさない。"""
    # Arrange
    patient = create_patient(corporate_id=CorporateId.generate())
    repository = InMemoryPatientRepository()
    await repository.save(patient)

    # Act & Assert
    with pytest.raises(error_type):
        await adapter_type(repository).require_exists(
            corporate_id=CorporateId.generate(), patient_id=patient.id
        )


@pytest.mark.parametrize(("adapter_type", "error_type"), _STAFF_ADAPTERS)
async def test_スタッフ資格_在籍していれば_保有資格をそのまま返す(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """判定を境界側で行わない。資格の中身をそのまま運ぶ。"""
    # Arrange
    corporate_id = CorporateId.generate()
    staff = create_staff(corporate_id=corporate_id)
    repository = InMemoryStaffRepository()
    await repository.save(staff)

    # Act
    qualifications = await adapter_type(repository).get_qualifications(
        corporate_id=corporate_id, staff_id=staff.id
    )

    # Assert
    assert qualifications == staff.qualifications
    del error_type


@pytest.mark.parametrize(("adapter_type", "error_type"), _STAFF_ADAPTERS)
async def test_スタッフ資格_別法人のスタッフは_存在しないものとして扱う(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """他テナントのスタッフIDの存在を漏らさない。"""
    # Arrange
    staff = create_staff(corporate_id=CorporateId.generate())
    repository = InMemoryStaffRepository()
    await repository.save(staff)

    # Act & Assert
    with pytest.raises(error_type):
        await adapter_type(repository).get_qualifications(
            corporate_id=CorporateId.generate(), staff_id=staff.id
        )


@pytest.mark.parametrize(("adapter_type", "error_type"), _STAFF_ADAPTERS)
async def test_スタッフ資格_未登録のスタッフは_同じ例外になる(
    adapter_type: type, error_type: type[Exception]
) -> None:
    """未存在と別法人を区別しない。"""
    # Arrange
    repository = InMemoryStaffRepository()

    # Act & Assert
    with pytest.raises(error_type):
        await adapter_type(repository).get_qualifications(
            corporate_id=CorporateId.generate(), staff_id=StaffId.generate()
        )


async def test_処方箋参照_自法人の処方箋なら_集約をそのまま返す() -> None:
    """調剤の整合性検証は処方箋の中身を要求するので、集約ごと運ぶ。"""
    # Arrange
    corporate_id = CorporateId.generate()
    prescription = create_prescription(corporate_id=corporate_id)
    repository = InMemoryPrescriptionRepository()
    await repository.save(prescription)

    # Act
    loaded = await PrescriptionSourceAdapter(repository).get_or_raise(
        corporate_id=corporate_id, prescription_id=prescription.id
    )

    # Assert
    assert loaded.id == prescription.id


async def test_処方箋参照_別法人の処方箋は_存在しないものとして扱う() -> None:
    """他テナントの処方箋IDの存在を漏らさない。"""
    # Arrange
    prescription = create_prescription(corporate_id=CorporateId.generate())
    repository = InMemoryPrescriptionRepository()
    await repository.save(prescription)

    # Act & Assert
    with pytest.raises(DispensingPrescriptionNotFoundError):
        await PrescriptionSourceAdapter(repository).get_or_raise(
            corporate_id=CorporateId.generate(), prescription_id=prescription.id
        )


async def test_処方箋完了_調剤済へ遷移させる() -> None:
    """調剤終了区分が来たら処方箋を閉じる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    prescription = create_prescription(corporate_id=corporate_id).ready_for_dispensing()
    repository = InMemoryPrescriptionRepository()
    await repository.save(prescription)

    # Act
    await PrescriptionSourceAdapter(repository).complete_dispensing(
        corporate_id=corporate_id, prescription_id=prescription.id
    )

    # Assert
    stored = await repository.get(
        corporate_id=corporate_id, prescription_id=prescription.id
    )
    assert stored is not None
    assert stored.status is PrescriptionStatus.DISPENSED


async def test_処方箋完了_すでに調剤済なら_二度目は何もしない() -> None:
    """分割・リフィルの各回が同じ処方箋を完了しうる。冪等でないと落ちる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    prescription = create_prescription(corporate_id=corporate_id).ready_for_dispensing()
    repository = InMemoryPrescriptionRepository()
    await repository.save(prescription)
    adapter = PrescriptionSourceAdapter(repository)
    await adapter.complete_dispensing(
        corporate_id=corporate_id, prescription_id=prescription.id
    )

    # Act
    await adapter.complete_dispensing(
        corporate_id=corporate_id, prescription_id=prescription.id
    )

    # Assert
    stored = await repository.get(
        corporate_id=corporate_id, prescription_id=prescription.id
    )
    assert stored is not None
    assert stored.status is PrescriptionStatus.DISPENSED


async def test_処方箋完了_未存在の処方箋は_404相当になる() -> None:
    """存在しない処方箋を黙って無視すると、調剤だけが残る。"""
    # Arrange
    repository = InMemoryPrescriptionRepository()

    # Act & Assert
    with pytest.raises(DispensingPrescriptionNotFoundError):
        await PrescriptionSourceAdapter(repository).complete_dispensing(
            corporate_id=CorporateId.generate(),
            prescription_id=PrescriptionId.generate(),
        )


async def test_調剤参照_自法人の調剤セッションなら_集約をそのまま返す() -> None:
    """薬歴と調剤の一致判定は本物の集約を要求する。"""
    # Arrange
    corporate_id = CorporateId.generate()
    process = create_dispensing(corporate_id=corporate_id)
    repository = InMemoryDispensingProcessRepository()
    await repository.save(process)

    # Act
    loaded = await DispensingSourceAdapter(repository).get_or_raise(
        corporate_id=corporate_id, dispensing_id=process.id
    )

    # Assert
    assert loaded.id == process.id


async def test_調剤参照_別法人の調剤セッションは_存在しないものとして扱う() -> None:
    """他テナントの調剤IDの存在を漏らさない。"""
    # Arrange
    process = create_dispensing(corporate_id=CorporateId.generate())
    repository = InMemoryDispensingProcessRepository()
    await repository.save(process)

    # Act & Assert
    with pytest.raises(MedicationHistoryDispensingNotFoundError):
        await DispensingSourceAdapter(repository).get_or_raise(
            corporate_id=CorporateId.generate(), dispensing_id=process.id
        )


async def test_調剤参照_未登録の調剤セッションは_同じ例外になる() -> None:
    """未存在と別法人を区別しない。"""
    # Arrange
    repository = InMemoryDispensingProcessRepository()

    # Act & Assert
    with pytest.raises(MedicationHistoryDispensingNotFoundError):
        await DispensingSourceAdapter(repository).get_or_raise(
            corporate_id=CorporateId.generate(), dispensing_id=DispensingId.generate()
        )


def _record_with_priorities(
    *,
    corporate_id: CorporateId,
    patient_id: PatientId,
    priorities: tuple[int, ...],
) -> CoverageSelectionRecord:
    """指定した公費順位だけを持つ資格選択履歴を作る。"""
    selection = CoverageSelection(
        insurance=None,
        public_expenses=tuple(
            SelectedPublicExpenseSource(
                source_coverage_id=SourceCoverageId.generate(),
                values=PublicExpenseCoverageSnapshot(
                    priority=ClaimCoveragePriority(priority),
                    payer_number=ClaimPublicPayerNumber(f"1234567{priority}"),
                    recipient_number=ClaimPublicRecipientNumber(f"123456{priority}"),
                ),
            )
            for priority in priorities
        ),
    )
    return CoverageSelectionRecord.create(
        corporate_id=corporate_id,
        store_id=StoreId.generate(),
        patient_id=patient_id,
        applied_on=CoverageAppliedOn(date(2026, 8, 23)),
        selection=selection,
        recorded_at=CoverageRecordedAt(datetime(2026, 8, 23, 1, 0, tzinfo=UTC)),
        recorded_by=OperatorPrincipalId("test-operator"),
    )


async def test_公費裏付け_第一から第三の順位が_処方箋の枠へ写る() -> None:
    """資格台帳の順位1〜3は、処方箋の第一〜第三公費に対応する。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    record = _record_with_priorities(
        corporate_id=corporate_id, patient_id=patient_id, priorities=(1, 2)
    )
    repository = InMemoryCoverageSelectionRecordRepository()
    await repository.save(record)

    # Act
    burden = await CoverageSelectionPublicExpenseAdapter(repository).available_burden(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_selection_record_id=record.id,
    )

    # Assert
    assert burden.first is True
    assert burden.second is True
    assert burden.third is False
    assert burden.special is False


async def test_公費裏付け_第四公費は_処方箋のどの枠も立てない() -> None:
    """処方箋側に第四公費の枠は無い。特殊公費へ流用すると別制度を名乗る。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    record = _record_with_priorities(
        corporate_id=corporate_id, patient_id=patient_id, priorities=(1, 2, 3, 4)
    )
    repository = InMemoryCoverageSelectionRecordRepository()
    await repository.save(record)

    # Act
    burden = await CoverageSelectionPublicExpenseAdapter(repository).available_burden(
        corporate_id=corporate_id,
        patient_id=patient_id,
        coverage_selection_record_id=record.id,
    )

    # Assert
    assert (burden.first, burden.second, burden.third) == (True, True, True)
    assert burden.special is False, "特殊公費は資格台帳から裏付けられない。"


async def test_公費裏付け_別患者の履歴は_存在しないものとして扱う() -> None:
    """患者を取り違えた履歴で公費負担が裏付けられてはならない。"""
    # Arrange
    corporate_id = CorporateId.generate()
    record = _record_with_priorities(
        corporate_id=corporate_id,
        patient_id=PatientId.generate(),
        priorities=(1,),
    )
    repository = InMemoryCoverageSelectionRecordRepository()
    await repository.save(record)

    # Act & Assert
    with pytest.raises(PrescriptionCoverageSelectionNotFoundError):
        await CoverageSelectionPublicExpenseAdapter(repository).available_burden(
            corporate_id=corporate_id,
            patient_id=PatientId.generate(),
            coverage_selection_record_id=record.id,
        )


async def test_公費裏付け_別法人の履歴は_存在しないものとして扱う() -> None:
    """他テナントの履歴IDの存在を漏らさない。"""
    # Arrange
    patient_id = PatientId.generate()
    record = _record_with_priorities(
        corporate_id=CorporateId.generate(),
        patient_id=patient_id,
        priorities=(1,),
    )
    repository = InMemoryCoverageSelectionRecordRepository()
    await repository.save(record)

    # Act & Assert
    with pytest.raises(PrescriptionCoverageSelectionNotFoundError):
        await CoverageSelectionPublicExpenseAdapter(repository).available_burden(
            corporate_id=CorporateId.generate(),
            patient_id=patient_id,
            coverage_selection_record_id=record.id,
        )


async def test_公費裏付け_未登録の履歴は_同じ例外になる() -> None:
    """未存在と別テナントを区別しない。"""
    # Arrange
    repository = InMemoryCoverageSelectionRecordRepository()

    # Act & Assert
    with pytest.raises(PrescriptionCoverageSelectionNotFoundError):
        await CoverageSelectionPublicExpenseAdapter(repository).available_burden(
            corporate_id=CorporateId.generate(),
            patient_id=PatientId.generate(),
            coverage_selection_record_id=CoverageSelectionRecordId.generate(),
        )
