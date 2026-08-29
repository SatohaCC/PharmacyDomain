"""調剤ユースケーステストで共有する組み立てヘルパー。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import ActorContext, AuthorizationService
from app.application.corporate import CorporateAccessService
from app.application.dispensing import (
    CompleteDispensingUseCase,
    DispensedMedicineInput,
    DispensedRpInput,
    GetDispensingUseCase,
    ListDispensingsByPrescriptionUseCase,
    RecordAuditUseCase,
    RecordDispensedContentUseCase,
    StartDispensingCommand,
    StartDispensingUseCase,
    SubstitutionInput,
    VerifyDispensingUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.prescription import Prescription
from app.domain.shared.medicine import MedicineCodeType
from app.domain.staff.primitives import (
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffId,
    StaffQualifications,
)
from app.domain.store.primitives import StoreId
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.factories.dispensing_factory import (
    DISPENSED_ON,
    GENERIC_CODE,
    GENERIC_NAME,
    MEDICINE_CODE,
    MEDICINE_NAME,
)
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_rp,
)
from tests.fakes.dispensing_reference_boundaries import (
    FakeDispensingStaffQualificationSource,
    FakeDispensingStoreReference,
    FakePrescriptionSource,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.in_memory_dispensing_process_repository import (
    InMemoryDispensingProcessRepository,
)


def create_pharmacist_qualifications() -> StaffQualifications:
    """薬剤師資格を1つ持つ保有資格を組み立てる。"""
    return StaffQualifications.from_profiles(
        PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
    )


def create_medicine_input(
    *,
    line_number: int = 1,
    code: str | None = MEDICINE_CODE,
    name: str = MEDICINE_NAME,
    amount: str = "3",
    unit: str = "錠",
    substitution: SubstitutionInput | None = None,
    preparations: tuple[str, ...] = (),
) -> DispensedMedicineInput:
    """調剤した薬品1明細の入力を組み立てる。"""
    return DispensedMedicineInput(
        line_number=line_number,
        code_type=MedicineCodeType.YJ.value,
        code=code,
        name=name,
        amount=amount,
        unit=unit,
        substitution=substitution,
        preparations=preparations,
    )


def create_generic_substitution() -> SubstitutionInput:
    """後発医薬品への変更調剤の入力を組み立てる。"""
    return SubstitutionInput(
        category="generic_substitution",
        original_code_type=MedicineCodeType.YJ.value,
        original_code=MEDICINE_CODE,
        original_name=MEDICINE_NAME,
    )


def create_substituted_medicine_input() -> DispensedMedicineInput:
    """後発品へ変更した薬品明細の入力を組み立てる。"""
    return create_medicine_input(
        code=GENERIC_CODE,
        name=GENERIC_NAME,
        substitution=create_generic_substitution(),
    )


def create_rp_input(
    *,
    rp_number: int = 1,
    quantity: int = 14,
    medicines: tuple[DispensedMedicineInput, ...] | None = None,
) -> DispensedRpInput:
    """調剤した剤（Rp）の入力を組み立てる。"""
    return DispensedRpInput(
        rp_number=rp_number,
        category="internal",
        quantity=quantity,
        dosage_code_type="none",
        dosage_name="1日3回毎食後",
        medicines=medicines if medicines is not None else (create_medicine_input(),),
    )


@dataclass(frozen=True, kw_only=True)
class DispensingFixture:
    """ユースケース一式と、その依存へ手を入れるための参照。"""

    start: StartDispensingUseCase
    record_content: RecordDispensedContentUseCase
    record_audit: RecordAuditUseCase
    verify: VerifyDispensingUseCase
    complete: CompleteDispensingUseCase
    get: GetDispensingUseCase
    list_by_prescription: ListDispensingsByPrescriptionUseCase
    repository: InMemoryDispensingProcessRepository
    corporate_repository: AutoProvisioningCorporateRepository
    store_reference: FakeDispensingStoreReference
    prescription_source: FakePrescriptionSource
    staff_qualification: FakeDispensingStaffQualificationSource
    clock: FakeClock
    corporate_id: CorporateId
    store_id: StoreId
    prescription: Prescription
    dispenser_id: StaffId
    verifier_id: StaffId


def create_fixture(*, prescription: Prescription | None = None) -> DispensingFixture:
    """既定の依存を配線した Fixture を生成する。

    処方箋は既定で「調剤可能」状態にする。受付済のままでは調剤を開始できない
    （``PrescriptionNotReadyForDispensingError``）。
    """
    dispenser_id = StaffId.generate()
    verifier_id = StaffId.generate()

    if prescription is None:
        prescription = create_prescription(
            rps=(create_rp(medicines=(create_medicine(),)),)
        )
    # 法人・店舗は処方箋から取る。別々に採番すると、渡された処方箋が
    # Fixture の法人に属さず、境界の参照が理由なく404になる。
    corporate_id = prescription.corporate_id
    store_id = prescription.store_id
    prescription = prescription.ready_for_dispensing()

    repository = InMemoryDispensingProcessRepository()
    store_reference = FakeDispensingStoreReference()
    store_reference.register(corporate_id=corporate_id, store_id=store_id)
    prescription_source = FakePrescriptionSource()
    prescription_source.register(prescription)
    staff_qualification = FakeDispensingStaffQualificationSource()
    for staff_id in (dispenser_id, verifier_id):
        staff_qualification.register(
            corporate_id=corporate_id,
            staff_id=staff_id,
            qualifications=create_pharmacist_qualifications(),
        )
    clock = FakeClock()
    corporate_repository = AutoProvisioningCorporateRepository()
    corporate_access = create_vendor_corporate_access_for(corporate_repository)

    return DispensingFixture(
        start=StartDispensingUseCase(
            repository,
            corporate_access,
            store_reference,
            prescription_source,
            staff_qualification,
            DispensingConsistencyService(),
            DispensingPharmacistService(),
            DispensingIterationUniquenessService(),
            clock,
        ),
        record_content=RecordDispensedContentUseCase(
            repository,
            corporate_access,
            prescription_source,
            DispensingConsistencyService(),
        ),
        record_audit=RecordAuditUseCase(
            repository,
            corporate_access,
            staff_qualification,
            DispensingPharmacistService(),
            clock,
        ),
        verify=VerifyDispensingUseCase(
            repository,
            corporate_access,
            staff_qualification,
            DispensingPharmacistService(),
            clock,
        ),
        complete=CompleteDispensingUseCase(
            repository, corporate_access, prescription_source
        ),
        get=GetDispensingUseCase(repository, corporate_access),
        list_by_prescription=ListDispensingsByPrescriptionUseCase(
            repository, corporate_access
        ),
        repository=repository,
        corporate_repository=corporate_repository,
        store_reference=store_reference,
        prescription_source=prescription_source,
        staff_qualification=staff_qualification,
        clock=clock,
        corporate_id=corporate_id,
        store_id=store_id,
        prescription=prescription,
        dispenser_id=dispenser_id,
        verifier_id=verifier_id,
    )


def create_start_command(
    fixture: DispensingFixture,
    *,
    iteration: int = 1,
    dispensed_on: date = DISPENSED_ON,
    dispensed_rps: tuple[DispensedRpInput, ...] | None = None,
    split_reason: str | None = None,
    dispenser_id: StaffId | None = None,
) -> StartDispensingCommand:
    """調剤開始コマンドを組み立てる。"""
    return StartDispensingCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        prescription_id=str(fixture.prescription.id.value),
        dispenser_id=str(
            (dispenser_id if dispenser_id is not None else fixture.dispenser_id).value
        ),
        iteration=iteration,
        dispensed_date=dispensed_on,
        dispensed_rps=(
            dispensed_rps if dispensed_rps is not None else (create_rp_input(),)
        ),
        split_reason=split_reason,
    )


def create_actor_access(
    corporate_repository: AutoProvisioningCorporateRepository,
    corporate_id: CorporateId,
) -> CorporateAccessService:
    """自法人だけを操作できる法人管理者のアクセス境界を組み立てる。"""
    return CorporateAccessService(
        corporate_repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="test-corporate-admin",
                corporate_id=corporate_id,
            )
        ),
    )
