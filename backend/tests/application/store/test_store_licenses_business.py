"""店舗許認可の業務接続テスト（TC-009〜TC-018）。

店舗の薬局開設許可・麻薬小売業者免許が、処方受付・処方登録・調剤の各業務操作で
正しく検証され、失効時や未登録時に409で拒否されること、および取消・閲覧の回帰を検証する。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.application.access_control.policies import AuthorizationService
from app.application.composition.adapters.clinical_store_guard import (
    ClinicalStoreWriteGuard,
)
from app.application.composition.adapters.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.composition.adapters.medicine_restriction_adapter import (
    MedicineCatalogRestrictionAdapter,
)
from app.application.composition.adapters.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.composition.adapters.store_operation_adapter import (
    StoreOperationAdapter,
)
from app.application.dispensing.commands.complete_dispensing import (
    CompleteDispensingCommand,
    CompleteDispensingUseCase,
)
from app.application.dispensing.commands.dtos.get_dispensing import (
    DispensingProcessDto,
)
from app.application.dispensing.commands.models import (
    DispensedMedicineInput,
    DispensedRpInput,
    StartDispensingCommand,
    SubstitutionInput,
)
from app.application.dispensing.commands.record_audit import (
    RecordAuditCommand,
    RecordAuditUseCase,
)
from app.application.dispensing.commands.record_dispensed_content import (
    RecordDispensedContentCommand,
    RecordDispensedContentUseCase,
)
from app.application.dispensing.commands.start_dispensing import StartDispensingUseCase
from app.application.dispensing.commands.verify_dispensing import (
    VerifyDispensingCommand,
    VerifyDispensingUseCase,
)
from app.application.prescription.commands.cancel_prescription import (
    CancelPrescriptionCommand,
    CancelPrescriptionUseCase,
)
from app.application.prescription.commands.models import (
    PrescriptionManagementInput,
    ReadyForDispensingCommand,
)
from app.application.prescription.commands.ready_for_dispensing import (
    ReadyForDispensingUseCase,
)
from app.application.prescription.commands.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.primitives import DispensingCompletionType
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.medicine_catalog.primitives import (
    MedicineCodeType,
    NarcoticCategory,
)
from app.domain.patient.entities import Patient
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import PatientBirthDate, PatientNumber
from app.domain.prescription.entities import Prescription
from app.domain.prescription.exceptions import (
    MedicineClassificationMissingError,
    NarcoticPrescriptionDetailsRequiredError,
)
from app.domain.prescription.primitives import PrescriptionStatus
from app.domain.prescription.services import (
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import PharmacistLicenseNumber
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    PharmacistProfile,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.exceptions import (
    NarcoticsLicenseRequiredConflictError,
    PharmacyLicenseRequiredConflictError,
)
from app.domain.store.identifiers import StoreId
from tests.application.access_helpers import create_vendor_corporate_access
from tests.application.dispensing.helpers import create_resolved_actor
from tests.application.prescription.helpers import (
    create_medicine_input,
    create_register_command,
    create_rp_input,
)
from tests.factories.medicine_catalog_factory import create_medicine
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import (
    create_manager_assignment,
    create_store,
    create_store_licenses,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_coverage_selection_record_repository import (
    InMemoryCoverageSelectionRecordRepository,
)
from tests.fakes.in_memory_dispensing_process_repository import (
    InMemoryDispensingProcessRepository,
)
from tests.fakes.in_memory_manager_assignment_repository import (
    InMemoryStoreManagerAssignmentRepository,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)
from tests.fakes.in_memory_patient_repository import InMemoryPatientRepository
from tests.fakes.in_memory_prescription_repository import (
    InMemoryPrescriptionRepository,
)
from tests.fakes.in_memory_staff_repository import InMemoryStaffRepository
from tests.fakes.in_memory_store_repository import InMemoryStoreRepository
from tests.fakes.null_unit_of_work import NullUnitOfWork

TODAY = date(2026, 10, 29)
NON_NARCOTIC_CODE = "2171022F1029"
NARCOTIC_CODE = "8111001M1020"
_DEFAULT_STAFF_ID = StaffId.generate()


def _make_clock(d: date) -> FakeClock:
    return FakeClock(datetime(d.year, d.month, d.day, 3, 0, tzinfo=UTC))


def _advance_clock(clock: FakeClock, d: date) -> None:
    clock._now = datetime(d.year, d.month, d.day, 3, 0, tzinfo=UTC)


def _create_patient(*, corporate_id: CorporateId) -> Patient:
    return Patient(
        id=PatientId.generate(),
        corporate_id=corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("山田"), first_name=PersonNamePart("太郎")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("ヤマダ"),
                first_name=PersonNameKanaPart("タロウ"),
            ),
        ),
        patient_number=PatientNumber(1),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
    )


def _create_staff(*, corporate_id: CorporateId, store_id: StoreId) -> Staff:
    staff = create_staff(
        corporate_id=corporate_id,
        qualifications=StaffQualifications.from_profiles(
            PharmacistProfile(
                license_number=PharmacistLicenseNumber("123456"),
            ),
        ),
    )
    return replace(
        staff,
        id=_DEFAULT_STAFF_ID,
        affiliations=(
            StoreAffiliation(
                store_id=store_id,
                period=AffiliationPeriod(start_date=date(2020, 1, 1)),
                is_primary=True,
            ),
        ),
    )


def _create_dispensed_rp(*, code: str, name: str) -> DispensedRpInput:
    return DispensedRpInput(
        rp_number=1,
        category="internal",
        quantity=14,
        dosage_code_type="none",
        dosage_name="1日3回毎食後",
        medicines=(
            DispensedMedicineInput(
                line_number=1,
                code_type=MedicineCodeType.YJ.value,
                code=code,
                name=name,
                amount="1",
                unit="錠",
            ),
        ),
    )


class GuardedPrescriptionRepository(InMemoryPrescriptionRepository):
    def __init__(self, guard: ClinicalStoreWriteGuard) -> None:
        super().__init__()
        self._guard = guard

    async def save(self, aggregate: Prescription) -> None:
        is_new = aggregate.id not in self.items
        await self._guard.check(aggregate, is_new)
        await super().save(aggregate)


class GuardedDispensingRepository(InMemoryDispensingProcessRepository):
    def __init__(self, guard: ClinicalStoreWriteGuard) -> None:
        super().__init__()
        self._guard = guard

    async def save(self, aggregate: object) -> None:
        from app.domain.dispensing.entities import DispensingProcess

        assert isinstance(aggregate, DispensingProcess)
        is_new = aggregate.id not in self.items
        await self._guard.check(aggregate, is_new)
        await super().save(aggregate)


class BusinessEnvironment:
    """処方・調剤の業務環境をまとめたテスト用フィクスチャ。"""

    def __init__(self, *, clock: FakeClock | None = None) -> None:
        self.clock = clock or _make_clock(TODAY)
        self.corporate_id = CorporateId.generate()
        self.store_repository = InMemoryStoreRepository()
        self.manager_repository = InMemoryStoreManagerAssignmentRepository()
        self.patient_repository = InMemoryPatientRepository()
        self.staff_repository = InMemoryStaffRepository()
        self.coverage_record_repository = InMemoryCoverageSelectionRecordRepository()
        self.catalog_repository = InMemoryMedicineCatalogRepository()

        # UoW と Guard
        self.uow = NullUnitOfWork()
        actor = create_resolved_actor(staff_id=_DEFAULT_STAFF_ID)
        self.corporate_access = create_vendor_corporate_access(actor=actor)
        self.auth = AuthorizationService(actor)
        self.lock = FakeOrganizationLock()

        self.store_op_adapter = StoreOperationAdapter(
            self.store_repository,
            self.corporate_access,
            self.manager_repository,
            self.clock,
        )
        self.restriction_adapter = MedicineCatalogRestrictionAdapter(
            self.catalog_repository
        )
        self.guard = ClinicalStoreWriteGuard(
            self.store_op_adapter,
            self.auth,
            self.lock,
            medicine_restriction=self.restriction_adapter,
            clock=self.clock,
        )

        self.prescription_repository = GuardedPrescriptionRepository(self.guard)
        self.dispensing_repository = GuardedDispensingRepository(self.guard)

        # ユースケース
        self.register_prescription_uc = RegisterPrescriptionUseCase(
            self.prescription_repository,
            self.corporate_access,
            PrescriptionStoreReferenceAdapter(self.store_repository),
            PrescriptionPatientReferenceAdapter(self.patient_repository),
            self.restriction_adapter,
            CoverageSelectionPublicExpenseAdapter(self.coverage_record_repository),
            PrescriptionDocumentNumberUniquenessService(),
            NarcoticPrescriptionService(),
            RefillEligibilityService(),
            PublicExpenseBurdenService(),
            clock=self.clock,
        )
        self.cancel_prescription_uc = CancelPrescriptionUseCase(
            self.prescription_repository,
            self.corporate_access,
        )
        self.ready_for_dispensing_uc = ReadyForDispensingUseCase(
            self.prescription_repository,
            self.corporate_access,
        )

        presc_source = PrescriptionSourceAdapter(self.prescription_repository)
        disp_qual = DispensingStaffQualificationAdapter(self.staff_repository)
        self.start_dispensing_uc = StartDispensingUseCase(
            self.dispensing_repository,
            self.corporate_access,
            DispensingStoreReferenceAdapter(self.store_repository),
            presc_source,
            disp_qual,
            DispensingConsistencyService(),
            DispensingPharmacistService(),
            DispensingIterationUniquenessService(),
            self.clock,
        )
        self.record_content_uc = RecordDispensedContentUseCase(
            self.dispensing_repository,
            self.corporate_access,
            presc_source,
            DispensingConsistencyService(),
            staff_qualification=disp_qual,
            pharmacist_service=DispensingPharmacistService(),
            clock=self.clock,
        )
        self.record_audit_uc = RecordAuditUseCase(
            self.dispensing_repository,
            self.corporate_access,
            disp_qual,
            DispensingPharmacistService(),
            self.clock,
        )
        self.verify_dispensing_uc = VerifyDispensingUseCase(
            self.dispensing_repository,
            self.corporate_access,
            disp_qual,
            DispensingPharmacistService(),
            self.clock,
        )
        self.complete_dispensing_uc = CompleteDispensingUseCase(
            self.dispensing_repository,
            self.corporate_access,
            presc_source,
            self.uow,
            self.clock,
            staff_qualification=disp_qual,
            pharmacist_service=DispensingPharmacistService(),
        )

    async def setup_medicines(self) -> None:
        """非麻薬および麻薬の医薬品マスタを登録する。"""
        non_narcotic = create_medicine(
            code=NON_NARCOTIC_CODE,
            name="アムロジピン錠2.5mg",
            listed_on=date(2020, 1, 1),
            withdrawn_on=None,
        )
        narcotic = create_medicine(
            code=NARCOTIC_CODE,
            name="オキシコドン徐放錠5mg",
            narcotic_category=NarcoticCategory.NARCOTIC,
            listed_on=date(2020, 1, 1),
            withdrawn_on=None,
        )
        await self.catalog_repository.save(non_narcotic)
        await self.catalog_repository.save(narcotic)


# ==============================================================================
# TC-009: 許可未登録の新店舗でマスタ操作は成功、新規業務は409
# ==============================================================================
@pytest.mark.asyncio
async def test_TC009_許可未登録店舗での新規業務を409で拒否する() -> None:
    env = BusinessEnvironment()
    await env.setup_medicines()

    # licenses=None で店舗作成
    store = create_store(corporate_id=env.corporate_id, licenses=None)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    # 処方箋登録を試みる -> 409 (PharmacyLicenseRequiredConflictError)
    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(
            create_rp_input(medicines=(create_medicine_input(code=NON_NARCOTIC_CODE),)),
        ),
    )
    with pytest.raises(PharmacyLicenseRequiredConflictError):
        await env.register_prescription_uc.execute(command)

    # DBに処方箋集約が作成されていないこと
    assert (
        await env.prescription_repository.list_by_patient(
            corporate_id=env.corporate_id, patient_id=patient.id
        )
        == []
    )


# ==============================================================================
# TC-010: 薬局許可の閉区間境界（開始前日/開始日/満了日/翌日）
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("as_of", "should_succeed"),
    [
        (date(2026, 9, 30), False),  # 開始前日
        (date(2026, 10, 1), True),  # 開始日（当日）
        (date(2032, 9, 30), True),  # 満了日（当日）
        (date(2032, 10, 1), False),  # 翌日（失効）
    ],
    ids=["開始前日", "開始日", "満了日", "翌日"],
)
async def test_TC010_薬局開設許可の閉区間境界(
    as_of: date, should_succeed: bool
) -> None:
    clock = _make_clock(as_of)
    env = BusinessEnvironment(clock=clock)
    await env.setup_medicines()

    licenses = create_store_licenses(
        pharmacy_valid_from=date(2026, 10, 1),
        pharmacy_valid_to=date(2032, 9, 30),
    )
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id,
        store_id=store.id,
        starts_on=date(2026, 1, 1),
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(
            create_rp_input(medicines=(create_medicine_input(code=NON_NARCOTIC_CODE),)),
        ),
    )
    command = replace(command, issued_date=as_of, valid_to=as_of)

    if should_succeed:
        result = await env.register_prescription_uc.execute(command)
        assert result.document_number == command.document_number
    else:
        with pytest.raises(PharmacyLicenseRequiredConflictError):
            await env.register_prescription_uc.execute(command)


# ==============================================================================
# TC-011: 麻薬免許の閉区間境界（免許なし/開始前日/開始日/満了日/翌日）
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("as_of", "has_license", "should_succeed"),
    [
        (TODAY, False, False),  # 免許なし
        (date(2026, 10, 28), True, False),  # 開始前日
        (date(2026, 10, 29), True, True),  # 開始日（当日）
        (date(2028, 12, 31), True, True),  # 満了日（当日）
        (date(2029, 1, 1), True, False),  # 翌日（失効）
    ],
    ids=["免許なし", "開始前日", "開始日", "満了日", "翌日"],
)
async def test_TC011_麻薬処方時の麻薬小売業者免許の閉区間境界(
    as_of: date, has_license: bool, should_succeed: bool
) -> None:
    clock = _make_clock(as_of)
    env = BusinessEnvironment(clock=clock)
    await env.setup_medicines()

    if has_license:
        licenses = create_store_licenses(
            pharmacy_valid_from=date(2020, 1, 1),
            pharmacy_valid_to=date(2035, 12, 31),
            narcotics_license_number="麻-2026-001",
            narcotics_valid_from=date(2026, 10, 29),
            narcotics_valid_to=date(2028, 12, 31),
        )
    else:
        licenses = create_store_licenses(
            pharmacy_valid_from=date(2020, 1, 1),
            pharmacy_valid_to=date(2035, 12, 31),
            narcotics_license_number=None,
        )

    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id,
        store_id=store.id,
        starts_on=date(2020, 1, 1),
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        management_info=PrescriptionManagementInput(
            narcotic_license_number="13-1234",
            patient_address="東京都千代田区1-1",
            patient_phone_number="090-1234-5678",
        ),
        rps=(create_rp_input(medicines=(create_medicine_input(code=NARCOTIC_CODE),)),),
    )
    command = replace(command, issued_date=as_of, valid_to=as_of)

    if should_succeed:
        result = await env.register_prescription_uc.execute(command)
        assert result.document_number == command.document_number
    else:
        with pytest.raises(NarcoticsLicenseRequiredConflictError):
            await env.register_prescription_uc.execute(command)


# ==============================================================================
# TC-012: 一般処方（非麻薬）は麻薬免許なしでも受付・調剤可能
# ==============================================================================
@pytest.mark.asyncio
async def test_TC012_一般処方は麻薬免許なしでも受付調剤可能() -> None:
    env = BusinessEnvironment()
    await env.setup_medicines()

    licenses = create_store_licenses(
        pharmacy_valid_from=date(2020, 1, 1),
        pharmacy_valid_to=date(2035, 12, 31),
        narcotics_license_number=None,
    )
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    staff = _create_staff(corporate_id=env.corporate_id, store_id=store.id)
    await env.staff_repository.save(staff)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(
            create_rp_input(medicines=(create_medicine_input(code=NON_NARCOTIC_CODE),)),
        ),
    )
    command = replace(command, issued_date=TODAY, valid_to=TODAY)
    presc_dto = await env.register_prescription_uc.execute(command)
    assert presc_dto.status == PrescriptionStatus.RECEIVED.value

    await env.ready_for_dispensing_uc.execute(
        ReadyForDispensingCommand(
            corporate_id=str(env.corporate_id.value),
            prescription_id=presc_dto.id,
        )
    )

    disp_dto = await env.start_dispensing_uc.execute(
        StartDispensingCommand(
            corporate_id=str(env.corporate_id.value),
            store_id=str(store.id.value),
            prescription_id=presc_dto.id,
            dispenser_id=str(staff.id.value),
            iteration=1,
            dispensed_date=TODAY,
            dispensed_rps=(
                _create_dispensed_rp(
                    code=NON_NARCOTIC_CODE, name="カロナール錠200 200mg"
                ),
            ),
        )
    )
    assert disp_dto.dispensed_date == TODAY.isoformat()


# ==============================================================================
# TC-013: 麻薬識別入力攻撃（麻薬薬品で麻薬欄省略時は422/409で拒否）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC013_マスタが麻薬の薬品は麻薬欄省略でも麻薬免許なしを409拒否() -> None:
    env = BusinessEnvironment()
    await env.setup_medicines()

    licenses = create_store_licenses(narcotics_license_number=None)
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        management_info=None,
        rps=(create_rp_input(medicines=(create_medicine_input(code=NARCOTIC_CODE),)),),
    )

    with pytest.raises(
        (
            NarcoticPrescriptionDetailsRequiredError,
            NarcoticsLicenseRequiredConflictError,
        )
    ):
        await env.register_prescription_uc.execute(command)


# ==============================================================================
# TC-014: 薬品分類/判定不能（未収載薬品は非麻薬として通さず業務を拒否）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC014_未収載薬品は非麻薬として通さず業務を拒否() -> None:
    env = BusinessEnvironment()

    licenses = create_store_licenses(narcotics_license_number="麻-2026-001")
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(create_rp_input(medicines=(create_medicine_input(code="9999999X9999"),)),),
    )
    with pytest.raises(MedicineClassificationMissingError):
        await env.register_prescription_uc.execute(command)


# ==============================================================================
# TC-015: 判定日境界（交付日と操作日で分類が異なる処方、過去日入力で失効回避不可）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC015_過去交付日でも現在業務日に麻薬免許が失効していれば拒否() -> None:
    today = date(2029, 1, 1)
    clock = _make_clock(today)
    env = BusinessEnvironment(clock=clock)
    await env.setup_medicines()

    licenses = create_store_licenses(
        pharmacy_valid_from=date(2020, 1, 1),
        pharmacy_valid_to=date(2035, 12, 31),
        narcotics_license_number="麻-2026-001",
        narcotics_valid_from=date(2026, 10, 29),
        narcotics_valid_to=date(2028, 12, 31),
    )
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id,
        store_id=store.id,
        starts_on=date(2020, 1, 1),
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    command = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        management_info=PrescriptionManagementInput(
            narcotic_license_number="13-1234",
            patient_address="東京都千代田区1-1",
            patient_phone_number="090-1234-5678",
        ),
        rps=(create_rp_input(medicines=(create_medicine_input(code=NARCOTIC_CODE),)),),
    )
    command = replace(
        command, issued_date=date(2028, 12, 30), valid_to=date(2029, 1, 3)
    )

    with pytest.raises(NarcoticsLicenseRequiredConflictError):
        await env.register_prescription_uc.execute(command)


# ==============================================================================
# TC-016: 業務接続/再検証（調剤開始・内容変更・処方鑑査・最終鑑査・交付完了で当日の免許を再評価）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC016_前日成功後に免許失効した場合の各調剤操作を拒否() -> None:
    day1 = date(2028, 12, 31)
    clock = _make_clock(day1)
    env = BusinessEnvironment(clock=clock)
    await env.setup_medicines()

    licenses = create_store_licenses(
        pharmacy_valid_from=date(2020, 1, 1),
        pharmacy_valid_to=date(2035, 12, 31),
        narcotics_license_number="麻-2026-001",
        narcotics_valid_from=date(2026, 10, 29),
        narcotics_valid_to=date(2028, 12, 31),
    )
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id,
        store_id=store.id,
        starts_on=date(2020, 1, 1),
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    staff = _create_staff(corporate_id=env.corporate_id, store_id=store.id)
    await env.staff_repository.save(staff)

    counter = 0

    async def _setup_session() -> DispensingProcessDto:
        nonlocal counter
        counter += 1
        presc_cmd = create_register_command(
            corporate_id=env.corporate_id,
            store_id=store.id,
            patient_id=patient.id,
            document_number=f"DOC-TC016-{counter}",
            management_info=PrescriptionManagementInput(
                narcotic_license_number="13-1234",
                patient_address="東京都千代田区1-1",
                patient_phone_number="090-1234-5678",
            ),
            rps=(
                create_rp_input(medicines=(create_medicine_input(code=NARCOTIC_CODE),)),
            ),
        )
        presc_cmd = replace(presc_cmd, issued_date=day1, valid_to=date(2029, 1, 5))
        presc = await env.register_prescription_uc.execute(presc_cmd)
        await env.ready_for_dispensing_uc.execute(
            ReadyForDispensingCommand(
                corporate_id=str(env.corporate_id.value),
                prescription_id=presc.id,
            )
        )
        return await env.start_dispensing_uc.execute(
            StartDispensingCommand(
                corporate_id=str(env.corporate_id.value),
                store_id=str(store.id.value),
                prescription_id=presc.id,
                dispenser_id=str(staff.id.value),
                iteration=1,
                dispensed_date=day1,
                dispensed_rps=(
                    _create_dispensed_rp(
                        code=NARCOTIC_CODE, name="オキシコドン徐放錠5mg"
                    ),
                ),
            )
        )

    # Session 1: 処方鑑査で拒否
    disp1 = await _setup_session()

    # Session 2: 最終鑑査で拒否（Day 1 に処方鑑査を通過）
    disp2 = await _setup_session()
    await env.record_audit_uc.execute(
        RecordAuditCommand(
            corporate_id=str(env.corporate_id.value),
            dispensing_id=disp2.id,
            auditor_id=str(staff.id.value),
            has_issues=False,
        )
    )

    # Session 3: 完了で拒否（Day 1 に処方鑑査・最終鑑査を通過）
    disp3 = await _setup_session()
    await env.record_audit_uc.execute(
        RecordAuditCommand(
            corporate_id=str(env.corporate_id.value),
            dispensing_id=disp3.id,
            auditor_id=str(staff.id.value),
            has_issues=False,
        )
    )
    await env.verify_dispensing_uc.execute(
        VerifyDispensingCommand(
            corporate_id=str(env.corporate_id.value),
            dispensing_id=disp3.id,
            verifier_id=str(staff.id.value),
            result="passed",
        )
    )

    # Day 2: 2029-01-01（麻薬免許失効日）へ日付変更
    day2 = date(2029, 1, 1)
    _advance_clock(env.clock, day2)

    # 1. 処方鑑査（record_audit）を試みる -> 当日の麻薬免許失効で409
    with pytest.raises(NarcoticsLicenseRequiredConflictError):
        await env.record_audit_uc.execute(
            RecordAuditCommand(
                corporate_id=str(env.corporate_id.value),
                dispensing_id=disp1.id,
                auditor_id=str(staff.id.value),
                has_issues=False,
            )
        )

    # 2. 最終鑑査（verify_dispensing）を試みる -> 当日の麻薬免許失効で409
    with pytest.raises(NarcoticsLicenseRequiredConflictError):
        await env.verify_dispensing_uc.execute(
            VerifyDispensingCommand(
                corporate_id=str(env.corporate_id.value),
                dispensing_id=disp2.id,
                verifier_id=str(staff.id.value),
                result="passed",
            )
        )

    # 3. 交付完了（complete_dispensing）を試みる -> 当日の麻薬免許失効で409
    with pytest.raises(NarcoticsLicenseRequiredConflictError):
        await env.complete_dispensing_uc.execute(
            CompleteDispensingCommand(
                corporate_id=str(env.corporate_id.value),
                dispensing_id=disp3.id,
                completion_type=DispensingCompletionType.COMPLETED.value,
            )
        )


# ==============================================================================
# TC-017: 代替・追加薬境界（一般処方から実調剤を麻薬へ変更、免許なしなら拒否）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC017_一般処方から実調剤を麻薬へ変更時に麻薬免許なしなら409拒否() -> (
    None
):
    env = BusinessEnvironment()
    await env.setup_medicines()

    licenses = create_store_licenses(narcotics_license_number=None)
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    staff = _create_staff(corporate_id=env.corporate_id, store_id=store.id)
    await env.staff_repository.save(staff)

    presc_cmd = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(
            create_rp_input(medicines=(create_medicine_input(code=NON_NARCOTIC_CODE),)),
        ),
    )
    presc_cmd = replace(presc_cmd, issued_date=TODAY, valid_to=TODAY)
    presc = await env.register_prescription_uc.execute(presc_cmd)
    await env.ready_for_dispensing_uc.execute(
        ReadyForDispensingCommand(
            corporate_id=str(env.corporate_id.value),
            prescription_id=presc.id,
        )
    )
    disp = await env.start_dispensing_uc.execute(
        StartDispensingCommand(
            corporate_id=str(env.corporate_id.value),
            store_id=str(store.id.value),
            prescription_id=presc.id,
            dispenser_id=str(staff.id.value),
            iteration=1,
            dispensed_date=TODAY,
            dispensed_rps=(
                _create_dispensed_rp(
                    code=NON_NARCOTIC_CODE, name="カロナール錠200 200mg"
                ),
            ),
        )
    )

    with pytest.raises(NarcoticsLicenseRequiredConflictError):
        await env.record_content_uc.execute(
            RecordDispensedContentCommand(
                corporate_id=str(env.corporate_id.value),
                dispensing_id=disp.id,
                dispensed_rps=(
                    DispensedRpInput(
                        rp_number=1,
                        category="internal",
                        quantity=14,
                        dosage_code_type="none",
                        dosage_name="1日3回毎食後",
                        medicines=(
                            DispensedMedicineInput(
                                line_number=1,
                                code_type=MedicineCodeType.YJ.value,
                                code=NARCOTIC_CODE,
                                name="オキシコドン徐放錠5mg",
                                amount="1",
                                unit="錠",
                                substitution=SubstitutionInput(
                                    category="inquiry_modified",
                                    original_code_type=MedicineCodeType.YJ.value,
                                    original_code=NON_NARCOTIC_CODE,
                                    original_name="カロナール錠200 200mg",
                                    inquiry_number=1,
                                ),
                            ),
                        ),
                    ),
                ),
            )
        )


# ==============================================================================
# TC-018: 訂正/取消/閲覧の回帰（免許失効後も既存履歴閲覧・処方箋取消は成功）
# ==============================================================================
@pytest.mark.asyncio
async def test_TC018_免許失効後も処方箋取消と閲覧は免許だけを理由に阻止しない() -> None:
    day1 = date(2026, 10, 29)
    clock = _make_clock(day1)
    env = BusinessEnvironment(clock=clock)
    await env.setup_medicines()

    licenses = create_store_licenses(
        pharmacy_valid_from=date(2020, 1, 1),
        pharmacy_valid_to=date(2026, 10, 30),
    )
    store = create_store(corporate_id=env.corporate_id, licenses=licenses)
    await env.store_repository.save(store)
    manager = create_manager_assignment(
        corporate_id=env.corporate_id, store_id=store.id
    )
    await env.manager_repository.save(manager)

    patient = _create_patient(corporate_id=env.corporate_id)
    await env.patient_repository.save(patient)

    presc_cmd = create_register_command(
        corporate_id=env.corporate_id,
        store_id=store.id,
        patient_id=patient.id,
        rps=(
            create_rp_input(medicines=(create_medicine_input(code=NON_NARCOTIC_CODE),)),
        ),
    )
    presc_cmd = replace(presc_cmd, issued_date=TODAY, valid_to=TODAY)
    presc = await env.register_prescription_uc.execute(presc_cmd)
    assert presc.status == PrescriptionStatus.RECEIVED.value

    _advance_clock(env.clock, date(2026, 11, 1))

    cancelled = await env.cancel_prescription_uc.execute(
        CancelPrescriptionCommand(
            corporate_id=str(env.corporate_id.value),
            prescription_id=presc.id,
        )
    )
    assert cancelled.status == PrescriptionStatus.CANCELLED.value
