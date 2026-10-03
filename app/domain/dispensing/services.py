"""調剤プロセス（調剤録・調剤鑑査）に関わるドメインサービス。

無状態（Stateless）であり、調剤や処方箋などの本物のドメインオブジェクトを引数で受け取る。
調剤回数（初回・リフィル・分割）、処方箋の使用期間、次回調剤予定日、後発医薬品等への変更可否、
処方箋と調剤薬品の対応など、単体では判定できない処方原本との整合性チェックを担う。

調剤者・鑑査者が薬剤師かどうかはスタッフ管理側の事実であり、
Application層の資格Boundary経由で渡された資格情報（StaffQualifications）を検証する。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum, auto

from app.domain.dispensing.dispensing_process import (
    DispensedMedicine,
    DispensingProcess,
)
from app.domain.dispensing.exceptions import (
    DispensedMedicineNotInPrescriptionError,
    DispensedRpNotInPrescriptionError,
    DispensingAlreadyExistsError,
    DispensingOutsidePrescriptionPeriodError,
    DispensingPharmacistQualificationError,
    DispensingScheduleOutOfRangeError,
    InquiryNotAgreedError,
    InquiryReferenceNotInPrescriptionError,
    IterationExceedsInstructionError,
    PreviousDispensingCompletedError,
    PreviousDispensingUnknownError,
    SplitInstructionMissingError,
    SubstitutionNotAllowedError,
    SubstitutionOriginalMismatchError,
    SubstitutionRequiredError,
)
from app.domain.dispensing.primitives import (
    DispensingSplitReason,
    SubstitutionCategory,
)
from app.domain.prescription.prescription import (
    Prescription,
    PrescriptionInquiry,
    PrescriptionMedicine,
    PrescriptionRp,
)
from app.domain.prescription.primitives import (
    GenericSubstitutionRestrictionType,
    InquiryNumber,
    InquiryResultType,
)
from app.domain.shared.medicine import (
    MedicineCodeType,
    MedicineIdentifier,
    MedicineLineNumber,
    RpNumber,
)
from app.domain.staff.primitives import PharmacistProfile, StaffQualifications

#: リフィル2回目以降の調剤日が、前回の次回調剤予定日から離れてよい日数。
#: 出典: 保険調剤の理解のために（令和8年度）。
REFILL_SCHEDULE_TOLERANCE_DAYS = 7


class _MedicineCodeComparison(Enum):
    """記録された薬品コードの一致・不一致・比較不能を表す。"""

    MATCH = auto()
    MISMATCH = auto()
    UNKNOWN = auto()


def _compare_medicine_codes(
    prescribed: MedicineIdentifier, dispensed: MedicineIdentifier
) -> _MedicineCodeComparison:
    """同じ非NONE体系だけでコードを比較し、薬品の同等性は推測しない。"""
    if (
        prescribed.code_type != dispensed.code_type
        or prescribed.code_type == MedicineCodeType.NONE
    ):
        return _MedicineCodeComparison.UNKNOWN
    if prescribed.code == dispensed.code:
        return _MedicineCodeComparison.MATCH
    return _MedicineCodeComparison.MISMATCH


#: 処方箋の変更制限が禁じる代替調剤の種別。
#:
#: 別表16 の変更制限（3〜6・8）と、本コンテキストの代替調剤3種の対応表。
#: 判定を制限ごとの ``if`` で書くと、制限が増えたときに必ず書き漏れる。
_FORBIDDEN_SUBSTITUTIONS: dict[
    GenericSubstitutionRestrictionType, frozenset[SubstitutionCategory]
] = {
    GenericSubstitutionRestrictionType.NO_GENERIC: frozenset(
        {SubstitutionCategory.GENERIC_SUBSTITUTION}
    ),
    GenericSubstitutionRestrictionType.NO_FORM_CHANGE: frozenset(
        {SubstitutionCategory.DOSAGE_FORM_CHANGE}
    ),
    GenericSubstitutionRestrictionType.NO_STRENGTH_CHANGE: frozenset(
        {SubstitutionCategory.STRENGTH_CHANGE}
    ),
    GenericSubstitutionRestrictionType.NO_FORM_OR_STRENGTH_CHANGE: frozenset(
        {
            SubstitutionCategory.DOSAGE_FORM_CHANGE,
            SubstitutionCategory.STRENGTH_CHANGE,
        }
    ),
    # 患者自身が長期収載品を希望した選定療養指示。後発品へ替えると希望に反する。
    GenericSubstitutionRestrictionType.BRAND_REQUESTED_BY_PATIENT: frozenset(
        {SubstitutionCategory.GENERIC_SUBSTITUTION}
    ),
}

#: 処方箋の変更制限に拘束されない代替調剤種別。
#:
#: 疑義照会に基づく処方変更調剤は処方医との合意に基づくため、
#: 処方箋記載の変更制限（後発品不可等）には拘束されない。
_UNRESTRICTED_SUBSTITUTIONS: frozenset[SubstitutionCategory] = frozenset(
    {SubstitutionCategory.INQUIRY_MODIFIED}
)


def verify_substitution_restriction_table(
    *,
    restriction_types: set[GenericSubstitutionRestrictionType],
    categories: set[SubstitutionCategory],
) -> None:
    """変更制限と代替調剤種別の対応表が網羅されていることを検証する。

    どちらかに値を足して対応表を更新し忘れると、その組み合わせだけ
    変更制限の判定が素通りする。読み込み時に落とすための不変条件チェックであり、
    最適化実行（``python -O``）でも省略されないよう ``assert`` は使わない。
    """
    missing = restriction_types - set(_FORBIDDEN_SUBSTITUTIONS)
    if missing:
        raise RuntimeError(
            "変更制限の対応表に定義漏れがあります: "
            f"{sorted(str(item) for item in missing)}。"
        )
    forbidden_categories = {
        category
        for forbidden in _FORBIDDEN_SUBSTITUTIONS.values()
        for category in forbidden
    }
    classified_categories = forbidden_categories | _UNRESTRICTED_SUBSTITUTIONS
    unclassified_categories = categories - classified_categories
    if unclassified_categories:
        raise RuntimeError(
            "変更制限の対応表に未分類の代替調剤種別が含まれています: "
            f"{sorted(str(item) for item in unclassified_categories)}。"
        )
    unknown_categories = classified_categories - categories
    if unknown_categories:
        raise RuntimeError(
            "変更制限の対応表に未知の代替調剤種別が含まれています: "
            f"{sorted(str(item) for item in unknown_categories)}。"
        )


verify_substitution_restriction_table(
    restriction_types=set(GenericSubstitutionRestrictionType),
    categories=set(SubstitutionCategory),
)


class DispensingIterationUniquenessService:
    """同一処方箋に対して同じ調剤回数（1回目、リフィル2回目等）が重複して作成されないことを検証する。"""

    def ensure_no_conflict(
        self,
        process: DispensingProcess,
        existing_processes: Iterable[DispensingProcess],
    ) -> None:
        """同一法人・同一処方箋で調剤回数が重複していないことを検証する。

        同じ回が二重に登録されると、調剤基本料の算定回数も薬歴の記録も二重になる。
        同じレコードIDの現在行は候補から除外し、自身の状態変更を妨げない。
        """
        for existing in existing_processes:
            if existing.id == process.id:
                continue
            if (
                existing.corporate_id == process.corporate_id
                and existing.prescription_id == process.prescription_id
                and existing.iteration == process.iteration
            ):
                raise DispensingAlreadyExistsError(iteration=process.iteration.value)


class DispensingConsistencyService:
    """調剤内容と処方箋原本・前回調剤との整合性を検証する。

    開始時は ``ensure_consistent()``、内容変更時は
    ``ensure_content_matches_prescription()`` を入口として使う。
    内容の対応と変更制限は両入口で共通に検証する。
    """

    def ensure_consistent(
        self,
        process: DispensingProcess,
        prescription: Prescription,
        *,
        previous: DispensingProcess | None = None,
    ) -> None:
        """処方箋および前回調剤との整合性を一括で検証する。

        Args:
            process: 検証対象の調剤プロセス。
            prescription: 対象の処方箋。
            previous: 同一処方箋における**直前の回**の調剤記録。初回調剤では不要。

        Raises:
            DispensedRpNotInPrescriptionError: 処方箋に無い剤を調剤している場合。
            DispensedMedicineNotInPrescriptionError: 処方箋に無い薬品を
                調剤している場合。
            SubstitutionRequiredError: 異なる薬品コードの調剤に代替記録がない場合。
            SubstitutionOriginalMismatchError: 代替前の薬品情報が原本引用と異なる場合。
            SubstitutionNotAllowedError: 処方箋の変更制限に反する代替調剤。
            SplitInstructionMissingError: 医師の分割指示による調剤なのに、
                処方箋に分割指示が無い場合。
            IterationExceedsInstructionError: 処方箋の指示より多い回数の場合。
            DispensingOutsidePrescriptionPeriodError: 1回目が使用期間外の場合。
            PreviousDispensingUnknownError: 2回目以降なのに前回が渡されない場合。
            PreviousDispensingCompletedError: 前回が調剤終了だった場合。
            DispensingScheduleOutOfRangeError: 次回調剤予定日から離れすぎている場合。
        """
        self.ensure_content_matches_prescription(process, prescription)
        self.ensure_inquiry_references_exist(process, prescription)
        self.ensure_iteration_is_within_instruction(process, prescription)
        self.ensure_schedule_is_valid(process, prescription, previous=previous)

    def ensure_content_matches_prescription(
        self, process: DispensingProcess, prescription: Prescription
    ) -> None:
        """原本との薬品対応・代替前引用・変更制限を共通に検証する。

        内容変更では調剤日と回数が変わらないため、前回調剤の検証を要求しない。
        """
        self.ensure_rps_match_prescription(process, prescription)
        self.ensure_substitutions_are_allowed(process, prescription)

    # ------------------------------------------------------------------
    # 剤・薬品の対応
    # ------------------------------------------------------------------

    def ensure_rps_match_prescription(
        self, process: DispensingProcess, prescription: Prescription
    ) -> None:
        """剤・薬品の対応、コード変更の代替記録、代替前情報の原本引用を検証する。

        処方箋の**すべて**の剤を調剤することは要求しない。分割調剤・減数調剤では
        一部だけを調剤しうるため。逆向き（処方箋に無いものを調剤した）だけを拒否する。
        """
        for rp in process.dispensed_rps:
            prescribed_rp = _find_prescribed_rp(prescription, rp.rp_number)
            if prescribed_rp is None:
                raise DispensedRpNotInPrescriptionError(rp_number=rp.rp_number.value)
            prescribed_medicines = {
                medicine.line_number: medicine for medicine in prescribed_rp.medicines
            }
            for medicine in rp.medicines:
                prescribed = prescribed_medicines.get(medicine.line_number)
                if prescribed is None:
                    raise DispensedMedicineNotInPrescriptionError(
                        rp_number=rp.rp_number.value,
                        line_number=medicine.line_number.value,
                    )
                if medicine.substitution is not None and (
                    medicine.substitution.original_identifier != prescribed.identifier
                    or (
                        prescribed.identifier.code_type == MedicineCodeType.NONE
                        and medicine.substitution.original_name != prescribed.name
                    )
                ):
                    raise SubstitutionOriginalMismatchError(
                        rp_number=rp.rp_number.value,
                        line_number=medicine.line_number.value,
                    )
                if (
                    medicine.substitution is None
                    and _compare_medicine_codes(
                        prescribed.identifier, medicine.identifier
                    )
                    == _MedicineCodeComparison.MISMATCH
                ):
                    raise SubstitutionRequiredError(
                        rp_number=rp.rp_number.value,
                        line_number=medicine.line_number.value,
                    )

    # ------------------------------------------------------------------
    # 変更制限
    # ------------------------------------------------------------------

    def ensure_substitutions_are_allowed(
        self, process: DispensingProcess, prescription: Prescription
    ) -> None:
        """代替調剤が処方箋の変更制限に反しないことを検証する。

        薬剤師法第23条第2項（処方医の同意なき変更の禁止）に対応する。
        変更制限の指示が無い薬品には何も課さない。
        """
        for rp in process.dispensed_rps:
            for medicine in rp.medicines:
                if medicine.substitution is None:
                    continue
                prescribed = _find_prescribed_medicine(
                    prescription, rp.rp_number, medicine.line_number
                )
                if prescribed is None:
                    raise DispensedMedicineNotInPrescriptionError(
                        rp_number=rp.rp_number.value,
                        line_number=medicine.line_number.value,
                    )
                _ensure_category_is_allowed(medicine, prescribed)

    # ------------------------------------------------------------------
    # 疑義照会整合性
    # ------------------------------------------------------------------

    def ensure_inquiry_references_exist(
        self, process: DispensingProcess, prescription: Prescription
    ) -> None:
        """調剤が参照する疑義照会が処方箋に実在し、変更合意済みであることを検証する。

        疑義照会に基づく処方変更調剤（INQUIRY_MODIFIED）や数量調整（INQUIRY_AGREED）は、
        処方箋集約上の疑義照会が「処方変更（MODIFIED）」として合意されていることを要する。
        未回答や変更なし（UNCHANGED）、削除（DELETED）の照会を根拠にした変更調剤は拒否する。

        Raises:
            InquiryReferenceNotInPrescriptionError: 指定された照会連番が処方箋に存在しない場合。
            InquiryNotAgreedError: 照会が未回答、または結果区分が処方変更でない場合。
        """
        inquiries_by_id = {inquiry.id: inquiry for inquiry in prescription.inquiries}

        for rp in process.dispensed_rps:
            if (
                rp.quantity_adjustment is not None
                and rp.quantity_adjustment.inquiry_number is not None
            ):
                _ensure_inquiry_agreed(
                    rp.quantity_adjustment.inquiry_number, inquiries_by_id
                )

            for medicine in rp.medicines:
                if (
                    medicine.substitution is not None
                    and medicine.substitution.inquiry_number is not None
                ):
                    _ensure_inquiry_agreed(
                        medicine.substitution.inquiry_number, inquiries_by_id
                    )

    # ------------------------------------------------------------------
    # 調剤回数
    # ------------------------------------------------------------------

    def ensure_iteration_is_within_instruction(
        self, process: DispensingProcess, prescription: Prescription
    ) -> None:
        """調剤回数および合計分割回数が処方箋の指示の範囲内であることを検証する。

        集約側ではセッション単体の自己無撞着性（iteration <= total_split_count）を
        保証し、ここでは**処方箋側の指示（医師の分割指示・リフィル）との整合性**を検証する。
        """
        iteration = process.iteration.value
        management = prescription.management_info
        if process.split_reason is DispensingSplitReason.PRESCRIBER_INSTRUCTED:
            if management.split is None:
                raise SplitInstructionMissingError()
            _ensure_within(
                iteration=iteration,
                limit=management.split.total_split_count.value,
                instruction="医師の分割指示",
            )
            if process.total_split_count is not None:
                _ensure_within(
                    iteration=process.total_split_count.value,
                    limit=management.split.total_split_count.value,
                    instruction="医師の分割指示の全分割回数",
                )
        if management.refill is not None:
            _ensure_within(
                iteration=iteration,
                limit=management.refill.total_refill_count.value,
                instruction="リフィル総使用回数",
            )
            return
        if process.split_reason is None:
            _ensure_within(iteration=iteration, limit=1, instruction="通常処方箋")

    # ------------------------------------------------------------------
    # 調剤日
    # ------------------------------------------------------------------

    def ensure_schedule_is_valid(
        self,
        process: DispensingProcess,
        prescription: Prescription,
        *,
        previous: DispensingProcess | None = None,
    ) -> None:
        """調剤日が使用期間または次回調剤予定日の範囲内であることを検証する。"""
        if process.is_first_iteration:
            self._ensure_within_prescription_period(process, prescription)
            return
        self._ensure_follows_previous_schedule(process, previous)

    @staticmethod
    def _ensure_within_prescription_period(
        process: DispensingProcess, prescription: Prescription
    ) -> None:
        """1回目の調剤日が処方箋の使用期間内であることを検証する。

        「1回目の調剤を行うことが可能な期間については、使用期間に記載されている
        日までとする」。2回目以降には使用期間を課さない。
        """
        if not prescription.period.includes(process.dispensed_date.value):
            raise DispensingOutsidePrescriptionPeriodError(
                dispensed_on=process.dispensed_date.value.isoformat(),
                valid_to=prescription.period.valid_to.value.isoformat(),
            )

    @staticmethod
    def _ensure_follows_previous_schedule(
        process: DispensingProcess, previous: DispensingProcess | None
    ) -> None:
        """2回目以降の調剤日が前回の次回調剤予定日の前後7日以内であることを検証する。

        基準は**前回セッションが記録した次回調剤予定日**であり、投薬期間から
        計算した値ではない。計算に倒すと、実際の受け渡し予定と食い違う。

        前回セッションが渡されないときは判定を飛ばさずに拒否する。各回は別の
        保険薬局で行われうるが、その場合も
        調剤の状況は情報提供を通じて渡される前提であり、「分からないので通す」に
        倒すと予定日の判定が常に素通りする。
        """
        if previous is None:
            raise PreviousDispensingUnknownError(iteration=process.iteration.value)
        scheduled = previous.next_dispensing_date
        if scheduled is None:
            raise PreviousDispensingCompletedError()
        difference = abs((process.dispensed_date.value - scheduled.value).days)
        if difference > REFILL_SCHEDULE_TOLERANCE_DAYS:
            raise DispensingScheduleOutOfRangeError(
                dispensed_on=process.dispensed_date.value.isoformat(),
                scheduled_on=scheduled.value.isoformat(),
                tolerance_days=REFILL_SCHEDULE_TOLERANCE_DAYS,
            )


def _ensure_within(*, iteration: int, limit: int, instruction: str) -> None:
    """調剤回数が上限以内であることを検証する。"""
    if iteration > limit:
        raise IterationExceedsInstructionError(
            iteration=iteration, limit=limit, instruction=instruction
        )


def _find_prescribed_rp(
    prescription: Prescription, rp_number: RpNumber
) -> PrescriptionRp | None:
    """処方箋から指定のRP番号の剤を探す。"""
    for rp in prescription.rps:
        if rp.rp_number == rp_number:
            return rp
    return None


def _find_prescribed_medicine(
    prescription: Prescription,
    rp_number: RpNumber,
    line_number: MedicineLineNumber,
) -> PrescriptionMedicine | None:
    """処方箋から指定のRP番号・薬品連番の明細を探す。"""
    for rp in prescription.rps:
        if rp.rp_number != rp_number:
            continue
        for medicine in rp.medicines:
            if medicine.line_number == line_number:
                return medicine
    return None


def _ensure_category_is_allowed(
    dispensed: DispensedMedicine, prescribed: PrescriptionMedicine
) -> None:
    """1薬品の代替調剤種別が処方箋の変更制限に反しないことを検証する。"""
    restriction = prescribed.substitution_restriction
    if restriction is None:
        return
    if dispensed.substitution is None:
        return
    forbidden = _FORBIDDEN_SUBSTITUTIONS[restriction.restriction_type]
    if dispensed.substitution.category in forbidden:
        raise SubstitutionNotAllowedError(
            medicine_name=dispensed.name.value,
            restriction_label=restriction.restriction_type.label,
        )


def _ensure_inquiry_agreed(
    inquiry_number: InquiryNumber,
    inquiries_by_id: Mapping[InquiryNumber, PrescriptionInquiry],
) -> None:
    """指定された照会連番が処方箋に実在し、処方変更として合意されていることを検証する。"""
    inquiry = inquiries_by_id.get(inquiry_number)
    if inquiry is None:
        raise InquiryReferenceNotInPrescriptionError(
            inquiry_number=inquiry_number.value
        )
    if inquiry.response is None:
        raise InquiryNotAgreedError(
            inquiry_number=inquiry_number.value, result_type=None
        )
    if inquiry.response.result_type is not InquiryResultType.MODIFIED:
        raise InquiryNotAgreedError(
            inquiry_number=inquiry_number.value,
            result_type=inquiry.response.result_type.value,
        )


class DispensingPharmacistService:
    """調剤者・鑑査者が薬剤師資格を持つかを検証する。

    薬剤師法第19条（調剤の制限）により、薬剤師でなければ販売または授与の目的で調剤してはならない。
    調剤プロセス側にはスタッフIDのみを保持しているため、Application層経由で渡された
    本物の資格情報（StaffQualifications）を本サービスが受け取って検証する。
    """

    def ensure_dispenser(self, qualifications: StaffQualifications) -> None:
        """調剤者が薬剤師資格を持つことを検証する（薬剤師法第19条）。"""
        self._ensure_pharmacist(qualifications, role_label="調剤者")

    def ensure_verifier(self, qualifications: StaffQualifications) -> None:
        """最終鑑査者が薬剤師資格を持つことを検証する。"""
        self._ensure_pharmacist(qualifications, role_label="最終鑑査者")

    def ensure_auditor(self, qualifications: StaffQualifications) -> None:
        """処方鑑査者が薬剤師資格を持つことを検証する。

        相互作用・重複投薬・用量の確認は薬学的判断であり、調剤補助では行えない。
        """
        self._ensure_pharmacist(qualifications, role_label="処方鑑査者")

    @staticmethod
    def _ensure_pharmacist(
        qualifications: StaffQualifications, *, role_label: str
    ) -> None:
        """薬剤師資格の保有を検証する。

        Raises:
            DispensingPharmacistQualificationError: 薬剤師資格が無い場合。
        """
        if not qualifications.has(PharmacistProfile):
            raise DispensingPharmacistQualificationError(role_label=role_label)
