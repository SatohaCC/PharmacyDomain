"""頭書き（患者医療プロファイル）をApplication DTOへ変換して取得・再構築する処理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.exceptions import (
    PatientMedicalProfileNotFoundError,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    AdverseReactionRecord,
    AllergyRecord,
    ConcurrentMedicationRecord,
    FamilyPharmacistAgreement,
    GenericPreference,
    LifestyleProfile,
    MedicalConditionRecord,
    MedicationHistoryRepository,
    PatientMedicalProfile,
    PatientMedicalProfileRepository,
    ProfileProvenance,
)
from app.domain.patient.primitives import PatientId


@dataclass(frozen=True, kw_only=True)
class ProvenanceDto:
    """頭書き要素の由来の出力DTO。"""

    source_record_id: str
    recorded_by: str
    recorded_on: str

    @classmethod
    def from_value(cls, value: ProfileProvenance) -> ProvenanceDto:
        """由来からDTOを生成する。"""
        return cls(
            source_record_id=str(value.source_record_id.value),
            recorded_by=str(value.recorded_by.value),
            recorded_on=value.recorded_on.isoformat(),
        )


@dataclass(frozen=True, kw_only=True)
class AllergyDto:
    """アレルギー歴の出力DTO。"""

    allergen: str
    reaction: str
    severity: str
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: AllergyRecord) -> AllergyDto:
        """アレルギー歴からDTOを生成する。"""
        return cls(
            allergen=value.allergen.value,
            reaction=value.reaction.value,
            severity=value.severity.value,
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class AdverseReactionDto:
    """副作用歴の出力DTO。"""

    medicine_name: str
    symptom: str
    occurred_on: str | None
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: AdverseReactionRecord) -> AdverseReactionDto:
        """副作用歴からDTOを生成する。"""
        return cls(
            medicine_name=value.medicine_name.value,
            symptom=value.symptom.value,
            occurred_on=(
                value.occurred_on.isoformat() if value.occurred_on is not None else None
            ),
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class MedicalConditionDto:
    """疾患の出力DTO。"""

    condition_name: str
    condition_status: str
    is_contraindication_target: bool
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: MedicalConditionRecord) -> MedicalConditionDto:
        """疾患からDTOを生成する。"""
        return cls(
            condition_name=value.condition_name.value,
            condition_status=value.condition_status.value,
            is_contraindication_target=value.is_contraindication_target,
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class ConcurrentMedicationDto:
    """併用薬の出力DTO。

    ``is_active`` は返さない。継続中かどうかは適用日ごとに決まるので、
    DTOへ焼き付けると受け取り側が古い判定を持ち回ることになる。
    """

    medicine_name: str
    category: str
    started_on: str
    ended_on: str | None
    prescriber_institution: str | None
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: ConcurrentMedicationRecord) -> ConcurrentMedicationDto:
        """併用薬からDTOを生成する。"""
        return cls(
            medicine_name=value.medicine_name.value,
            category=value.category.value,
            started_on=value.started_on.isoformat(),
            ended_on=(
                value.ended_on.isoformat() if value.ended_on is not None else None
            ),
            prescriber_institution=(
                value.prescriber_institution.value
                if value.prescriber_institution is not None
                else None
            ),
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class LifestyleDto:
    """生活像の出力DTO。"""

    note: str
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: LifestyleProfile) -> LifestyleDto:
        """生活像からDTOを生成する。"""
        return cls(
            note=value.note.value,
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class GenericPreferenceDto:
    """後発医薬品への意向の出力DTO。"""

    preference: str
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: GenericPreference) -> GenericPreferenceDto:
        """意向からDTOを生成する。"""
        return cls(
            preference=value.preference.value,
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class FamilyPharmacistDto:
    """かかりつけ薬剤師の出力DTO。"""

    pharmacist_id: str
    agreed_on: str
    provenance: ProvenanceDto

    @classmethod
    def from_value(cls, value: FamilyPharmacistAgreement) -> FamilyPharmacistDto:
        """かかりつけ薬剤師の同意からDTOを生成する。"""
        return cls(
            pharmacist_id=str(value.pharmacist_id.value),
            agreed_on=value.agreed_on.isoformat(),
            provenance=ProvenanceDto.from_value(value.provenance),
        )


@dataclass(frozen=True, kw_only=True)
class PatientMedicalProfileDto:
    """頭書きの出力DTO。"""

    id: str
    corporate_id: str
    patient_id: str
    allergies: tuple[AllergyDto, ...]
    adverse_reactions: tuple[AdverseReactionDto, ...]
    medical_conditions: tuple[MedicalConditionDto, ...]
    concurrent_medications: tuple[ConcurrentMedicationDto, ...]
    #: 適用日を指定して抽出した、その日に併用していた薬。
    active_concurrent_medications: tuple[ConcurrentMedicationDto, ...]
    lifestyle: LifestyleDto | None
    generic_preference: GenericPreferenceDto | None
    family_pharmacist: FamilyPharmacistDto | None

    @classmethod
    def from_entity(
        cls, profile: PatientMedicalProfile, *, as_of: date
    ) -> PatientMedicalProfileDto:
        """頭書き集約からDTOを生成する。

        併用中かどうかは適用日で決まるため、判定日を引数で受け取る。
        ``date.today()`` を暗黙に使わない（ruff ``DTZ011``）。
        """
        return cls(
            id=str(profile.id.value),
            corporate_id=str(profile.corporate_id.value),
            patient_id=str(profile.patient_id.value),
            allergies=tuple(AllergyDto.from_value(item) for item in profile.allergies),
            adverse_reactions=tuple(
                AdverseReactionDto.from_value(item)
                for item in profile.adverse_reactions
            ),
            medical_conditions=tuple(
                MedicalConditionDto.from_value(item)
                for item in profile.medical_conditions
            ),
            concurrent_medications=tuple(
                ConcurrentMedicationDto.from_value(item)
                for item in profile.concurrent_medications
            ),
            active_concurrent_medications=tuple(
                ConcurrentMedicationDto.from_value(item)
                for item in profile.active_concurrent_medications(as_of)
            ),
            lifestyle=(
                LifestyleDto.from_value(profile.lifestyle)
                if profile.lifestyle is not None
                else None
            ),
            generic_preference=(
                GenericPreferenceDto.from_value(profile.generic_preference)
                if profile.generic_preference is not None
                else None
            ),
            family_pharmacist=(
                FamilyPharmacistDto.from_value(profile.family_pharmacist)
                if profile.family_pharmacist is not None
                else None
            ),
        )


@dataclass(frozen=True, kw_only=True)
class GetPatientMedicalProfileQuery:
    """頭書き取得の入力データ。"""

    corporate_id: str
    patient_id: str
    #: 併用薬の継続判定に使う適用日。
    as_of: date


class GetPatientMedicalProfileUseCase:
    """法人境界を確認して頭書きを取得する。"""

    def __init__(
        self,
        repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, query: GetPatientMedicalProfileQuery
    ) -> PatientMedicalProfileDto:
        """指定法人・患者の頭書きをDTOで返す。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        profile = await self._repository.get_by_patient(
            corporate_id=corporate_id,
            patient_id=PatientId.parse(query.patient_id),
        )
        if profile is None:
            raise PatientMedicalProfileNotFoundError()
        return PatientMedicalProfileDto.from_entity(profile, as_of=query.as_of)


