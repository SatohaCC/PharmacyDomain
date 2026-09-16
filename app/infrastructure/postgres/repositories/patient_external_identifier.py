"""患者外部識別子の PostgreSQL Repository。

一意とみなすのは**有効な行だけ**。誤った患者へ紐付けた外部IDを無効化してから
正しい患者へ付け替えられるようにするためで、無効化を終端にすると外部IDが
恒久的に使えなくなる。スタッフコード（無効化後も再利用させない）とは逆向きで、
部分一意インデックスの条件も逆になる。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientExternalIdentifierId,
    PatientId,
)
from app.domain.patient.repository import PatientExternalIdentifierRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import patient_external_identifiers


def _external_identifier_columns(
    identifier: PatientExternalIdentifier,
) -> dict[str, object]:
    """検索・一意性制約に使う列を外部識別子から導く。"""
    return {
        "id": identifier.id.value,
        "corporate_id": identifier.corporate_id.value,
        "patient_id": identifier.patient_id.value,
        "system_name": identifier.system_name.value,
        "external_patient_id": identifier.external_patient_id.value,
        "is_active": identifier.is_active,
    }


PATIENT_EXTERNAL_IDENTIFIER_MAPPING = AggregateMapping(
    table=patient_external_identifiers,
    aggregate_type=PatientExternalIdentifier,
    label="外部識別子",
    search_columns=_external_identifier_columns,
)


class PostgresPatientExternalIdentifierRepository(
    PostgresRepositoryBase, PatientExternalIdentifierRepository
):
    """患者外部識別子を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        identifier_id: PatientExternalIdentifierId,
    ) -> PatientExternalIdentifier | None:
        """法人境界を含めてIDで外部識別子を検索する。"""
        return await self.get_by_id(
            PATIENT_EXTERNAL_IDENTIFIER_MAPPING,
            identifier_id,
            corporate_id=corporate_id,
        )

    async def get_active_by_source(
        self,
        *,
        corporate_id: CorporateId,
        system_name: ExternalSystemName,
        external_patient_id: ExternalPatientId,
    ) -> PatientExternalIdentifier | None:
        """連携先と外部患者IDの組に一致する有効な行だけを取得する。

        無効化済みは返さない。誤った患者へ紐付けた外部IDを無効化してから正しい
        患者へ付け替えられるよう、一意とみなすのは有効な行だけである。
        """
        return await self.find_one(
            PATIENT_EXTERNAL_IDENTIFIER_MAPPING,
            select(patient_external_identifiers).where(
                patient_external_identifiers.c.corporate_id == corporate_id.value,
                patient_external_identifiers.c.system_name == system_name.value,
                patient_external_identifiers.c.external_patient_id
                == external_patient_id.value,
                patient_external_identifiers.c.is_active,
            ),
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientExternalIdentifier]:
        """法人・患者の外部識別子をID順で返す。"""
        return await self.find_all(
            PATIENT_EXTERNAL_IDENTIFIER_MAPPING,
            select(patient_external_identifiers)
            .where(
                patient_external_identifiers.c.corporate_id == corporate_id.value,
                patient_external_identifiers.c.patient_id == patient_id.value,
            )
            .order_by(patient_external_identifiers.c.id),
        )

    async def save(self, identifier: PatientExternalIdentifier) -> None:
        """有効行の一意性を原子的に守って外部識別子を保存する。"""
        await self.save_with_conflict_map(
            PATIENT_EXTERNAL_IDENTIFIER_MAPPING,
            identifier,
            conflicts={
                "uq_patient_external_identifiers_active_source": PatientExternalIdentifierAlreadyExistsError,
            },
        )
