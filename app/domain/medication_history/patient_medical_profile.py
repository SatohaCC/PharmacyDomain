"""患者医療プロファイル（頭書き）集約。

**薬歴からの投影であり、独立した真実を持たない。** その患者の確定済薬歴を
``counseled_at`` 昇順に畳み込めば決定的に再構築できる。

そのため**唯一の状態変更メソッドは :meth:`apply` である**。項目ごとの
``register_allergy(...)`` のような直接編集を公開しない。公開すると、薬歴に
由来しない要素を作れてしまい、再構築が不可能になる。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.base.domain.medicine import MedicineName
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    ConcurrentMedicationNotFoundError,
    ProfilePatientMismatchError,
    UnfinalizedRecordProjectionError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import PatientMedicalProfileId
from app.domain.medication_history.value_objects import (
    AdverseReactionRecord,
    AllergyRecord,
    ConcurrentMedicationRecord,
    FamilyPharmacistAgreement,
    GenericPreference,
    LifestyleProfile,
    MedicalConditionRecord,
    ProfileProvenance,
)
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, eq=False, kw_only=True)
class PatientMedicalProfile(AggregateRoot[PatientMedicalProfileId]):
    """患者の継続的医療プロファイル（頭書き / フェイスシート）。

    ライフサイクルのフィールドを持たない。頭書きは投影なので「無効化」という
    状態が無く、要素の終了は各要素の期間（併用薬の ``ended_on``）で表す。
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
        """指定日に併用していた薬の一覧を返す。

        適用日を引数で受け取る全域関数にする。``date.today()`` の暗黙利用は
        ruff ``DTZ011`` が禁じており、遡及判定は相互作用チェックで実際に要る。
        """
        return tuple(
            item
            for item in self.concurrent_medications
            if item.is_active_on(target_date)
        )

    @property
    def contraindication_conditions(self) -> tuple[MedicalConditionRecord, ...]:
        """禁忌チェックの対象になる疾患。"""
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
        """まだ何も投影されていない頭書きを作る。

        Repository が ``None`` を返すのは欠損ではなく「まだ投影されていない」を
        意味するので、呼び出し側はこれを作ってから畳み込んでよい。
        """
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
        """確定済薬歴の列から頭書きを再構築する。

        ``counseled_at`` 昇順に畳み込む。頭書きは薬歴からの投影なので、
        確定済薬歴が残ってさえいれば同じ状態を作り直せる。保存順序
        ``save(record)`` → ``save(profile)`` の後者が失敗したときの回復手段であり、
        2回の保存を原子的にするものではない（Unit of Work が無いことへの対処）。
        """
        profile = cls.empty_for(corporate_id=corporate_id, patient_id=patient_id)
        for record in sorted(records, key=lambda item: item.counseled_at.value):
            profile = profile.apply(record)
        return profile

    # ------------------------------------------------------------------
    # 投影（唯一の状態変更）
    # ------------------------------------------------------------------

    def apply(self, record: MedicationHistoryRecord) -> Self:
        """確定済薬歴の頭書き差分を適用する。

        由来（``ProfileProvenance``）は薬歴から組み立てる。呼び出し側に
        由来を渡させると、薬歴と食い違う由来を書ける余地ができる。

        Raises:
            ProfilePatientMismatchError: 別の患者・法人の薬歴である場合。
            UnfinalizedRecordProjectionError: 未確定の薬歴である場合。
            ConcurrentMedicationNotFoundError: 終了対象の併用薬が無い場合。
        """
        self._ensure_same_patient(record)
        if not record.is_finalized:
            raise UnfinalizedRecordProjectionError()
        provenance = _provenance_of(record)
        intents = record.profile_updates
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
        for intent in intents.stopped_concurrent_medications:
            updated = updated._close_concurrent_medication(
                intent.medicine_name, intent.ended_on
            )
        return updated

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
    return ProfileProvenance(
        source_record_id=record.id,
        recorded_by=record.counselor_id,
        recorded_on=record.counseled_at.value.date(),
    )
