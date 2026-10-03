"""患者の確定済み薬歴から頭書き（患者医療プロファイル）を再投影して保存する。"""

from __future__ import annotations

from dataclasses import replace

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.repository import (
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.patient.primitives import PatientId


class PatientMedicalProfileProjectionService:
    """確定済み薬歴から頭書きを再構築し、同一患者の全店舗記録を反映して保存する。

    確定・訂正・手動再構築の各ユースケースから呼び出される共通のApplicationサービスである。
    各集約・差分の時系列再生順序や臨床Intentの適用規則はDomain層の
    ``PatientMedicalProfile.rebuild_from()`` に委ね、このサービスは複数店舗にわたる
    投影対象の取得、投影対象レコードの選別、既存頭書きIDの維持、および永続化を集約する。
    """

    def __init__(
        self,
        record_repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository

    async def project(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile:
        """患者の全店舗の投影対象から頭書きを再構築し、既存IDを維持して保存する。"""
        records = await self._record_repository.list_for_profile_projection(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        rebuilt = PatientMedicalProfile.rebuild_from(
            corporate_id=corporate_id,
            patient_id=patient_id,
            records=tuple(item for item in records if item.is_projection_eligible),
        )
        existing = await self._profile_repository.get_by_patient(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if existing is not None:
            rebuilt = replace(rebuilt, id=existing.id)
        await self._profile_repository.save(rebuilt)
        return rebuilt


__all__ = ["PatientMedicalProfileProjectionService"]
