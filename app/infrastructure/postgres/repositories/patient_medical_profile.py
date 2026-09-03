"""頭書き（薬歴からの投影）の PostgreSQL Repository。

患者ごとに1件だけ存在する投影なので、IDではなく患者で引く。投影元の薬歴と
同じ UnitOfWork で確定させる前提であり、失敗しても薬歴から作り直せる。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.repository import PatientMedicalProfileRepository
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    constraint_name,
)
from app.infrastructure.postgres.schema import patient_medical_profiles


def _medical_profile_columns(profile: PatientMedicalProfile) -> dict[str, object]:
    """検索・一意性制約に使う列を頭書きから導く。"""
    return {
        "id": profile.id.value,
        "corporate_id": profile.corporate_id.value,
        "patient_id": profile.patient_id.value,
    }


PATIENT_MEDICAL_PROFILE_MAPPING = AggregateMapping(
    table=patient_medical_profiles,
    aggregate_type=PatientMedicalProfile,
    label="頭書き",
    search_columns=_medical_profile_columns,
)


class PostgresPatientMedicalProfileRepository(
    PostgresRepositoryBase, PatientMedicalProfileRepository
):
    """患者医療プロファイル（頭書き）を PostgreSQL へ保存・検索する。"""

    async def get_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile | None:
        """患者の頭書きを取得する。``None`` は「まだ投影されていない」。"""
        return await self.find_one(
            PATIENT_MEDICAL_PROFILE_MAPPING,
            select(patient_medical_profiles).where(
                patient_medical_profiles.c.corporate_id == corporate_id.value,
                patient_medical_profiles.c.patient_id == patient_id.value,
            ),
        )

    async def save(self, profile: PatientMedicalProfile) -> None:
        """患者ごとに1件であることを原子的に保証して保存する。"""
        try:
            await self.save_aggregate(PATIENT_MEDICAL_PROFILE_MAPPING, profile)
        except IntegrityError as error:
            if constraint_name(error) == "uq_patient_medical_profiles_patient":
                raise PatientMedicalProfileAlreadyExistsError() from error
            raise
