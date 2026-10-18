"""prescriptionのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.identifiers import CoverageSelectionRecordId
from app.domain.foundation.entity import AggregateRoot, Entity
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.exceptions import (
    BlockingInquiryExistsError,
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    InquiryNumberSequenceError,
    MedicineCodeTypeNotAllowedError,
    OpenInquiryExistsError,
    PrescriptionDomainError,
    PrescriptionRpRequiredError,
    PrescriptionStatusTransitionError,
    RpNumberSequenceError,
)
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.primitives import (
    InquiryCategory,
    InquiryContent,
    InquiryNumber,
    InquiryTimestamp,
    MedicineCodeType,
    PrescriptionDocumentNumber,
    PrescriptionSourceType,
    PrescriptionStatus,
    _ensure_consecutive_from_one,
)
from app.domain.prescription.value_objects import (
    DepartmentInfo,
    MedicalInstitutionInfo,
    MedicineIdentifier,
    PrescriberInfo,
    PrescriberResponse,
    PrescriptionManagementInfo,
    PrescriptionPeriod,
    PrescriptionRp,
)
from app.domain.shared.preservation import (
    PreservationObligation,
    PreservationRecordKind,
    resolve_latest_retention_expiry_date,
)
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId

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


_ELECTRONIC_PRESCRIPTION_CODE_TYPES = frozenset(
    {
        MedicineCodeType.RECEIPT,
        MedicineCodeType.YJ,
        MedicineCodeType.GENERIC,
    }
)


@dataclass(frozen=True, eq=False, kw_only=True)
class PrescriptionInquiry(Entity[InquiryNumber]):
    """処方箋に対する疑義照会（薬剤師法第24条）の1レコード。

    疑義照会は処方内容に対して行われ、その照会結果が調剤の可否や処方内容の確定に直結するため、
    本モデルでは処方箋集約の配下として管理します。
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
    dispensed_on: date | None = None

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """処方箋集約が単独で判定できる不変条件を検証する。"""
        self._ensure_has_rp()
        self._ensure_rp_numbers_are_consecutive()
        self._ensure_inquiry_numbers_are_consecutive()
        self._ensure_medicine_code_types_match_source()
        self._ensure_ready_inquiries_are_resolved()

    def _ensure_ready_inquiries_are_resolved(self) -> None:
        """調剤可能状態（READY_FOR_DISPENSING）では、未回答の照会や調剤不可となった照会が存在しないことを検証する。"""
        if self.status is not PrescriptionStatus.READY_FOR_DISPENSING:
            return
        if self.has_open_inquiry:
            raise OpenInquiryExistsError()
        if self.has_blocking_inquiry:
            raise BlockingInquiryExistsError()

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
        """受取元形式（電子処方箋等）で使用不可と定められている薬品コード種別が含まれていないかを検証する。"""
        if self.source_type is not PrescriptionSourceType.ELECTRONIC:
            return
        for rp in self.rps:
            for medicine in rp.medicines:
                code_type = medicine.identifier.code_type
                if code_type not in _ELECTRONIC_PRESCRIPTION_CODE_TYPES:
                    raise MedicineCodeTypeNotAllowedError(
                        code_type_label=code_type.label
                    )

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def has_open_inquiry(self) -> bool:
        """回答待ち（未解決）の疑義照会が存在するかを判定する。"""
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

    def replace_rps(self, rps: tuple[PrescriptionRp, ...]) -> Self:
        """調剤可能な処方内容を差し替える。

        調剤工程や薬歴との整合を保てるかは集約単体では判定できないため、
        呼び出し側がそれらの状態を確認したうえで使用する。
        """
        if self.status is not PrescriptionStatus.READY_FOR_DISPENSING:
            raise PrescriptionStatusTransitionError(
                current=self.status.label,
                target="調剤可能な処方内容の差し替え",
            )
        return replace(self, rps=rps)

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
        # 照会追加で処方の確定が失効する。状態と履歴を同時に更新し、
        # 未回答を持つ調剤可能状態を途中にも作らない。
        return replace(
            self,
            inquiries=(*self.inquiries, inquiry),
            status=PrescriptionStatus.RECEIVED,
        )

    def resolve_inquiry(
        self, *, inquiry_number: InquiryNumber, response: PrescriberResponse
    ) -> Self:
        """疑義照会に回答を記録する。

        処方削除の回答は処方箋そのものを無効にするため、記録すると同時に取消へ
        畳む。調剤を止められるかどうかを導出プロパティのままにすると、下流は
        「未回答が無いこと」しか状態から読めず、削除された処方の調剤開始を
        止められない。既に調剤済・取消済なら回答は事実として記録するだけに
        留める（渡し終えた薬を後から取り消すことはできない）。
        """
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
        status = (
            PrescriptionStatus.CANCELLED
            if response.blocks_dispensing and not self.status.is_terminal
            else self.status
        )
        return replace(self, inquiries=tuple(resolved), status=status)

    # ------------------------------------------------------------------
    # 状態遷移
    # ------------------------------------------------------------------

    def ready_for_dispensing(self) -> Self:
        """処方を確定し、調剤セッションを開始可能な状態にする。

        未回答の疑義照会があるうちは進めない。処方の内容がまだ確定していない
        ためであり、これは集約が単独で判定できる。
        """
        return self._transition_to(PrescriptionStatus.READY_FOR_DISPENSING)

    def return_for_inquiry(self) -> Self:
        """疑義が生じたため受付済へ差し戻す。"""
        return self._transition_to(PrescriptionStatus.RECEIVED)

    def complete_dispensing(self, dispensed_on: date | None = None) -> Self:
        """全ての調剤が完了したことを記録する（調剤済）。

        遷移の契機は調剤編 ``リフィル処方箋情報レコード(521)`` の調剤終了区分で
        あり、「総使用回数に達したこと」ではない。規格は「達していないが次回
        以降の調剤が不要となった場合」も終了として扱うため、判断は
        Dispensing 側から渡される。
        """
        self._ensure_transition_allowed(PrescriptionStatus.DISPENSED)
        return replace(
            self,
            status=PrescriptionStatus.DISPENSED,
            dispensed_on=dispensed_on,
        )

    def calculate_retention_expiry_date(
        self,
        obligation: PreservationObligation,
        *additional_obligations: PreservationObligation,
    ) -> date:
        """処方箋の法定保存満了日を計算する。

        薬剤師法第27条（処方せんの保存）等に基づき、調剤済となった処方箋の
        調剤済日（dispensed_on）を起算日としてポリシーカタログから満了日を計算する。
        各義務には個別の起算日（(catalog, anchor_date) のタプル）を指定することもできる。
        複数のポリシーカタログが指定された場合は、各義務で計算した満了日のうち
        最も遅い日（最新満了日）を返す。
        """
        if self.dispensed_on is None:
            raise PrescriptionDomainError(
                "処方箋の保存満了日を計算するには調剤済日が必要です。"
            )
        return resolve_latest_retention_expiry_date(
            self.dispensed_on,
            PreservationRecordKind.PRESCRIPTION,
            obligation,
            *additional_obligations,
        )

    def cancel(self) -> Self:
        """処方箋を取消・無効にする。"""
        return self._transition_to(PrescriptionStatus.CANCELLED)

    def _transition_to(self, target: PrescriptionStatus) -> Self:
        """遷移表に従って状態を変更する。"""
        self._ensure_transition_allowed(target)
        return replace(self, status=target)

    def _ensure_transition_allowed(self, target: PrescriptionStatus) -> None:
        """遷移表にある状態変更であることを保証する。"""
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise PrescriptionStatusTransitionError(
                current=self.status.label, target=target.label
            )

    def _ensure_not_terminal(self, _target: PrescriptionStatus) -> None:
        """終端状態では内容を変更できないことを保証する。"""
        if self.status.is_terminal:
            raise PrescriptionStatusTransitionError(
                current=self.status.label, target="疑義照会の追加"
            )
