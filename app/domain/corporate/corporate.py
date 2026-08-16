from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.domain.corporate.primitives import (
    CorporateId,
    CorporateName,
    CorporateRepresentativeName,
    CorporateStatus,
)


@dataclass(frozen=True, eq=False, kw_only=True)
class Corporate(AggregateRoot[CorporateId]):
    """法人エンティティ（集約ルート）。複数の薬局店舗を束ねるマルチテナントの境界"""

    id: CorporateId
    name: CorporateName
    representative_name: CorporateRepresentativeName
    status: CorporateStatus = CorporateStatus.ACTIVE

    @classmethod
    def create(
        cls,
        *,
        name: CorporateName,
        representative_name: CorporateRepresentativeName,
    ) -> Self:
        """ファクトリメソッド：新規法人の開設（契約開始）"""
        corporate = cls(
            id=CorporateId.generate(),
            name=name,
            representative_name=representative_name,
        )
        return corporate

    def change_name(self, new_name: CorporateName) -> Self:
        """法人名を変更する"""
        return replace(self, name=new_name)

    def change_representative(
        self, new_representative_name: CorporateRepresentativeName
    ) -> Self:
        """代表者名を変更する"""
        return replace(self, representative_name=new_representative_name)

    @property
    def is_active(self) -> bool:
        """通常の店舗・スタッフ操作を受け付けられる状態か判定する。"""
        return self.status is CorporateStatus.ACTIVE

    def activate(self) -> Self:
        """法人を利用可能な状態へ変更する。"""
        return replace(self, status=CorporateStatus.ACTIVE)

    def deactivate(self) -> Self:
        """法人を利用停止状態へ変更する。"""
        return replace(self, status=CorporateStatus.INACTIVE)
