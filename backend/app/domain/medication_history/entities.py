"""medication_historyのエンティティと集約。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any, ClassVar, Self, cast
from uuid import uuid5, uuid7

from app.domain.care_event.identifiers import EventId
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.foundation.entity import AggregateRoot, Entity
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import (
    AdverseReactionNotFoundError,
    AllergyNotFoundError,
    ConcurrentMedicationNotFoundError,
    DuplicatedTracingReportIdError,
    DuplicateMajorCategoryError,
    DuplicateMediumCategoryError,
    FinalizationDateBeforeCounselingError,
    FinalizationDelayReasonRequiredError,
    FinalizationStaffRequiredError,
    MajorCategoryNotFoundError,
    MedicalConditionNotFoundError,
    MedicationHistoryAlreadyFinalizedError,
    MedicationHistoryDomainError,
    MedicationHistoryNotFinalizedError,
    MedicationHistoryUnassessedItemsError,
    ProfilePatientMismatchError,
    RequiredCategoryMissingError,
    SoapContentRequiredError,
    TracingReportAlreadyRespondedError,
    TracingReportDateBeforeCounselingError,
    TracingReportNotFoundError,
    TracingReportOnDraftError,
    TracingReportResponseDateBeforeProvidedError,
    UnfinalizedRecordProjectionError,
)
from app.domain.medication_history.identifiers import (
    AmendmentId,
    CategoryCatalogId,
    FactRecordId,
    FollowUpId,
    MedicationHistoryRecordId,
    PatientMedicalProfileId,
    TracingReportId,
)
from app.domain.medication_history.primitives import (
    AllergenName,
    AmendmentReason,
    AmendmentTimestamp,
    CategoryDisplayOrder,
    ConditionName,
    ConditionStatus,
    CounselingMethod,
    CounselingTimestamp,
    ExternalCorrectionDecision,
    ExternalCorrectionReason,
    ExternalCorrectionStatus,
    ExternalCorrectionTimestamp,
    FactCorrectionOperation,
    FactCorrectionReason,
    FactCorrectionTimestamp,
    FactFieldName,
    FactTarget,
    FinalizationDelayReason,
    FinalizedTimestamp,
    FollowUpRecordedTimestamp,
    MajorCategoryCode,
    MajorCategoryName,
    MedicalInstitutionName,
    MedicationHistoryImportTimestamp,
    MedicationHistoryRecordedTimestamp,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
    MedicineName,
    MediumCategoryCode,
    MediumCategoryName,
    PhysicianName,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportTimestamp,
)
from app.domain.medication_history.value_objects import (
    FACT_ARRAY_TYPES,
    FACT_FIELD_TYPES,
    AdverseReactionRecord,
    AllergyRecord,
    BillingAddition,
    CategorizedNote,
    ConcurrentMedicationRecord,
    EffectiveMedicationHistoryFacts,
    ExternalCorrectionReviewEvent,
    ExternalPrescriptionCorrection,
    FactArrayValue,
    FactValue,
    FamilyPharmacistAgreement,
    GenericPreference,
    HandbookStatus,
    LifestyleProfile,
    MajorCategoryDefinition,
    MedicalConditionRecord,
    MedicationHistoryAmendment,
    MediumCategoryDefinition,
    ProfileProvenance,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
    TracingReportResponse,
)
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.shared.preservation import (
    PreservationObligation,
    PreservationRecordKind,
    latest_retention_expiry_date,
    resolve_latest_retention_expiry_date,
)
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId

_SOAP_SECTION_MAPPING: dict[str, str] = {
    "s": "subjective",
    "o": "objective",
    "a": "assessment",
    "p": "plan",
}


@dataclass(frozen=True, eq=False, kw_only=True)
class FactElement(Entity[FactRecordId]):
    """原本または訂正で追加された配列要素。"""

    id: FactRecordId
    value: FactArrayValue


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryFactCorrection(Entity[FactRecordId]):
    """原本を変更せず積み上げる一件の訂正。"""

    id: FactRecordId
    target: FactTarget
    field_name: FactFieldName
    operation: FactCorrectionOperation
    before: FactValue | None
    after: FactValue | None
    reason: FactCorrectionReason
    corrected_by: StaffId
    recorded_at: FactCorrectionTimestamp
    element_id: FactRecordId | None = None

    def validate(self) -> None:
        """対象項目の型と操作の組み合わせを監査記録の構築時に検証する。"""
        field = self.field_name.value
        is_array = field in FACT_ARRAY_TYPES
        expected = (FACT_ARRAY_TYPES if is_array else FACT_FIELD_TYPES)[field]
        if not is_array and self.target.value != field:
            raise DomainValidationError("訂正対象と事実項目が一致しません。")
        if (
            self.operation is FactCorrectionOperation.APPEND
            and self.target.value != field
        ):
            raise DomainValidationError("追加先の配列項目が一致しません。")
        for value in (self.before, self.after):
            if value is not None and not isinstance(value, expected):
                raise DomainValidationError("訂正値の型が対象項目と異なります。")
        if self.operation is FactCorrectionOperation.RETRACT and self.after is not None:
            raise DomainValidationError("取消しには訂正後の値を指定できません。")
        if self.operation is FactCorrectionOperation.APPEND:
            if (
                not is_array
                or self.element_id is None
                or self.after is None
                or self.before is not None
            ):
                raise DomainValidationError("配列追加には新しい要素IDと値が必要です。")
        elif self.element_id is not None:
            raise DomainValidationError("要素IDの新規発行は配列追加時だけ許可します。")


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryCategoryCatalog(AggregateRoot[CategoryCatalogId]):
    """法人ごとの薬歴記載区分（大区分・中区分）を管理する集約ルート。"""

    id: CategoryCatalogId
    corporate_id: CorporateId
    major_categories: tuple[MajorCategoryDefinition, ...]
    medium_categories: tuple[MediumCategoryDefinition, ...]

    def validate(self) -> None:
        """集約の不変条件（大区分の存在、コード重複防止等）を検証する。"""
        # 大区分コードの重複検証
        major_codes = [m.code.value for m in self.major_categories]
        if len(major_codes) != len(set(major_codes)):
            raise DuplicateMajorCategoryError()

        # 中区分コードの重複検証
        medium_codes = [m.code.value for m in self.medium_categories]
        if len(medium_codes) != len(set(medium_codes)):
            raise DuplicateMediumCategoryError()

        # 中区分の親大区分コードの存在確認
        major_code_set = set(major_codes)
        for med in self.medium_categories:
            if med.major_category_code.value not in major_code_set:
                raise MajorCategoryNotFoundError()

    @classmethod
    def create_default(cls, *, corporate_id: CorporateId) -> Self:
        """新規法人向けの標準区分カタログを構築する。"""
        soap_code = MajorCategoryCode("soap")
        statutory_code = MajorCategoryCode("statutory")

        major_categories = (
            MajorCategoryDefinition(
                code=soap_code,
                name=MajorCategoryName("SOAP"),
                display_order=CategoryDisplayOrder(1),
            ),
            MajorCategoryDefinition(
                code=statutory_code,
                name=MajorCategoryName("法令"),
                display_order=CategoryDisplayOrder(2),
            ),
        )

        medium_categories = (
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S（主観的情報）"),
                display_order=CategoryDisplayOrder(1),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("o"),
                major_category_code=soap_code,
                name=MediumCategoryName("O（客観的情報）"),
                display_order=CategoryDisplayOrder(2),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("a"),
                major_category_code=soap_code,
                name=MediumCategoryName("A（評価・判断）"),
                display_order=CategoryDisplayOrder(3),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P（計画・指導）"),
                display_order=CategoryDisplayOrder(4),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("handbook"),
                major_category_code=statutory_code,
                name=MediumCategoryName("お薬手帳"),
                display_order=CategoryDisplayOrder(5),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("residual_drug"),
                major_category_code=statutory_code,
                name=MediumCategoryName("残薬確認"),
                display_order=CategoryDisplayOrder(6),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("concurrent_medication"),
                major_category_code=statutory_code,
                name=MediumCategoryName("併用薬確認"),
                display_order=CategoryDisplayOrder(7),
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("other"),
                major_category_code=statutory_code,
                name=MediumCategoryName("その他"),
                display_order=CategoryDisplayOrder(8),
            ),
        )

        return cls(
            id=CategoryCatalogId.generate(),
            corporate_id=corporate_id,
            major_categories=major_categories,
            medium_categories=medium_categories,
        )

    def add_major_category(self, definition: MajorCategoryDefinition) -> Self:
        """大区分を追加する。"""
        if any(m.code == definition.code for m in self.major_categories):
            raise DuplicateMajorCategoryError()
        return replace(self, major_categories=(*self.major_categories, definition))

    def update_major_category(self, definition: MajorCategoryDefinition) -> Self:
        """既存の大区分を更新する。"""
        new_majors = tuple(
            definition if m.code == definition.code else m
            for m in self.major_categories
        )
        return replace(self, major_categories=new_majors)

    def add_medium_category(self, definition: MediumCategoryDefinition) -> Self:
        """中区分を追加する。"""
        if any(m.code == definition.code for m in self.medium_categories):
            raise DuplicateMediumCategoryError()
        return replace(self, medium_categories=(*self.medium_categories, definition))

    def update_medium_category(self, definition: MediumCategoryDefinition) -> Self:
        """既存の中区分を更新する。"""
        new_mediums = tuple(
            definition if m.code == definition.code else m
            for m in self.medium_categories
        )
        return replace(self, medium_categories=new_mediums)

    def medium_categories_for(
        self, major_code: MajorCategoryCode
    ) -> tuple[MediumCategoryDefinition, ...]:
        """指定した大区分に属する中区分を表示順に返す。"""
        matched = [
            m for m in self.medium_categories if m.major_category_code == major_code
        ]
        return tuple(sorted(matched, key=lambda m: m.display_order.value))

    def required_medium_categories(self) -> tuple[MediumCategoryDefinition, ...]:
        """法人ルールとして確定時に必須とされている有効な中区分を返す。"""
        required = [m for m in self.medium_categories if m.is_required and m.is_enabled]
        return tuple(sorted(required, key=lambda m: m.display_order.value))

    def validate_record_compliance(self, record: MedicationHistoryRecord) -> None:
        """薬歴記録が本カタログの法人必須ルールを満たしているか検証する。"""
        required_mediums = self.required_medium_categories()
        for req in required_mediums:
            code_val = req.code.value.lower()
            if code_val in _SOAP_SECTION_MAPPING:
                field_name = _SOAP_SECTION_MAPPING[code_val]
                notes = getattr(record.effective_soap, field_name)
                if not any(note.has_content for note in notes):
                    raise RequiredCategoryMissingError(
                        medium_category_name=req.name.value
                    )
            else:
                has_in_additional = any(
                    note.medium_category_code == req.code and note.has_content
                    for note in record.effective_facts.additional_notes
                )
                if not has_in_additional:
                    raise RequiredCategoryMissingError(
                        medium_category_name=req.name.value
                    )


@dataclass(frozen=True, eq=False, kw_only=True)
class FollowUpRecord(Entity[FollowUpId]):
    """服薬期間中のフォローアップ（調剤後フォロー）記録。

    固有の識別子（FollowUpId）で同一性を持つ集約内子エンティティ。
    """

    id: FollowUpId
    counselor_id: StaffId
    followed_up_at: CounselingTimestamp
    method: CounselingMethod | None
    soap: SoapRecord
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None = False
    source_system: MedicationHistorySourceSystem | None = None
    recorded_at: FollowUpRecordedTimestamp | None = None
    recorded_by: StaffId | None = None
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "フォローアップID",
        "counselor_id": "指導薬剤師",
        "followed_up_at": "フォローアップ日時",
        "method": "実施方法",
        "soap": "SOAP記録",
        "handbook_status": "お薬手帳確認",
        "residual_drug": "残薬確認",
        "information_sheet_provided": "情報提供文書有無",
        "source_system": "記録由来システム",
        "profile_updates": "頭書き差分",
        "additional_notes": "追加記載メモ",
    }

    def validate(self) -> None:
        """白紙のフォローアップ記録を拒否する。"""
        if (self.recorded_at is None) != (self.recorded_by is None):
            raise DomainValidationError(
                "フォローアップ登録日時と登録者は両方設定するか、両方未設定にしてください。"
            )
        has_soap = self.soap.has_content
        has_additional = any(note.has_content for note in self.additional_notes)
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()


@dataclass(frozen=True, eq=False, kw_only=True)
class TracingReport(Entity[TracingReportId]):
    """処方医への服薬情報等提供（トレーシングレポート）記録。

    固有の識別子（TracingReportId）を持ち、処方医返答の受領・記録という
    状態遷移（ライフサイクル）を持つ集約内子エンティティ。
    """

    id: TracingReportId
    reporter_id: StaffId
    provided_at: TracingReportTimestamp
    medical_institution_name: MedicalInstitutionName
    physician_name: PhysicianName
    category: TracingReportCategory
    fee_category: TracingReportFeeCategory
    delivery_method: TracingReportDeliveryMethod
    content: TracingReportContent
    response: TracingReportResponse | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "トレーシングレポートID",
        "reporter_id": "作成薬剤師",
        "provided_at": "提供日時",
        "medical_institution_name": "提供先医療機関",
        "physician_name": "提供先処方医",
        "category": "提供区分",
        "fee_category": "算定区分",
        "delivery_method": "提供手段",
        "content": "提供内容",
        "response": "医師返答",
    }

    @property
    def is_responded(self) -> bool:
        """医師からの返答が記録されているか。"""
        return self.response is not None

    def record_response(self, response: TracingReportResponse) -> Self:
        """処方医からの返答を記録する。

        Raises:
            TracingReportAlreadyRespondedError: 既に返答が記録されている場合。
            TracingReportResponseDateBeforeProvidedError: 返答日時が提供日時より前の場合。
        """
        if self.response is not None:
            raise TracingReportAlreadyRespondedError()
        if response.responded_at.value < self.provided_at.value:
            raise TracingReportResponseDateBeforeProvidedError()
        return replace(self, response=response)


_FACT_VALUE_ABSENT = object()


def _replace_fact_field[T](value: T, field_name: str, new_value: object) -> T:
    """指定されたフィールドの値を動的に更新するヘルパー関数。"""
    return cast(T, replace(cast(Any, value), **{field_name: new_value}))


@dataclass(frozen=True, eq=False, kw_only=True)
class PatientMedicalProfile(AggregateRoot[PatientMedicalProfileId]):
    """患者の継続的な医療プロファイル（頭書き / フェイスシート）。

    本集約は薬歴からの投影であるため、独立した有効/無効といったライフサイクル状態は持ちません。
    各項目の終了や治癒などは、各レコード内の期間情報（終了日や状態区分など）で表現します。
    """

    id: PatientMedicalProfileId
    corporate_id: CorporateId
    patient_id: PatientId
    allergies: tuple[AllergyRecord, ...] = ()
    adverse_reactions: tuple[AdverseReactionRecord, ...] = ()
    medical_conditions: tuple[MedicalConditionRecord, ...] = ()
    concurrent_medications: tuple[ConcurrentMedicationRecord, ...] = ()
    lifestyle: LifestyleProfile | None = None
    generic_preference: GenericPreference | None = None
    family_pharmacist: FamilyPharmacistAgreement | None = None

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    def active_concurrent_medications(
        self, target_date: date
    ) -> tuple[ConcurrentMedicationRecord, ...]:
        """指定日時点で有効な併用薬の一覧を取得する。

        タイムゾーンのズレや暗黙のシステム日付依存を防ぐため、基準日を引数で明示的に受け取ります。
        """
        return tuple(
            item
            for item in self.concurrent_medications
            if item.is_active_on(target_date)
        )

    @property
    def contraindication_conditions(self) -> tuple[MedicalConditionRecord, ...]:
        """禁忌チェックの対象となる疾患の一覧を取得する。"""
        return tuple(
            item for item in self.medical_conditions if item.is_contraindication_target
        )

    @property
    def source_record_ids(self) -> tuple[str, ...]:
        """頭書きの各要素が由来する薬歴IDの一覧（重複を含む）。"""
        return tuple(
            str(provenance.source_record_id.value)
            for provenance in self._all_provenances()
        )

    def _all_provenances(self) -> tuple[ProfileProvenance, ...]:
        """保持しているすべての要素の由来を平坦に返す。"""
        singles = (self.lifestyle, self.generic_preference, self.family_pharmacist)
        return (
            *(item.provenance for item in self.allergies),
            *(item.provenance for item in self.adverse_reactions),
            *(item.provenance for item in self.medical_conditions),
            *(item.provenance for item in self.concurrent_medications),
            *(item.provenance for item in singles if item is not None),
        )

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def empty_for(cls, *, corporate_id: CorporateId, patient_id: PatientId) -> Self:
        """指定された患者の初期状態（投影前の空のプロファイル）を作成する。"""
        return cls(
            id=PatientMedicalProfileId.generate(),
            corporate_id=corporate_id,
            patient_id=patient_id,
        )

    @classmethod
    def rebuild_from(
        cls,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        records: tuple[MedicationHistoryRecord, ...],
    ) -> Self:
        """確定済みの薬歴一覧から時系列順に差分を適用し、患者頭書きプロファイルを再構築する。"""
        profile = cls.empty_for(corporate_id=corporate_id, patient_id=patient_id)

        raw_events: list[
            tuple[datetime, datetime | None, str, MedicationHistoryRecord]
        ] = []
        for record in records:
            if not record.is_projection_eligible:
                continue
            facts = record.effective_facts
            if facts.counselor_id is None or facts.counseled_at is None:
                raise MedicationHistoryDomainError(
                    "頭書きへ投影する薬歴には実際の指導者と指導日時が必要です。"
                )
            audit_time = (
                record.finalized_at.value
                if record.finalized_at is not None
                else record.recorded_at.value
                if record.recorded_at is not None
                else None
            )
            raw_events.append(
                (
                    facts.counseled_at.value,
                    audit_time,
                    str(record.id.value),
                    record,
                )
            )

        raw_events.sort(
            key=lambda item: (
                item[0],
                item[1] is None,
                item[1] or item[0],
                item[2],
            )
        )
        for _, _, _, record in raw_events:
            profile = profile.apply(record)
        return profile

    # ------------------------------------------------------------------
    # 投影（唯一の状態変更）
    # ------------------------------------------------------------------

    def apply(self, record: MedicationHistoryRecord) -> Self:
        """確定済み薬歴に記録された頭書き更新差分を適用する。

        各臨床情報の由来（記録ID・指導者・指導日時など）は渡された薬歴オブジェクトから自動抽出されます。

        Raises:
            ProfilePatientMismatchError: 異なる患者または別法人の薬歴が渡された場合。
            UnfinalizedRecordProjectionError: 未確定（下書き）の薬歴が渡された場合。
            ConcurrentMedicationNotFoundError: 終了対象として指定された併用薬が存在しない場合。
        """
        self._ensure_same_patient(record)
        if not record.is_projection_eligible:
            raise UnfinalizedRecordProjectionError()
        facts = record.effective_facts
        if facts.counselor_id is None or facts.counseled_at is None:
            raise MedicationHistoryDomainError(
                "頭書きへの投影には実際の指導者と指導日時が必要です。"
            )
        provenance = _provenance_of(record)
        return self._apply_intents(facts.profile_updates, provenance)

    def _apply_intents(
        self, intents: ProfileUpdateIntents, provenance: ProfileProvenance
    ) -> Self:
        """差分群を指定された由来で頭書きに反映する。"""
        updated = replace(
            self,
            allergies=(
                *self.allergies,
                *(
                    AllergyRecord(
                        allergen=intent.allergen,
                        reaction=intent.reaction,
                        severity=intent.severity,
                        provenance=provenance,
                    )
                    for intent in intents.new_allergies
                ),
            ),
            adverse_reactions=(
                *self.adverse_reactions,
                *(
                    AdverseReactionRecord(
                        medicine_name=intent.medicine_name,
                        symptom=intent.symptom,
                        occurred_on=intent.occurred_on,
                        provenance=provenance,
                    )
                    for intent in intents.new_adverse_reactions
                ),
            ),
            medical_conditions=(
                *self.medical_conditions,
                *(
                    MedicalConditionRecord(
                        condition_name=intent.condition_name,
                        condition_status=intent.condition_status,
                        is_contraindication_target=intent.is_contraindication_target,
                        provenance=provenance,
                    )
                    for intent in intents.new_conditions
                ),
            ),
            concurrent_medications=(
                *self.concurrent_medications,
                *(
                    ConcurrentMedicationRecord(
                        medicine_name=intent.medicine_name,
                        category=intent.category,
                        started_on=intent.started_on,
                        prescriber_institution=intent.prescriber_institution,
                        provenance=provenance,
                    )
                    for intent in intents.new_concurrent_medications
                ),
            ),
            lifestyle=(
                LifestyleProfile(
                    note=intents.lifestyle_update.note, provenance=provenance
                )
                if intents.lifestyle_update is not None
                else self.lifestyle
            ),
            generic_preference=(
                GenericPreference(
                    preference=intents.generic_preference_update.preference,
                    provenance=provenance,
                )
                if intents.generic_preference_update is not None
                else self.generic_preference
            ),
            family_pharmacist=(
                FamilyPharmacistAgreement(
                    pharmacist_id=intents.family_pharmacist_update.pharmacist_id,
                    agreed_on=intents.family_pharmacist_update.agreed_on,
                    provenance=provenance,
                )
                if intents.family_pharmacist_update is not None
                else self.family_pharmacist
            ),
        )
        for allergy_intent in intents.retracted_allergies:
            updated = updated._retract_allergy(allergy_intent.allergen)
        for adverse_intent in intents.retracted_adverse_reactions:
            updated = updated._retract_adverse_reaction(adverse_intent.medicine_name)
        for condition_update in intents.updated_conditions:
            updated = updated._update_condition_status(
                condition_update.condition_name,
                condition_update.new_status,
                condition_update.is_contraindication_target,
                provenance,
            )
        for condition_retract in intents.retracted_conditions:
            updated = updated._retract_condition(condition_retract.condition_name)
        for stop_intent in intents.stopped_concurrent_medications:
            updated = updated._close_concurrent_medication(
                stop_intent.medicine_name, stop_intent.ended_on
            )
        return updated

    def _retract_allergy(self, allergen: AllergenName) -> Self:
        """誤登録または否定されたアレルギー歴を取り消す。"""
        kept = [item for item in self.allergies if item.allergen != allergen]
        if len(kept) == len(self.allergies):
            raise AllergyNotFoundError(allergen=allergen.value)
        return replace(self, allergies=tuple(kept))

    def _retract_adverse_reaction(self, medicine_name: MedicineName) -> Self:
        """誤登録または否定された副作用歴を取り消す。"""
        kept = [
            item
            for item in self.adverse_reactions
            if item.medicine_name != medicine_name
        ]
        if len(kept) == len(self.adverse_reactions):
            raise AdverseReactionNotFoundError(medicine_name=medicine_name.value)
        return replace(self, adverse_reactions=tuple(kept))

    def _update_condition_status(
        self,
        condition_name: ConditionName,
        new_status: ConditionStatus,
        is_contraindication_target: bool | None,
        provenance: ProfileProvenance,
    ) -> Self:
        """既往疾患の状態（治癒・寛解・コントロール等）を更新する。"""
        updated_conditions: list[MedicalConditionRecord] = []
        found = False
        for item in self.medical_conditions:
            if item.condition_name == condition_name:
                contraindication = (
                    is_contraindication_target
                    if is_contraindication_target is not None
                    else item.is_contraindication_target
                )
                updated_conditions.append(
                    replace(
                        item,
                        condition_status=new_status,
                        is_contraindication_target=contraindication,
                        provenance=provenance,
                    )
                )
                found = True
            else:
                updated_conditions.append(item)
        if not found:
            raise MedicalConditionNotFoundError(condition_name=condition_name.value)
        return replace(self, medical_conditions=tuple(updated_conditions))

    def _retract_condition(self, condition_name: ConditionName) -> Self:
        """誤登録された疾患情報を取り消す。"""
        kept = [
            item
            for item in self.medical_conditions
            if item.condition_name != condition_name
        ]
        if len(kept) == len(self.medical_conditions):
            raise MedicalConditionNotFoundError(condition_name=condition_name.value)
        return replace(self, medical_conditions=tuple(kept))

    def _close_concurrent_medication(
        self, medicine_name: MedicineName, ended_on: date
    ) -> Self:
        """継続中の併用薬を終了させる。

        同名で継続中の行が複数あることは通常ないが、あれば全て終了させる。
        「どれか1件だけ」にすると、どれを選ぶかが並び順の規約になる。
        """
        closed: list[ConcurrentMedicationRecord] = []
        found = False
        for item in self.concurrent_medications:
            if item.medicine_name == medicine_name and item.ended_on is None:
                closed.append(item.close(ended_on))
                found = True
            else:
                closed.append(item)
        if not found:
            raise ConcurrentMedicationNotFoundError(medicine_name=medicine_name.value)
        return replace(self, concurrent_medications=tuple(closed))

    def _ensure_same_patient(self, record: MedicationHistoryRecord) -> None:
        """投影しようとしている薬歴が同一法人・同一患者のものかを検証する。"""
        if (
            record.corporate_id != self.corporate_id
            or record.patient_id != self.patient_id
        ):
            raise ProfilePatientMismatchError()


def _provenance_of(record: MedicationHistoryRecord) -> ProfileProvenance:
    """薬歴から由来を組み立てる。

    登録日は服薬指導日時のUTC日付とする。頭書きは監査で「誰がいつ登録したか」を
    示すためのものなので、投影を実行した時刻ではなく指導の時刻を根拠にする。
    """
    facts = record.effective_facts
    if facts.counselor_id is None or facts.counseled_at is None:
        raise MedicationHistoryDomainError(
            "頭書きの由来には実際の指導者と指導日時が必要です。"
        )
    return ProfileProvenance(
        source_record_id=record.id,
        recorded_by=facts.counselor_id,
        recorded_on=facts.counseled_at.value.date(),
    )


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryRecord(AggregateRoot[MedicationHistoryRecordId]):
    """1回の服薬指導の記録を管理する集約ルート。"""

    id: MedicationHistoryRecordId
    event_id: EventId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    dispensing_id: DispensingId | None
    prescription_id: PrescriptionId | None
    counselor_id: StaffId | None
    counseled_at: CounselingTimestamp | None
    method: CounselingMethod | None
    soap: SoapRecord
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None = None
    # 別モジュールの frozen dataclass なので ruff が不変性を追えない（RUF009）。
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()
    billing_additions: tuple[BillingAddition, ...] = ()
    source_system: MedicationHistorySourceSystem | None = None
    imported_at: MedicationHistoryImportTimestamp | None = None
    recorded_by: StaffId | None = None
    recorded_at: MedicationHistoryRecordedTimestamp | None = None
    status: MedicationHistoryStatus = MedicationHistoryStatus.DRAFT
    amendments: tuple[MedicationHistoryAmendment, ...] = ()
    tracing_reports: tuple[TracingReport, ...] = ()
    finalized_at: FinalizedTimestamp | None = None
    finalized_by: StaffId | None = None
    delay_reason: FinalizationDelayReason | None = None
    review_result: MedicationHistoryReviewResult | None = None
    retention_expiry_date: date | None = None
    external_corrections: tuple[ExternalPrescriptionCorrection, ...] = ()
    fact_corrections: tuple[MedicationHistoryFactCorrection, ...] = ()

    # ------------------------------------------------------------------
    # 不変条件
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """薬歴の業務ルール（記入漏れや状態の不整合がないか）を検証する。

        SOAPなどの指導記録の記入チェックは、薬歴の確定時（FINALIZED）にのみ実施します。
        下書き（DRAFT）作成中には、患者への服薬指導を行いながら段階的に記録できるよう
        未入力項目があっても保存可能です。
        """
        self._ensure_fact_corrections_are_valid()
        self._ensure_counseling_provenance_is_valid()
        self._ensure_amendments_only_after_finalized()
        self._ensure_finalized_soap_is_complete()
        self._ensure_finalized_review_has_authored_evidence()
        self._ensure_finalized_items_are_assessed()
        self._ensure_finalization_metadata_is_valid()

    def _ensure_finalized_items_are_assessed(self) -> None:
        """薬歴確定時に、服薬指導方法（対面・オンライン等）などの必須確認項目が記録されているかを検証する。"""
        if not self.status.is_finalized:
            return
        required_items: list[tuple[str, object | None]] = [
            ("服薬指導方法", self.effective_facts.method)
        ]
        missing_items = tuple(label for label, value in required_items if value is None)
        if missing_items:
            raise MedicationHistoryUnassessedItemsError(missing_items=missing_items)

    def _ensure_finalized_review_has_authored_evidence(self) -> None:
        """薬歴確定時、薬剤師による薬学的判断（Assessment）または指導方針（Plan）が記録されていることを検証する。"""
        review_result = self.effective_facts.review_result
        if not self.status.is_finalized or review_result is None:
            return
        if (
            review_result
            is MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS
        ):
            return
        if not any(
            note.has_content for note in (*self.soap.assessment, *self.soap.plan)
        ):
            raise MedicationHistoryDomainError(
                "確定には薬剤師が記載したAssessmentまたはPlanが必要です。"
            )

    def _ensure_amendments_only_after_finalized(self) -> None:
        """過去記録の訂正・追記（amendments）は、確定済みの薬歴に対してのみ許可されることを検証する。"""
        if self.amendments and not self.status.is_finalized:
            raise MedicationHistoryNotFinalizedError()

    def _ensure_finalized_soap_is_complete(self) -> None:
        """確定済みの薬歴に、指導内容等の記載が1件以上存在することを検証する。

        S/O/A/Pの全項目を画一的に必須とするものではありませんが、
        SOAPおよび補足メモの双方が未記入である白紙状態での確定は拒否します。
        """
        if not self.status.is_finalized:
            return
        has_soap = self.effective_soap.has_content
        has_additional = any(
            note.has_content for note in self.effective_facts.additional_notes
        )
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()

    def _ensure_finalization_metadata_is_valid(self) -> None:
        """確定日時、確定薬剤師、翌日以降確定時の遅延理由などが正しく記録されているかを検証する。"""
        facts = self.effective_facts
        if self.status is MedicationHistoryStatus.FINALIZED:
            if self.finalized_at is None or self.finalized_by is None:
                raise FinalizationStaffRequiredError()
            if facts.counseled_at is None or facts.counselor_id is None:
                raise MedicationHistoryDomainError(
                    "確定済の薬歴には実際の指導者と指導日時が必要です。"
                )
            if self.finalized_at.value < facts.counseled_at.value:
                raise FinalizationDateBeforeCounselingError()
            if (
                self.finalized_at.value.date() != facts.counseled_at.value.date()
                and facts.delay_reason is None
            ):
                raise FinalizationDelayReasonRequiredError()
        elif self.status is MedicationHistoryStatus.DRAFT:
            if (
                self.finalized_at is not None
                or self.finalized_by is not None
                or self.delay_reason is not None
                or self.review_result is not None
            ):
                raise MedicationHistoryDomainError(
                    "下書き状態の薬歴に確定メタデータは設定できません。"
                )
        elif (
            self.finalized_at is not None
            or self.finalized_by is not None
            or facts.delay_reason is not None
            or facts.review_result is not None
        ):
            raise MedicationHistoryDomainError("移行記録に確定監査値は設定できません。")

    def _ensure_counseling_provenance_is_valid(self) -> None:
        """指導薬剤師・指導日時の組み合わせや、下書き作成元の整合性を検証する。"""
        facts = self.effective_facts
        has_counselor = facts.counselor_id is not None
        has_counseled_at = facts.counseled_at is not None
        if has_counselor != has_counseled_at:
            raise MedicationHistoryDomainError(
                "指導者と指導日時は両方設定するか、両方未設定にしてください。"
            )
        if has_counselor:
            return
        if self.status is not MedicationHistoryStatus.DRAFT or (
            self.recorded_by is None
            and (
                facts.source_system != MedicationHistorySourceSystem("NSIPS")
                or self.imported_at is None
            )
        ):
            raise MedicationHistoryDomainError(
                "指導実績のない下書きには薬剤師の記載者またはNSIPS取込時刻が必要です。"
            )

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    @property
    def is_finalized(self) -> bool:
        """薬歴が確定済み（調剤録・指導記録として正式完了した状態）かどうかを判定する。"""
        return self.status.is_finalized

    @property
    def is_projection_eligible(self) -> bool:
        """頭書き（アレルギー・副作用・既往歴・併用薬）に反映可能な記録（確定済みまたは移行記録）かを判定する。"""
        return self.status in {
            MedicationHistoryStatus.FINALIZED,
            MedicationHistoryStatus.LEGACY_RECORDED,
        }

    @property
    def effective_soap(self) -> SoapRecord:
        """現時点で有効な最新のSOAP記録を取得する。

        確定後に追記・訂正がある場合は最新の追記内容を返します。
        調剤録・薬歴の真正性を保つため、初回確定時の記載内容はそのまま保持されます。
        """
        if not self.amendments:
            return self.soap
        return self.amendments[-1].amended_soap

    @property
    def updates_profile(self) -> bool:
        """この服薬指導で患者のアレルギー・副作用・既往歴・併用薬などの頭書き更新があるかを判定する。"""
        return not self.effective_facts.profile_updates.is_empty

    def _original_fact_elements(self) -> dict[str, list[FactElement]]:
        """薬歴IDと配列内の位置をもとに、要素ごとの一意で安定したIDを割り当てる。"""
        result: dict[str, list[FactElement]] = {}
        for field_name in FACT_ARRAY_TYPES:
            if field_name.startswith("profile_updates."):
                values = getattr(self.profile_updates, field_name.split(".", 1)[1])
            else:
                values = getattr(self, field_name)
            result[field_name] = [
                FactElement(
                    id=FactRecordId(str(uuid5(self.id.value, f"{field_name}:{index}"))),
                    value=value,
                )
                for index, value in enumerate(values)
            ]
        return result

    def _replay_facts(
        self,
    ) -> tuple[EffectiveMedicationHistoryFacts, dict[str, list[FactElement]]]:
        """訂正履歴を記録順に適用（リプレイ）し、現在の有効な事実データと要素一覧を計算する。"""
        facts = EffectiveMedicationHistoryFacts(
            counselor_id=self.counselor_id,
            counseled_at=self.counseled_at,
            method=self.method,
            handbook_status=self.handbook_status,
            residual_drug=self.residual_drug,
            information_sheet_provided=self.information_sheet_provided,
            profile_updates=self.profile_updates,
            additional_notes=self.additional_notes,
            billing_additions=self.billing_additions,
            source_system=self.source_system,
            delay_reason=self.delay_reason,
            review_result=self.review_result,
        )
        elements = self._original_fact_elements()
        for correction in self.fact_corrections:
            field_name = correction.field_name.value
            if field_name in FACT_ARRAY_TYPES:
                items = elements[field_name]
                if correction.operation == "append":
                    if correction.element_id is None or correction.after is None:
                        raise MedicationHistoryDomainError(
                            "追加要素のIDと値が必要です。"
                        )
                    items.append(
                        FactElement(
                            id=FactRecordId(correction.element_id.value),
                            value=cast(FactArrayValue, correction.after),
                        )
                    )
                else:
                    position = next(
                        (
                            index
                            for index, item in enumerate(items)
                            if item.id.value == correction.target.value
                        ),
                        None,
                    )
                    if position is None:
                        raise MedicationHistoryDomainError(
                            "訂正対象の要素がありません。"
                        )
                    if correction.operation == "retract":
                        items.pop(position)
                    elif correction.after is not None:
                        items[position] = FactElement(
                            id=FactRecordId(correction.target.value),
                            value=cast(FactArrayValue, correction.after),
                        )
            elif field_name.startswith("profile_updates."):
                facts = replace(
                    facts,
                    profile_updates=_replace_fact_field(
                        facts.profile_updates,
                        field_name.split(".", 1)[1],
                        correction.after,
                    ),
                )
            else:
                facts = _replace_fact_field(facts, field_name, correction.after)
        profile_updates = facts.profile_updates
        for field_name, items in elements.items():
            values = tuple(item.value for item in items)
            if field_name.startswith("profile_updates."):
                profile_updates = _replace_fact_field(
                    profile_updates, field_name.split(".", 1)[1], values
                )
            else:
                facts = _replace_fact_field(facts, field_name, values)
        return replace(facts, profile_updates=profile_updates), elements

    @property
    def effective_facts(self) -> EffectiveMedicationHistoryFacts:
        """訂正履歴を適用した最新の有効な事実データを取得する（原本はそのまま保持されます）。"""
        return self._replay_facts()[0]

    def fact_elements(self, field_name: str) -> tuple[FactElement, ...]:
        """指定した配列項目の有効な要素一覧をID付きで取得する。"""
        if field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("指定した項目は配列ではありません。")
        return tuple(self._replay_facts()[1][field_name])

    def original_fact_elements(self, field_name: str) -> tuple[FactElement, ...]:
        """原本データにおける指定配列項目の要素一覧を取得する。"""
        if field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("指定した項目は配列ではありません。")
        return tuple(self._original_fact_elements()[field_name])

    def _ensure_fact_corrections_are_valid(self) -> None:
        """事実訂正履歴の不整合（ID重複や未確定記録への訂正など）がないかを検証する。"""
        if self.fact_corrections and not self.is_projection_eligible:
            raise MedicationHistoryNotFinalizedError()
        ids = [item.id.value for item in self.fact_corrections]
        if len(ids) != len(set(ids)):
            raise MedicationHistoryDomainError("薬歴訂正IDが重複しています。")
        if self.status is MedicationHistoryStatus.FINALIZED and any(
            item.field_name == "review_result" and item.after is None
            for item in self.fact_corrections
        ):
            raise MedicationHistoryDomainError("レビュー結果は訂正で解除できません。")
        self._replay_facts()

    def correct_fact(
        self,
        *,
        target: str,
        operation: str = "replace",
        reason: str,
        corrected_by: StaffId,
        recorded_at: datetime,
        value: object = _FACT_VALUE_ABSENT,
    ) -> Self:
        """確定済みまたは移行済みの薬歴に対して、事実情報の訂正を監査情報付きで記録する。"""
        if not self.is_projection_eligible:
            raise MedicationHistoryNotFinalizedError()
        if not reason.strip():
            raise MedicationHistoryDomainError("訂正理由を入力してください。")
        if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
            raise MedicationHistoryDomainError("訂正日時にはタイムゾーンが必要です。")
        if operation not in {"replace", "retract", "append"}:
            raise MedicationHistoryDomainError("訂正操作が正しくありません。")
        facts, elements = self._replay_facts()
        field_name = target
        if target not in FACT_FIELD_TYPES and target not in FACT_ARRAY_TYPES:
            field_name = next(
                (
                    name
                    for name, items in elements.items()
                    if any(item.id.value == target for item in items)
                ),
                "",
            )
        if field_name not in FACT_FIELD_TYPES and field_name not in FACT_ARRAY_TYPES:
            raise MedicationHistoryDomainError("訂正対象がありません。")
        is_array = field_name in FACT_ARRAY_TYPES
        if operation == "append" and (not is_array or target != field_name):
            raise MedicationHistoryDomainError("配列への追加対象が正しくありません。")
        if operation != "append" and is_array and target == field_name:
            raise MedicationHistoryDomainError("配列要素のIDを指定してください。")
        if operation == "retract":
            if value is not _FACT_VALUE_ABSENT:
                raise MedicationHistoryDomainError("取消しに新しい値は指定できません。")
            after: object | None = None
        else:
            if value is _FACT_VALUE_ABSENT:
                raise MedicationHistoryDomainError("訂正後の値を指定してください。")
            expected = (FACT_ARRAY_TYPES if is_array else FACT_FIELD_TYPES)[field_name]
            if value is not None and (
                type(value) is not bool
                if expected is bool
                else not isinstance(value, expected)
            ):
                raise MedicationHistoryDomainError("訂正値の型が対象項目と異なります。")
            if is_array and value is None:
                raise MedicationHistoryDomainError("配列に空の要素は追加できません。")
            after = value
        if is_array:
            before = next(
                (
                    item.value
                    for item in elements[field_name]
                    if item.id.value == target
                ),
                None,
            )
            if operation != "append" and before is None:
                raise MedicationHistoryDomainError("訂正対象の要素がありません。")
        elif field_name.startswith("profile_updates."):
            before = getattr(facts.profile_updates, field_name.split(".", 1)[1])
        else:
            before = getattr(facts, field_name)
        if operation == "retract" and not is_array and before is None:
            raise MedicationHistoryDomainError("取消し対象の値がありません。")
        event = MedicationHistoryFactCorrection(
            id=FactRecordId(str(uuid7())),
            target=FactTarget(target),
            field_name=FactFieldName(field_name),
            operation=FactCorrectionOperation(operation),
            before=cast(FactValue | None, before),
            after=cast(FactValue | None, after),
            reason=FactCorrectionReason(reason.strip()),
            corrected_by=corrected_by,
            recorded_at=FactCorrectionTimestamp(recorded_at),
            element_id=(FactRecordId(str(uuid7())) if operation == "append" else None),
        )
        return replace(self, fact_corrections=(*self.fact_corrections, event))

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        *,
        event_id: EventId,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        dispensing_id: DispensingId | None,
        prescription_id: PrescriptionId | None,
        counselor_id: StaffId | None,
        counseled_at: CounselingTimestamp | None,
        method: CounselingMethod | None,
        soap: SoapRecord,
        handbook_status: HandbookStatus | None,
        residual_drug: ResidualDrugRecord | None,
        information_sheet_provided: bool | None = None,
        profile_updates: ProfileUpdateIntents | None = None,
        additional_notes: tuple[CategorizedNote, ...] = (),
        billing_additions: tuple[BillingAddition, ...] = (),
        source_system: MedicationHistorySourceSystem | None = None,
        imported_at: MedicationHistoryImportTimestamp | None = None,
        recorded_by: StaffId | None = None,
        recorded_at: MedicationHistoryRecordedTimestamp | None = None,
    ) -> Self:
        """服薬指導記録を下書き（DRAFT）として新規作成する。"""
        return cls(
            id=MedicationHistoryRecordId.generate(),
            event_id=event_id,
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            method=method,
            soap=soap,
            handbook_status=handbook_status,
            residual_drug=residual_drug,
            information_sheet_provided=information_sheet_provided,
            profile_updates=(
                profile_updates
                if profile_updates is not None
                else ProfileUpdateIntents()
            ),
            additional_notes=additional_notes,
            billing_additions=billing_additions,
            source_system=source_system,
            imported_at=imported_at,
            recorded_by=recorded_by,
            recorded_at=recorded_at,
            status=MedicationHistoryStatus.DRAFT,
        )

    # ------------------------------------------------------------------
    # 編集と確定
    # ------------------------------------------------------------------

    def update_draft_soap(self, soap: SoapRecord) -> Self:
        """下書き状態のSOAP内容を更新する。

        確定済みの薬歴は直接変更できません（確定後の修正は amend による追記のみ）。
        """
        self._ensure_not_finalized()
        return replace(self, soap=soap)

    def update_draft_profile_updates(self, intents: ProfileUpdateIntents) -> Self:
        """下書き状態の患者頭書き更新差分を更新する。"""
        self._ensure_not_finalized()
        return replace(self, profile_updates=intents)

    def update_draft(
        self,
        *,
        method: CounselingMethod | None = None,
        soap: SoapRecord | None = None,
        handbook_status: HandbookStatus | None = None,
        residual_drug: ResidualDrugRecord | None = None,
        information_sheet_provided: bool | None = None,
        profile_updates: ProfileUpdateIntents | None = None,
        additional_notes: tuple[CategorizedNote, ...] | None = None,
        billing_additions: tuple[BillingAddition, ...] | None = None,
    ) -> Self:
        """下書き状態の各項目を一括更新する。

        確定済みの薬歴は直接変更できません（確定後の修正は amend による追記のみ）。
        """
        self._ensure_not_finalized()
        return replace(
            self,
            method=method if method is not None else self.method,
            soap=soap if soap is not None else self.soap,
            handbook_status=handbook_status
            if handbook_status is not None
            else self.handbook_status,
            residual_drug=residual_drug
            if residual_drug is not None
            else self.residual_drug,
            information_sheet_provided=information_sheet_provided
            if information_sheet_provided is not None
            else self.information_sheet_provided,
            profile_updates=profile_updates
            if profile_updates is not None
            else self.profile_updates,
            additional_notes=additional_notes
            if additional_notes is not None
            else self.additional_notes,
            billing_additions=billing_additions
            if billing_additions is not None
            else self.billing_additions,
        )

    def finalize(
        self,
        *,
        counselor_id: StaffId | None = None,
        counseled_at: CounselingTimestamp | None = None,
        finalized_at: FinalizedTimestamp | None = None,
        finalized_by: StaffId | None = None,
        delay_reason: FinalizationDelayReason | None = None,
        review_result: MedicationHistoryReviewResult | None = None,
    ) -> Self:
        """薬歴を確定する。

        確定日時および確定者は呼び出し元から明示的に指定する必要があります（指導日時や指導者から自動推測しません）。
        外部取込による下書きの場合は、実際の指導者および指導日時の指定も必須です。
        """
        self._ensure_not_finalized()
        if finalized_at is None or finalized_by is None:
            raise FinalizationStaffRequiredError()
        if review_result is None:
            raise MedicationHistoryDomainError(
                "薬歴確定時のレビュー結果を指定してください。"
            )
        supplied_counselor = counselor_id is not None
        supplied_counseled_at = counseled_at is not None
        if supplied_counselor != supplied_counseled_at:
            raise MedicationHistoryDomainError(
                "指導者と指導日時は両方指定してください。"
            )
        actual_counselor_id: StaffId | None = self.counselor_id
        actual_counseled_at: CounselingTimestamp | None = self.counseled_at
        if supplied_counselor:
            if counselor_id is None or counseled_at is None:
                raise MedicationHistoryDomainError(
                    "指導者と指導日時は両方指定してください。"
                )
            if (
                self.counselor_id is not None and self.counselor_id != counselor_id
            ) or (self.counseled_at is not None and self.counseled_at != counseled_at):
                raise MedicationHistoryDomainError(
                    "記録済みの指導者または指導日時は確定時に変更できません。"
                )
            actual_counselor_id = counselor_id
            actual_counseled_at = counseled_at
        if actual_counselor_id is None or actual_counseled_at is None:
            raise MedicationHistoryDomainError(
                "薬歴を確定するには実際の指導者と指導日時が必要です。"
            )
        with_counseling = replace(
            self,
            counselor_id=actual_counselor_id,
            counseled_at=actual_counseled_at,
        )
        return replace(
            with_counseling,
            status=MedicationHistoryStatus.FINALIZED,
            finalized_at=finalized_at,
            finalized_by=finalized_by,
            delay_reason=delay_reason,
            review_result=review_result,
        )

    def amend(
        self,
        *,
        amended_soap: SoapRecord,
        reason: AmendmentReason,
        amended_by: StaffId,
        amended_at: AmendmentTimestamp,
        amendment_id: str | None = None,
    ) -> Self:
        """確定済の薬歴に対して修正内容を追記する。

        過去の記録の改ざんを防ぎ真正性を保つため、元の ``soap`` を直接上書きせず、
        追記履歴として保存します。

        Raises:
            MedicationHistoryNotFinalizedError: 未確定（下書き）の薬歴の場合。
            SoapContentRequiredError: 追記後の実効SOAPが白紙になる場合。
        """
        # 確定済みでなければ追記できない
        if not self.is_finalized:
            raise MedicationHistoryNotFinalizedError()
        effective_amendment_id = amendment_id or str(uuid7())
        amendment = MedicationHistoryAmendment(
            amended_soap=amended_soap,
            reason=reason,
            amended_by=amended_by,
            amended_at=amended_at,
            amendment_id=(AmendmentId(effective_amendment_id)),
        )
        return replace(self, amendments=(*self.amendments, amendment))

    def _ensure_not_finalized(self) -> None:
        """確定済でないことを保証する。"""
        if self.status is not MedicationHistoryStatus.DRAFT:
            raise MedicationHistoryAlreadyFinalizedError()

    def add_tracing_report(self, report: TracingReport) -> Self:
        """確定済の薬歴に処方医へのトレーシングレポート提供記録を追加する。

        Raises:
            TracingReportOnDraftError: 薬歴が未確定（下書き）の場合。
            TracingReportDateBeforeCounselingError: 初回指導日時より前の提供日時の場合。
            DuplicatedTracingReportIdError: 同一のレポートIDが既に存在する場合。
        """
        if not self.is_finalized:
            raise TracingReportOnDraftError()
        if self.counseled_at is None:
            raise MedicationHistoryDomainError("確定済の薬歴に指導日時がありません。")
        if report.provided_at.value < self.counseled_at.value:
            raise TracingReportDateBeforeCounselingError()
        if any(existing.id == report.id for existing in self.tracing_reports):
            raise DuplicatedTracingReportIdError()
        return replace(self, tracing_reports=(*self.tracing_reports, report))

    def record_tracing_report_response(
        self,
        tracing_report_id: TracingReportId,
        response: TracingReportResponse,
    ) -> Self:
        """トレーシングレポートに対する処方医からの返答を記録する。

        Raises:
            TracingReportNotFoundError: 指定されたレポートIDが存在しない場合。
            TracingReportAlreadyRespondedError: 既に返答が記録されている場合。
            TracingReportResponseDateBeforeProvidedError: 提供日時より前の返答日時の場合。
        """
        report = next(
            (r for r in self.tracing_reports if r.id == tracing_report_id), None
        )
        if report is None:
            raise TracingReportNotFoundError()
        if report.response is not None:
            raise TracingReportAlreadyRespondedError()
        if response.responded_at.value < report.provided_at.value:
            raise TracingReportResponseDateBeforeProvidedError()
        updated_report = replace(report, response=response)
        updated_reports = tuple(
            updated_report if r.id == tracing_report_id else r
            for r in self.tracing_reports
        )
        return replace(self, tracing_reports=updated_reports)

    @property
    def has_pending_correction_review(self) -> bool:
        """確認待ちまたは調査中の外部処方訂正が存在するかを判定する。"""
        return any(
            correction.status is not ExternalCorrectionStatus.RESOLVED
            and not correction.is_acknowledged
            for correction in self.external_corrections
        )

    def record_external_correction(
        self, correction: ExternalPrescriptionCorrection
    ) -> Self:
        """確定済みの薬歴を改変せず、外部システム（レセコン等）から届いた処方訂正を追記する。

        確定済み薬歴の原本（SOAP・確定情報）は真正性を保つため凍結し、
        外部で発生した処方変更・調剤訂正の事実を追記履歴として管理します。
        """
        existing = next(
            (
                item
                for item in self.external_corrections
                if item.correction_id.value == correction.correction_id.value
            ),
            None,
        )
        if existing is not None:
            if (
                existing.kind == correction.kind
                and existing.source_document_number.value
                == correction.source_document_number.value
                and existing.reason.value == correction.reason.value
                and (existing.details.value if existing.details is not None else None)
                == (
                    correction.details.value if correction.details is not None else None
                )
            ):
                return self
            raise MedicationHistoryDomainError(
                "同一の外部訂正IDに異なる訂正内容を登録できません。"
            )
        return replace(
            self, external_corrections=(*self.external_corrections, correction)
        )

    def acknowledge_external_correction(
        self,
        *,
        correction_id: str,
        acknowledged_by: StaffId,
        acknowledged_at: ExternalCorrectionTimestamp,
    ) -> Self:
        """外部処方訂正の内容を薬剤師が確認・了解したことを記録する。"""
        target = next(
            (
                c
                for c in self.external_corrections
                if c.correction_id.value == correction_id
            ),
            None,
        )
        if target is None:
            raise MedicationHistoryDomainError("指定された外部訂正IDが存在しません。")
        updated_correction = replace(
            target,
            acknowledged_by=acknowledged_by,
            acknowledged_at=acknowledged_at,
            status=ExternalCorrectionStatus.RESOLVED,
        )
        updated_corrections = tuple(
            updated_correction if c.correction_id.value == correction_id else c
            for c in self.external_corrections
        )
        return replace(self, external_corrections=updated_corrections)

    def review_external_correction(
        self,
        *,
        correction_id: str,
        decision: ExternalCorrectionDecision,
        reason: str,
        reviewed_by: StaffId,
        reviewed_at: ExternalCorrectionTimestamp,
        amended_soap: SoapRecord | None = None,
        matched_prescription_id: PrescriptionId | None = None,
    ) -> Self:
        """外部処方訂正に対する薬剤師の対応判断（追記修正・再登録処方との照合等）を履歴に記録する。"""
        if not self.is_finalized and decision not in (
            ExternalCorrectionDecision.NO_ACTION,
            ExternalCorrectionDecision.INVESTIGATING,
        ):
            raise MedicationHistoryNotFinalizedError()
        target = next(
            (
                item
                for item in self.external_corrections
                if item.correction_id.value == correction_id
            ),
            None,
        )
        if target is None:
            raise MedicationHistoryDomainError("指定された外部訂正IDが存在しません。")
        if target.status is ExternalCorrectionStatus.RESOLVED or target.is_acknowledged:
            raise MedicationHistoryDomainError("解決済みの外部訂正は再判断できません。")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise MedicationHistoryDomainError("外部訂正の判断理由は必須です。")

        amendment_id: str | None = None
        if decision is ExternalCorrectionDecision.AMEND:
            if amended_soap is None:
                raise MedicationHistoryDomainError("追記するSOAPを指定してください。")
            amendment_id = str(uuid7())
            updated = self.amend(
                amended_soap=amended_soap,
                reason=AmendmentReason(normalized_reason),
                amended_by=reviewed_by,
                amended_at=AmendmentTimestamp(reviewed_at.value),
                amendment_id=amendment_id,
            )
        else:
            updated = self
        if (
            decision is ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
            and matched_prescription_id is None
        ):
            raise MedicationHistoryDomainError("照合先の処方IDを指定してください。")
        if (
            decision is not ExternalCorrectionDecision.MATCH_REREGISTERED_PRESCRIPTION
            and matched_prescription_id is not None
        ):
            raise MedicationHistoryDomainError(
                "照合先の処方IDは照合判断の場合だけ指定できます。"
            )

        is_final_decision = decision is not ExternalCorrectionDecision.INVESTIGATING
        event = ExternalCorrectionReviewEvent(
            decision=decision,
            reason=ExternalCorrectionReason(normalized_reason),
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            amendment_id=(
                AmendmentId(amendment_id) if amendment_id is not None else None
            ),
            matched_prescription_id=matched_prescription_id,
        )
        updated_target = replace(
            target,
            status=(
                ExternalCorrectionStatus.RESOLVED
                if is_final_decision
                else ExternalCorrectionStatus.INVESTIGATING
            ),
            review_events=(*target.review_events, event),
            acknowledged_by=reviewed_by
            if is_final_decision
            else target.acknowledged_by,
            acknowledged_at=reviewed_at
            if is_final_decision
            else target.acknowledged_at,
        )
        updated_corrections = tuple(
            updated_target if item.correction_id.value == correction_id else item
            for item in updated.external_corrections
        )
        return replace(updated, external_corrections=updated_corrections)

    def calculate_and_set_retention_expiry(
        self,
        obligation: PreservationObligation,
        *additional_obligations: PreservationObligation,
        last_written_on: date,
    ) -> Self:
        """法定保存期間ポリシーに基づき、薬歴の保存期限日を計算して設定する。

        複数の保存義務が指定されている場合は最も遅い満了日を採用し、
        既存の満了日がある場合は短縮されないよう最新の日付を維持します。
        """
        expiry_date = resolve_latest_retention_expiry_date(
            last_written_on,
            PreservationRecordKind.MEDICATION_HISTORY,
            obligation,
            *additional_obligations,
        )
        if self.retention_expiry_date is not None:
            expiry_date = latest_retention_expiry_date(
                self.retention_expiry_date, expiry_date
            )
        return replace(self, retention_expiry_date=expiry_date)
