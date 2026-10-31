"""Applicationのmanagementを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class CorporatePolicyOverridableSnapshot:
    """法人ポリシーの上書き可否スナップショット。"""

    require_prescription_audit_overridable: bool
    prohibit_self_verification_overridable: bool


class CorporatePolicyBoundary(Protocol):
    """店舗ポリシー更新時に法人ポリシーの上書き可否を確認する境界。"""

    async def get_overridable(
        self, corporate_id: CorporateId
    ) -> CorporatePolicyOverridableSnapshot: ...


class StaffPersonBoundary(Protocol):
    """スタッフに対応する自然人を引く境界。

    Identity のユースケースへは依存させない。管理薬剤師の専任義務が要るのは
    「そのスタッフが誰か」という1点だけなので、本人・アカウント・法人アクセス権の
    語彙をまとめて持ち込むと、店舗の配線が Identity の変更に引きずられる。
    """

    async def person_of(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> AccountPersonId | None:
        """固定済みの本人を返す。未固定・他法人・未存在は ``None`` で隠す。"""
        ...


class StoreWorkBoundary(Protocol):
    """店舗に残っている未完了の処方箋・調剤を照会する。"""

    async def has_unfinished(
        self, corporate_id: CorporateId, store_id: StoreId
    ) -> bool:
        """対象法人・店舗の未完了業務が一件でもあれば真を返す。"""
        ...
