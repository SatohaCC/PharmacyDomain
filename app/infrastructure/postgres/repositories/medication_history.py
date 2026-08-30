"""薬歴・頭書きの PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    MedicationHistoryStatus,
)
from app.domain.medication_history.repository import (
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.patient.primitives import PatientId
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import (
    medication_history_records,
    patient_medical_profiles,
)


def row_values(record: MedicationHistoryRecord) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": record.id.value,
        "corporate_id": record.corporate_id.value,
        "store_id": record.store_id.value,
        "patient_id": record.patient_id.value,
        "dispensing_id": record.dispensing_id.value,
        "prescription_id": record.prescription_id.value,
        "status": record.status.value,
        "counseled_at": record.counseled_at.value,
        "payload": encode_aggregate(record),
    }


def profile_row_values(profile: PatientMedicalProfile) -> dict[str, object]:
    """頭書きから、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": profile.id.value,
        "corporate_id": profile.corporate_id.value,
        "patient_id": profile.patient_id.value,
        "payload": encode_aggregate(profile),
    }


class PostgresMedicationHistoryRepository(
    PostgresRepositoryBase, MedicationHistoryRepository
):
    """薬歴指導記録集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        record_id: MedicationHistoryRecordId,
    ) -> MedicationHistoryRecord | None:
        """法人境界を含めてIDで薬歴を検索する。"""
        result = await self.session.execute(
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.id == record_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=medication_history_records.name,
            )
        )

    async def get_by_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> MedicationHistoryRecord | None:
        """調剤セッションに紐付く確定済の薬歴を返す。

        下書きは複数あってよいので確定済だけを対象にする。確定済が1件以下で
        あることは部分一意インデックスが保証する。
        """
        result = await self.session.execute(
            select(medication_history_records).where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.dispensing_id == dispensing_id.value,
                medication_history_records.c.status
                == MedicationHistoryStatus.FINALIZED.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=medication_history_records.name,
            )
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[MedicationHistoryRecord]:
        """患者の薬歴タイムラインを ``counseled_at`` 降順で返す。"""
        result = await self.session.execute(
            select(medication_history_records)
            .where(
                medication_history_records.c.corporate_id == corporate_id.value,
                medication_history_records.c.patient_id == patient_id.value,
            )
            .order_by(
                medication_history_records.c.counseled_at.desc(),
                medication_history_records.c.id.desc(),
            )
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=medication_history_records.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, record: MedicationHistoryRecord) -> None:
        """同一調剤セッションの確定済薬歴の重複を原子的に拒否して保存する。"""
        try:
            await self.upsert(
                medication_history_records,
                aggregate_id=record.id.value,
                values=row_values(record),
            )
        except IntegrityError as error:
            if (
                constraint_name(error)
                == "uq_medication_history_records_finalized_dispensing"
            ):
                raise MedicationHistoryAlreadyExistsError() from error
            raise


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
        result = await self.session.execute(
            select(patient_medical_profiles).where(
                patient_medical_profiles.c.corporate_id == corporate_id.value,
                patient_medical_profiles.c.patient_id == patient_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_profile(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=patient_medical_profiles.name,
            )
        )

    async def save(self, profile: PatientMedicalProfile) -> None:
        """患者ごとに1件であることを原子的に保証して保存する。"""
        try:
            await self.upsert(
                patient_medical_profiles,
                aggregate_id=profile.id.value,
                values=profile_row_values(profile),
            )
        except IntegrityError as error:
            if constraint_name(error) == "uq_patient_medical_profiles_patient":
                raise PatientMedicalProfileAlreadyExistsError() from error
            raise


def _decode_row(row: Mapping[str, object]) -> MedicationHistoryRecord:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "薬歴の payload が JSON オブジェクトではありません。"
        )
    record = decode_aggregate(payload, MedicationHistoryRecord)
    if (
        record.id.value != row.get("id")
        or record.corporate_id.value != row.get("corporate_id")
        or record.store_id.value != row.get("store_id")
        or record.patient_id.value != row.get("patient_id")
        or record.dispensing_id.value != row.get("dispensing_id")
        or record.prescription_id.value != row.get("prescription_id")
        or record.status.value != row.get("status")
        or record.counseled_at.value != row.get("counseled_at")
    ):
        raise PersistenceMappingError("薬歴の検索列と payload が一致しません。")
    return record


def _decode_profile(row: Mapping[str, object]) -> PatientMedicalProfile:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "頭書きの payload が JSON オブジェクトではありません。"
        )
    profile = decode_aggregate(payload, PatientMedicalProfile)
    if (
        profile.id.value != row.get("id")
        or profile.corporate_id.value != row.get("corporate_id")
        or profile.patient_id.value != row.get("patient_id")
    ):
        raise PersistenceMappingError("頭書きの検索列と payload が一致しません。")
    return profile
