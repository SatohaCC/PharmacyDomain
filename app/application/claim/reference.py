"""Claim Applicationが依存する外部集約の参照境界。"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.claim.coverage_snapshot import CoverageSnapshot
from app.domain.claim.primitives import CoverageUsageTimestamp
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId


class StoreReferenceBoundary(Protocol):
    """店舗集約を直接保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人に店舗が存在することを確認する。

        Raises:
            ClaimStoreNotFoundError: 店舗が存在しない場合、および店舗が別法人に
                所属している場合。他テナントのデータは存在を隠すため403ではなく
                404相当のこの例外へ揃える。``AuthorizationError`` を送出すると
                他法人の店舗IDの存在が呼び出し元へ漏れる。
        """
        ...


class PatientReferenceBoundary(Protocol):
    """患者集約を直接保持せず、患者の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人に患者が存在することを確認する。

        Raises:
            ClaimPatientNotFoundError: 患者が存在しない場合、および患者が別法人に
                所属している場合。他テナントのデータは存在を隠すため403ではなく
                404相当のこの例外へ揃える。
        """
        ...


class CoverageSnapshotBoundary(Protocol):
    """選択された資格を請求側スナップショットへ変換する境界。"""

    async def build_snapshot(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_ids: tuple[str, ...],
        applied_at: CoverageUsageTimestamp,
    ) -> CoverageSnapshot:
        """資格IDを検証し、適用日時点の請求用スナップショットを構成する。

        Raises:
            ClaimCoverageSelectionError: 資格IDが指定法人・指定患者のものでない
                場合、適用日時点で資格が有効でない場合、および医療保険と公費の
                組み合わせがスナップショットとして成立しない場合。資格の不在も
                他テナントの資格IDの存在を隠すためこの例外へ揃える。
        """
        ...


class CoverageValidityBoundary(Protocol):
    """凍結済みスナップショットが今も有効かを資格台帳へ問い合わせる境界。

    最新履歴は受付画面の初期候補にすぎず、記録時点で有効だった資格がその後に
    期間満了や無効化を迎えている可能性がある。Claimは資格台帳を保持しないため、
    再検証はこの境界へ委ね、結果を候補DTOのフラグとして呼び出し元へ返す。
    """

    async def is_snapshot_valid(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        snapshot: CoverageSnapshot,
        applied_on: date,
    ) -> bool:
        """スナップショットの全資格が適用日時点で有効かを返す。

        存在しない資格・別法人の資格・期間外の資格・無効化済みの資格が1つでも
        含まれていれば ``False`` を返す。存在の有無を例外で区別すると他テナントの
        資格の存在が漏れるため、判定は真偽値へ畳み込む。
        """
        ...