@dataclass(frozen=True, kw_only=True)
class RebuildPatientMedicalProfileCommand:
    """頭書き再構築の入力データ。"""

    corporate_id: str
    patient_id: str
    as_of: date


class RebuildPatientMedicalProfileUseCase:
    """確定済薬歴から頭書きを作り直す。

    薬歴の保存は成功したが頭書きの保存が失敗した場合の**回復手段**である。
    頭書きは投影なので、
    真である薬歴を畳み込めば必ず正しい状態へ戻せる。

    既存の頭書きがあれば、その同一性（``id``）を保ったまま中身を差し替える。
    新しい ``id`` で作り直すと、患者ごと1件の一意制約に引っかかる。
    """

    def __init__(
        self,
        record_repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: RebuildPatientMedicalProfileCommand
    ) -> PatientMedicalProfileDto:
        """薬歴を畳み込んで頭書きを保存し直す。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        patient_id = PatientId.parse(command.patient_id)
        records = await self._record_repository.list_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )
        rebuilt = PatientMedicalProfile.rebuild_from(
            corporate_id=corporate_id,
            patient_id=patient_id,
            records=tuple(record for record in records if record.is_finalized),
        )
        existing = await self._profile_repository.get_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )
        if existing is not None:
            rebuilt = _with_id_of(rebuilt, existing)
        await self._profile_repository.save(rebuilt)
        return PatientMedicalProfileDto.from_entity(rebuilt, as_of=command.as_of)


def _with_id_of(
    rebuilt: PatientMedicalProfile, existing: PatientMedicalProfile
) -> PatientMedicalProfile:
    """再構築した頭書きに、既存の同一性を引き継がせる。"""
    return PatientMedicalProfile(
        id=existing.id,
        corporate_id=rebuilt.corporate_id,
        patient_id=rebuilt.patient_id,
        allergies=rebuilt.allergies,
        adverse_reactions=rebuilt.adverse_reactions,
        medical_conditions=rebuilt.medical_conditions,
        concurrent_medications=rebuilt.concurrent_medications,
        lifestyle=rebuilt.lifestyle,
        generic_preference=rebuilt.generic_preference,
        family_pharmacist=rebuilt.family_pharmacist,
    )
