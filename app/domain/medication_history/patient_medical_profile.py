"""患者医療プロファイル（頭書き / フェイスシート）集約。

本集約は確定済みの薬歴指導記録から導出される投影（プロジェクション）モデルです。
患者の確定済み薬歴を指導日時の古い順に順次適用することで、決定的に再構築できます。

そのため、状態変更の窓口は :meth:`apply` に一元化されており、アレルギーや既往歴を
直接編集するメソッドは提供しません（薬歴に記録されていない臨床情報が紛れ込み、
再構築不能になることを防ぐためです）。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.exceptions import (
    AdverseReactionNotFoundError,
    AllergyNotFoundError,
    ConcurrentMedicationNotFoundError,
    MedicalConditionNotFoundError,
    MedicationHistoryDomainError,
    ProfilePatientMismatchError,
    UnfinalizedRecordProjectionError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    AllergenName,
    ConditionName,
    ConditionStatus,
    PatientMedicalProfileId,
)
from app.domain.medication_history.value_objects import (
    AdverseReactionRecord,
    AllergyRecord,
    ConcurrentMedicationRecord,
    FamilyPharmacistAgreement,
    GenericPreference,
    LifestyleProfile,
    MedicalConditionRecord,
    ProfileProvenance,
    ProfileUpdateIntents,
)
from app.domain.patient.primitives import PatientId
from app.domain.shared.medicine import MedicineName


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
