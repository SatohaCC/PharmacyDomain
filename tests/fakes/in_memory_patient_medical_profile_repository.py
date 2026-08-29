"""患者医療プロファイル（頭書き）Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import PatientMedicalProfileId
from app.domain.medication_history.repository import PatientMedicalProfileRepository
from app.domain.medication_history.services import (
    PatientMedicalProfileUniquenessService,
)
from app.domain.patient.primitives import PatientId


class InMemoryPatientMedicalProfileRepository(PatientMedicalProfileRepository):
    """法人境界を適用するテスト用頭書きRepository。"""

    def __init__(self) -> None:
        self.items: dict[PatientMedicalProfileId, PatientMedicalProfile] = {}
        #: 保存を失敗させたい患者。投影の保存順序を検証するテストで使う。
        self.failing_patient_ids: set[PatientId] = set()

    def fail_next_save_for(self, patient_id: PatientId) -> None:
        """指定患者の保存を以後失敗させる。

        「``save(record)`` は成功したが ``save(profile)`` が失敗した」状況を
        再現するための細工。頭書きは投影なので、この状況から薬歴を畳み込んで
        回復できることがテストの主題になる。
        """
        self.failing_patient_ids.add(patient_id)

    async def get_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile | None:
        """指定法人・患者の頭書きを取得する。未投影なら ``None``。"""
        for item in self.items.values():
            if item.corporate_id == corporate_id and item.patient_id == patient_id:
                return copy.deepcopy(item)
        return None

    async def save(self, profile: PatientMedicalProfile) -> None:
        """患者ごとに1件であることを原子的に保証して保存する。

        判定は ``PatientMedicalProfileUniquenessService`` を呼び、規則の実装が
        2箇所に分かれないようにする。
        """
        if profile.patient_id in self.failing_patient_ids:
            raise RuntimeError("頭書きの保存に失敗しました（テスト用の細工）。")
        PatientMedicalProfileUniquenessService().ensure_no_conflict(
            profile,
            [item for item in self.items.values() if item.id != profile.id],
        )
        self.items[profile.id] = copy.deepcopy(profile)
