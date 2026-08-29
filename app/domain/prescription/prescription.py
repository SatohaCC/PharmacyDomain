"""処方箋集約。

医師・歯科医師が交付した処方箋原本の完全性と、薬剤師法第24条に基づく
疑義照会を管理する整合性境界のルート。

**集約が単独で検証できることだけを ``validate()`` に置く。** 麻薬かどうか、
リフィル適用除外に当たるかは医薬品マスタ側の属性であり、薬剤師資格は Staff
集約が持つ。これらは Domain Service が Boundary 経由で判定する。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Self

from app.base.domain.dosage import DosageInstruction
from app.base.domain.entity import AggregateRoot, Entity
from app.base.domain.medicine import (
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PublicExpenseBurden,
    RpNumber,
    SingleDoseAmount,
)
from app.base.domain.value_object import ValueObject
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.exceptions import (
    DuplicatedDosageSupplementError,
    DuplicatedMedicineSupplementError,
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    InquiryNumberSequenceError,
    MedicineCodeTypeNotAllowedError,
    MedicineLineNumberSequenceError,
    OpenInquiryExistsError,
    PrescriptionMedicineRequiredError,
    PrescriptionRpRequiredError,
    PrescriptionStatusTransitionError,
    RpNumberSequenceError,
    UnequalDosageTotalMismatchError,
)
from app.domain.prescription.primitives import (
    DosageFormName,
    InquiryCategory,
    InquiryContent,
    InquiryNumber,
    InquiryTimestamp,
    PrescriptionDocumentNumber,
    PrescriptionId,
    PrescriptionSourceType,
    PrescriptionStatus,
)
from app.domain.prescription.value_objects import (
    DepartmentInfo,
    DosageSupplement,
    GenericSubstitutionRestriction,
    MedicalInstitutionInfo,
    MedicineSupplement,
    PrescriberInfo,
    PrescriberResponse,
    PrescriptionManagementInfo,
    PrescriptionPeriod,
    UnequalDosageInstruction,
    UnitConversion,
)
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId

#: ``status`` から遷移できる先。ここに無い組み合わせは拒否する。
_ALLOWED_TRANSITIONS: dict[PrescriptionStatus, frozenset[PrescriptionStatus]] = {
    PrescriptionStatus.RECEIVED: frozenset(
        {PrescriptionStatus.READY_FOR_DISPENSING, PrescriptionStatus.CANCELLED}
    ),
    PrescriptionStatus.READY_FOR_DISPENSING: frozenset(
        {
            PrescriptionStatus.RECEIVED,
            PrescriptionStatus.DISPENSED,
            PrescriptionStatus.CANCELLED,
        }
    ),
    PrescriptionStatus.DISPENSED: frozenset(),
    PrescriptionStatus.CANCELLED: frozenset(),
}

if set(_ALLOWED_TRANSITIONS) != set(PrescriptionStatus):
    raise RuntimeError("PrescriptionStatus の遷移表に定義漏れがあります。")


def _ensure_consecutive_from_one(numbers: tuple[int, ...]) -> bool:
    """1から連続した昇順に並んでいるかを返す。"""
    return list(numbers) == list(range(1, len(numbers) + 1))


@dataclass(frozen=True, kw_only=True)
class PrescriptionMedicine(ValueObject):
    """剤（Rp）に含まれる処方薬品の1明細。

    出典: JAHIS レコードNo.201（薬品レコード）と、これに紐づく
    No.211（単位変換）/ No.221（不均等）/ No.231（負担区分）/
    No.241（1回服用量）/ No.281（薬品補足）。
    """

    line_number: MedicineLineNumber
    identifier: MedicineIdentifier
    name: MedicineName
    amount: DosageAmount
    unit: MedicineUnit
    unit_conversion: UnitConversion | None = None
    unequal_dosage: UnequalDosageInstruction | None = None
    single_dose: SingleDoseAmount | None = None
    substitution_restriction: GenericSubstitutionRestriction | None = None
    public_expense_burden: PublicExpenseBurden | None = None
    supplements: tuple[MedicineSupplement, ...] = ()

    def validate(self) -> None:
        """薬品明細のうち、この明細だけで判定できる不変条件を検証する。"""
        self._ensure_unequal_dosage_matches_amount()
        self._ensure_supplements_are_unique()

    def _ensure_unequal_dosage_matches_amount(self) -> None:
        """不均等服用の各回合計が1日量と一致することを検証する。

        用量は ``Decimal`` なので、実在する用量刻み（0.05刻み等）でも
        合計が誤差なく一致する。``float`` だとここが正当な処方を弾く。
        """
        if self.unequal_dosage is None:
            return
        if not self.unequal_dosage.matches_daily_amount(self.amount):
            raise UnequalDosageTotalMismatchError(
                total=self.unequal_dosage.total.value,
                daily_amount=self.amount.value,
            )

    def _ensure_supplements_are_unique(self) -> None:
        """同じ薬品補足区分が重複していないことを検証する。"""
        types = [supplement.supplement_type for supplement in self.supplements]
        if len(types) != len(set(types)):
            raise DuplicatedMedicineSupplementError()


@dataclass(frozen=True, kw_only=True)
class PrescriptionRp(ValueObject):
    """剤（Rp）。用法・調剤数量と、それを共有する薬品明細の束。

    出典: JAHIS レコードNo.101（剤形レコード）/ No.111（用法レコード）/
    No.181（用法補足レコード）。
    """

    rp_number: RpNumber
    category: DosageFormCategory
    quantity: DispensingQuantity
    dosage_instruction: DosageInstruction
    medicines: tuple[PrescriptionMedicine, ...]
    custom_category_name: DosageFormName | None = None
    dosage_supplements: tuple[DosageSupplement, ...] = ()

    def validate(self) -> None:
        """剤の構造的な不変条件を検証する。"""
        self._ensure_has_medicine()
        self._ensure_line_numbers_are_consecutive()
        self._ensure_dosage_supplements_are_unique()

    def _ensure_has_medicine(self) -> None:
        """薬品明細が1件以上あることを検証する。"""
        if not self.medicines:
            raise PrescriptionMedicineRequiredError()

    def _ensure_line_numbers_are_consecutive(self) -> None:
        """RP内連番が1から連続した昇順であることを検証する。"""
        numbers = tuple(medicine.line_number.value for medicine in self.medicines)
        if not _ensure_consecutive_from_one(numbers):
            raise MedicineLineNumberSequenceError(
                rp_number=self.rp_number.value, actual=numbers
            )

    def _ensure_dosage_supplements_are_unique(self) -> None:
        """同じ用法補足区分が重複していないことを検証する。"""
        types = [supplement.supplement_type for supplement in self.dosage_supplements]
        if len(types) != len(set(types)):
            raise DuplicatedDosageSupplementError()

    @property
    def medicine_identifiers(self) -> tuple[MedicineIdentifier, ...]:
        """この剤に含まれる薬品の識別子。"""
        return tuple(medicine.identifier for medicine in self.medicines)


@dataclass(frozen=True, eq=False, kw_only=True)
class PrescriptionInquiry(Entity[InquiryNumber]):
    """疑義照会の1件。

    規格上は調剤編の ``疑義照会結果レコード(511)`` として調剤結果に記録されるが、
    疑義は処方内容に対して発生しその解決が処方内容を確定させるため、
    本モデルでは処方箋集約が保持する。送信時に511へ写像する。

    連番で同一性を持つので :class:`Entity` を継承する。
    """

    id: InquiryNumber
    pharmacist_id: StaffId
    inquired_at: InquiryTimestamp
    category: InquiryCategory
    content: InquiryContent
    response: PrescriberResponse | None = None

    @property
    def inquiry_number(self) -> InquiryNumber:
        """照会連番（``id`` の別名。呼び出し側の意図を読みやすくする）。"""
        return self.id

    @property
    def is_open(self) -> bool:
        """未回答か。"""
        return self.response is None

    @property
    def blocks_dispensing(self) -> bool:
        """この照会の結果、当該処方の調剤ができなくなるか。"""
        return self.response is not None and self.response.blocks_dispensing

    def resolve(self, response: PrescriberResponse) -> Self:
        """回答を記録する。回答済みの照会には再度回答できない。"""
        if self.response is not None:
            raise InquiryAlreadyResolvedError()
        return replace(self, response=response)


@dataclass(frozen=True, eq=False, kw_only=True)
class Prescription(AggregateRoot[PrescriptionId]):
    """処方箋原本の完全性と疑義照会を管理する集約ルート。"""

    id: PrescriptionId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    source_type: PrescriptionSourceType
    document_number: PrescriptionDocumentNumber
    medical_institution: MedicalInstitutionInfo
    department: DepartmentInfo
    prescriber: PrescriberInfo
    period: PrescriptionPeriod
    rps: tuple[PrescriptionRp, ...]
    status: PrescriptionStatus = PrescriptionStatus.RECEIVED
    # 別モジュールの frozen dataclass なので ruff が不変性を追えない。
    # default_factory で意図を明示する（RUF009）。
    management_info: PrescriptionManagementInfo = field(
        default_factory=PrescriptionManagementInfo
    )
    inquiries: tuple[PrescriptionInquiry, ...] = ()
    coverage_selection_record_id: CoverageSelectionRecordId | None = None

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """処方箋集約が単独で判定できる不変条件を検証する。"""
        self._ensure_has_rp()
        self._ensure_rp_numbers_are_consecutive()
        self._ensure_inquiry_numbers_are_consecutive()
        self._ensure_medicine_code_types_match_source()

    def _ensure_has_rp(self) -> None:
        """剤（Rp）が1件以上あることを検証する。"""
        if not self.rps:
            raise PrescriptionRpRequiredError()

    def _ensure_rp_numbers_are_consecutive(self) -> None:
        """RP番号が1から連続した昇順であることを検証する。"""
        numbers = tuple(rp.rp_number.value for rp in self.rps)
        if not _ensure_consecutive_from_one(numbers):
            raise RpNumberSequenceError(actual=numbers)

    def _ensure_inquiry_numbers_are_consecutive(self) -> None:
        """疑義照会の連番が1から連続した昇順であることを検証する。"""
        numbers = tuple(inquiry.id.value for inquiry in self.inquiries)
        if not _ensure_consecutive_from_one(numbers):
            raise InquiryNumberSequenceError()

    def _ensure_medicine_code_types_match_source(self) -> None:
        """電子処方箋で使用できない薬品コード種別が無いことを検証する。

        処方編 別表15 は ``1:コードなし`` を「未使用」、``3:厚生省コード`` と
        ``6:HOTコード`` を「使用しない」と定めている。紙処方箋（JAHIS）では
        いずれも使えるため、受領元形式と組み合わせて初めて判定できる。
        ここで弾かないと、送信不能なコードのまま処方箋が確定してしまう。
        """
        if self.source_type is not PrescriptionSourceType.ELECTRONIC:
            return
        for rp in self.rps:
            for medicine in rp.medicines:
                code_type = medicine.identifier.code_type
                if not code_type.allowed_in_electronic_prescription:
                    raise MedicineCodeTypeNotAllowedError(
                        code_type_label=code_type.label
                    )

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def has_open_inquiry(self) -> bool:
        """未回答の疑義照会があるか。

        「疑義照会中」を状態として持たず、ここから導出する。状態にすると
        照会解決後の戻り先が ``status`` だけでは決まらず、かつ
        「照会中なのに未回答が0件」という矛盾が構築可能になる。
        """
        return any(inquiry.is_open for inquiry in self.inquiries)

    @property
    def has_blocking_inquiry(self) -> bool:
        """処方削除の回答を受けた照会があるか。"""
        return any(inquiry.blocks_dispensing for inquiry in self.inquiries)

    @property
    def medicine_identifiers(self) -> tuple[MedicineIdentifier, ...]:
        """処方箋に含まれるすべての薬品識別子（Domain Service の入力に使う）。"""
        return tuple(
            medicine.identifier for rp in self.rps for medicine in rp.medicines
        )

    @property
    def next_inquiry_number(self) -> InquiryNumber:
        """次に採番する疑義照会の連番。"""
        return InquiryNumber(len(self.inquiries) + 1)

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        source_type: PrescriptionSourceType,
        document_number: PrescriptionDocumentNumber,
        medical_institution: MedicalInstitutionInfo,
        department: DepartmentInfo,
        prescriber: PrescriberInfo,
        period: PrescriptionPeriod,
        rps: tuple[PrescriptionRp, ...],
        management_info: PrescriptionManagementInfo | None = None,
        coverage_selection_record_id: CoverageSelectionRecordId | None = None,
    ) -> Self:
        """受け付けた処方箋を新規に登録する。"""
        return cls(
            id=PrescriptionId.generate(),
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            source_type=source_type,
            document_number=document_number,
            medical_institution=medical_institution,
            department=department,
            prescriber=prescriber,
            period=period,
            rps=rps,
            status=PrescriptionStatus.RECEIVED,
            management_info=(
                management_info
                if management_info is not None
                else PrescriptionManagementInfo()
            ),
            coverage_selection_record_id=coverage_selection_record_id,
        )

    # ------------------------------------------------------------------
    # 疑義照会
    # ------------------------------------------------------------------

    def start_inquiry(
        self,
        *,
        pharmacist_id: StaffId,
        category: InquiryCategory,
        content: InquiryContent,
        inquired_at: InquiryTimestamp,
    ) -> Self:
        """疑義照会を開始する。

        照会薬剤師が薬剤師資格を持つかは Staff 集約を見ないと判定できないため、
        ここでは検証しない（``InquiryPharmacistService`` が担う）。
        """
        self._ensure_not_terminal(PrescriptionStatus.RECEIVED)
        inquiry = PrescriptionInquiry(
            id=self.next_inquiry_number,
            pharmacist_id=pharmacist_id,
            inquired_at=inquired_at,
            category=category,
            content=content,
        )
        return replace(self, inquiries=(*self.inquiries, inquiry))

    def resolve_inquiry(
        self, *, inquiry_number: InquiryNumber, response: PrescriberResponse
    ) -> Self:
        """疑義照会に回答を記録する。"""
        resolved: list[PrescriptionInquiry] = []
        found = False
        for inquiry in self.inquiries:
            if inquiry.id == inquiry_number:
                resolved.append(inquiry.resolve(response))
                found = True
            else:
                resolved.append(inquiry)
        if not found:
            raise InquiryNotFoundError(inquiry_number=inquiry_number.value)
        return replace(self, inquiries=tuple(resolved))

    # ------------------------------------------------------------------
    # 状態遷移
    # ------------------------------------------------------------------

    def ready_for_dispensing(self) -> Self:
        """処方を確定し、調剤セッションを開始可能な状態にする。

        未回答の疑義照会があるうちは進めない。処方の内容がまだ確定していない
        ためであり、これは集約が単独で判定できる。
        """
        if self.has_open_inquiry:
            raise OpenInquiryExistsError()
        return self._transition_to(PrescriptionStatus.READY_FOR_DISPENSING)

    def return_for_inquiry(self) -> Self:
        """疑義が生じたため受付済へ差し戻す。"""
        return self._transition_to(PrescriptionStatus.RECEIVED)

    def complete_dispensing(self) -> Self:
        """全ての調剤が完了したことを記録する（調剤済）。

        遷移の契機は調剤編 ``リフィル処方箋情報レコード(521)`` の調剤終了区分で
        あり、「総使用回数に達したこと」ではない。規格は「達していないが次回
        以降の調剤が不要となった場合」も終了として扱うため、判断は
        Dispensing 側から渡される。
        """
        return self._transition_to(PrescriptionStatus.DISPENSED)

    def cancel(self) -> Self:
        """処方箋を取消・無効にする。"""
        return self._transition_to(PrescriptionStatus.CANCELLED)

    def _transition_to(self, target: PrescriptionStatus) -> Self:
        """遷移表に従って状態を変更する。"""
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise PrescriptionStatusTransitionError(
                current=self.status.label, target=target.label
            )
        return replace(self, status=target)

    def _ensure_not_terminal(self, _target: PrescriptionStatus) -> None:
        """終端状態では内容を変更できないことを保証する。"""
        if self.status.is_terminal:
            raise PrescriptionStatusTransitionError(
                current=self.status.label, target="疑義照会の追加"
            )
