"""患者・外部識別子の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientExternalIdentifierId,
    PatientId,
    PatientNumber,
)
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import (
    patient_external_identifiers,
    patient_number_sequences,
    patients,
)


def row_values(patient: Patient) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": patient.id.value,
        "corporate_id": patient.corporate_id.value,
        "patient_number": patient.patient_number.value,
        "payload": encode_aggregate(patient),
    }


def identifier_row_values(
    identifier: PatientExternalIdentifier,
) -> dict[str, object]:
    """外部識別子から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": identifier.id.value,
        "corporate_id": identifier.corporate_id.value,
        "patient_id": identifier.patient_id.value,
        "system_name": identifier.system_name.value,
        "external_patient_id": identifier.external_patient_id.value,
        "is_active": identifier.is_active,
        "payload": encode_aggregate(identifier),
    }


class PostgresPatientRepository(PostgresRepositoryBase, PatientRepository):
    """患者集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> Patient | None:
        """法人境界を含めてIDで患者を検索する。"""
        result = await self.session.execute(
            select(patients).where(
                patients.c.corporate_id == corporate_id.value,
                patients.c.id == patient_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_patient(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=patients.name,
            )
        )

    async def save(self, patient: Patient) -> None:
        """患者を保存する。"""
        await self.upsert(
            patients, aggregate_id=patient.id.value, values=row_values(patient)
        )

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
        result = await self.session.execute(
            select(patient_external_identifiers).where(
                patient_external_identifiers.c.corporate_id == corporate_id.value,
                patient_external_identifiers.c.id == identifier_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_identifier(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=patient_external_identifiers.name,
            )
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
        result = await self.session.execute(
            select(patient_external_identifiers).where(
                patient_external_identifiers.c.corporate_id == corporate_id.value,
                patient_external_identifiers.c.system_name == system_name.value,
                patient_external_identifiers.c.external_patient_id
                == external_patient_id.value,
                patient_external_identifiers.c.is_active,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_identifier(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=patient_external_identifiers.name,
            )
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientExternalIdentifier]:
        """法人・患者の外部識別子をID順で返す。"""
        result = await self.session.execute(
            select(patient_external_identifiers)
            .where(
                patient_external_identifiers.c.corporate_id == corporate_id.value,
                patient_external_identifiers.c.patient_id == patient_id.value,
            )
            .order_by(patient_external_identifiers.c.id)
        )
        return [
            _decode_identifier(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=patient_external_identifiers.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, identifier: PatientExternalIdentifier) -> None:
        """有効行の一意性を原子的に守って外部識別子を保存する。"""
        try:
            await self.upsert(
                patient_external_identifiers,
                aggregate_id=identifier.id.value,
                values=identifier_row_values(identifier),
            )
        except IntegrityError as error:
            if (
                constraint_name(error)
                == "uq_patient_external_identifiers_active_source"
            ):
                raise PatientExternalIdentifierAlreadyExistsError() from error
            raise


def _decode_patient(row: Mapping[str, object]) -> Patient:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "患者の payload が JSON オブジェクトではありません。"
        )
    patient = decode_aggregate(payload, Patient)
    if (
        patient.id.value != row.get("id")
        or patient.corporate_id.value != row.get("corporate_id")
        or patient.patient_number.value != row.get("patient_number")
    ):
        raise PersistenceMappingError("患者の検索列と payload が一致しません。")
    return patient


def _decode_identifier(row: Mapping[str, object]) -> PatientExternalIdentifier:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "外部識別子の payload が JSON オブジェクトではありません。"
        )
    identifier = decode_aggregate(payload, PatientExternalIdentifier)
    if (
        identifier.id.value != row.get("id")
        or identifier.corporate_id.value != row.get("corporate_id")
        or identifier.patient_id.value != row.get("patient_id")
        or identifier.system_name.value != row.get("system_name")
        or identifier.external_patient_id.value != row.get("external_patient_id")
        or identifier.is_active != row.get("is_active")
    ):
        raise PersistenceMappingError("外部識別子の検索列と payload が一致しません。")
    return identifier


__all__ = [
    "PostgresPatientExternalIdentifierRepository",
    "PostgresPatientRepository",
    "identifier_row_values",
    "row_values",
]
