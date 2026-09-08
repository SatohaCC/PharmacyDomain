"""患者集約の PostgreSQL Repository。

患者番号の採番表もここで扱う。採番は患者の登録と同じトランザクションで進める
必要があり、別の集約として切り出しても意味を持たない。
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as postgres_insert

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientId, PatientNumber
from app.domain.patient.repository import PatientRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import patient_number_sequences, patients


def _patient_columns(patient: Patient) -> dict[str, object]:
    """検索・一意性制約に使う列を患者から導く。"""
    return {
        "id": patient.id.value,
        "corporate_id": patient.corporate_id.value,
        "patient_number": patient.patient_number.value,
    }


PATIENT_MAPPING = AggregateMapping(
    table=patients,
    aggregate_type=Patient,
    label="患者",
    search_columns=_patient_columns,
)


class PostgresPatientRepository(PostgresRepositoryBase, PatientRepository):
    """患者集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> Patient | None:
        """法人境界を含めてIDで患者を検索する。"""
        return await self.get_by_id(
            PATIENT_MAPPING, patient_id, corporate_id=corporate_id
        )

    async def save(self, patient: Patient) -> None:
        """患者を保存する。"""
        await self.save_with_conflict_map(PATIENT_MAPPING, patient)

    async def allocate_patient_number(
        self,
        corporate_id: CorporateId,
    ) -> PatientNumber:
        """法人ごとの採番表を1文で進めて患者番号を得る。

        読んでから書くと、同時受付で同じ番号が2人に渡る。``ON CONFLICT DO
        UPDATE ... RETURNING`` なら採番と加算が1文で閉じる。

        トランザクションを巻き戻すと番号は戻るが、巻き戻った番号は患者へ
        割り当てられていないので「一度使った番号を再利用しない」契約は保たれる。
        """
        statement = (
            postgres_insert(patient_number_sequences)
            .values(corporate_id=corporate_id.value, last_number=1)
            .on_conflict_do_update(
                index_elements=[patient_number_sequences.c.corporate_id],
                set_={
                    "last_number": patient_number_sequences.c.last_number + 1,
                },
            )
            .returning(patient_number_sequences.c.last_number)
        )
        result = await self.session.execute(statement)
        return PatientNumber(int(result.scalar_one()))
