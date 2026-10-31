"""Applicationのget_corporateを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from app.domain.corporate.entities import Corporate


@dataclass(frozen=True, kw_only=True)
class PolicySettingDto:
    """ポリシー単一項目の出力データ。"""

    value: bool
    overridable: bool


@dataclass(frozen=True, kw_only=True)
class CorporatePolicyDto:
    """法人ポリシーの出力データ。"""

    require_prescription_audit: PolicySettingDto
    prohibit_self_verification: PolicySettingDto


@dataclass(frozen=True, kw_only=True)
class CorporateResponseDto:
    """取得結果として画面やAPIに返すデータ構造（DTO）"""

    id: str
    name: str
    representative_name: str
    is_active: bool
    policy: CorporatePolicyDto

    @classmethod
    def from_entity(cls, corporate: Corporate) -> Self:
        """Corporate エンティティから DTO を復元するファクトリメソッド"""
        return cls(
            id=str(corporate.id.value),
            name=corporate.name.value,
            representative_name=corporate.representative_name.full_name,
            is_active=corporate.is_active,
            policy=CorporatePolicyDto(
                require_prescription_audit=PolicySettingDto(
                    value=corporate.policy.require_prescription_audit.value,
                    overridable=corporate.policy.require_prescription_audit.overridable,
                ),
                prohibit_self_verification=PolicySettingDto(
                    value=corporate.policy.prohibit_self_verification.value,
                    overridable=corporate.policy.prohibit_self_verification.overridable,
                ),
            ),
        )
