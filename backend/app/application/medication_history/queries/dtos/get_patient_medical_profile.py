"""Applicationのget_patient_medical_profileを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.common.optional_conversion import unwrap
from app.domain.medication_history.entities import PatientMedicalProfile
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
            occurred_on=value.occurred_on.isoformat()
            if value.occurred_on is not None
            else None,
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
            ended_on=value.ended_on.isoformat() if value.ended_on is not None else None,
            prescriber_institution=unwrap(value.prescriber_institution),
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
            note=value.note.value, provenance=ProvenanceDto.from_value(value.provenance)
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
        ``date.today()`` を暗黙に使わない（環境日時取得のAST検査）。
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
            lifestyle=LifestyleDto.from_value(profile.lifestyle)
            if profile.lifestyle is not None
            else None,
            generic_preference=GenericPreferenceDto.from_value(
                profile.generic_preference
            )
            if profile.generic_preference is not None
            else None,
            family_pharmacist=FamilyPharmacistDto.from_value(profile.family_pharmacist)
            if profile.family_pharmacist is not None
            else None,
        )
