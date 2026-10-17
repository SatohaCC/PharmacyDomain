"""患者の名寄せ（統合）ドメインサービス。"""

from __future__ import annotations

from datetime import datetime

from app.domain.patient.exceptions import PatientStateConflictError
from app.domain.patient.lifecycle import PatientStatus, PatientStatusReason
from app.domain.patient.patient import Patient
from app.domain.shared.actor import AccountPersonId, UserAccountId


class PatientMergeService:
    """同一法人内の患者集約を統合するドメインサービス。"""

    @classmethod
    def merge(
        cls,
        source: Patient,
        target: Patient,
        *,
        reason: PatientStatusReason,
        person_id: AccountPersonId,
        account_id: UserAccountId,
        recorded_at: datetime,
    ) -> Patient:
        """source患者をtarget患者へ名寄せ統合する。

        複数集約に跨る以下のルールを検証する:
        1. source と target は同一法人に属していなければならない。
        2. source と target は同一の患者であってはならない。
        3. source は既に統合済み（MERGED）であってはならない。
        4. target は有効（ACTIVE）でなければならない（非アクティブまたは統合済みの患者へは統合できない）。
        """
        if source.corporate_id != target.corporate_id:
            raise PatientStateConflictError(
                "異なる法人の患者どうしを統合することはできません。"
            )
        if source.id == target.id:
            raise PatientStateConflictError(
                "同一の患者どうしを統合することはできません。"
            )
        if source.status == PatientStatus.MERGED:
            raise PatientStateConflictError(
                "既に統合済みの患者を再度統合することはできません。"
            )
        if target.status != PatientStatus.ACTIVE:
            raise PatientStateConflictError("統合先には有効な患者を指定してください。")
        return source.merge_into(
            target.id,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
