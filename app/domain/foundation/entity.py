"""DDD エンティティおよび集約ルートの基底クラス定義。"""

from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.foundation.field_guard import ensure_declared_field_types
from app.domain.foundation.primitives.base import DomainPrimitive


@dataclass(frozen=True, eq=False, kw_only=True)
class Entity[ID: DomainPrimitive[Any]](ABC):
    """すべてのエンティティの基底クラス。

    エンティティは属性の値ではなく、識別子（ID）によって同一性が判定される。
    派生クラスの `@dataclass` で `eq=False` を指定することで、
    この ID に基づく同値判定（__eq__）が維持される。
    """

    id: ID

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {}

    def __post_init__(self) -> None:
        """正規化、宣言型の照合、業務ルール検証を順に実行する。"""
        self._normalize_fields()
        ensure_declared_field_types(self, labels=self._FIELD_LABELS)
        self.validate()

    def _normalize_fields(self) -> None:
        """派生クラスが複合フィールドを正規化するためのフック。"""
        return None

    def validate(self) -> None:
        """派生クラスが集約固有の不変条件を検証するためのフック。"""
        return None

    def __eq__(self, other: object) -> bool:
        """同一クラスかつ同一IDの場合に二つのエンティティを等しいとみなす。"""
        if not isinstance(other, Entity):
            return False
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        """エンティティのハッシュ値をIDに基づいて算出する。"""
        return hash((type(self), self.id))


@dataclass(frozen=True, eq=False, kw_only=True)
class AggregateRoot[ID: DomainPrimitive[Any]](Entity[ID], ABC):
    """集約ルートの基底クラス。

    整合性の境界を守るルートエンティティであることを型として表明する標識であり、
    振る舞いは :class:`Entity` と同じ（ID による同一性判定）。
    リポジトリが直接取得・永続化してよいのは、この基底を継承したクラスだけである。
    集約内部の子エンティティは :class:`Entity` を継承し、ルート経由でのみ操作する。

    ドメインイベントの記録・配送機構は意図的に持たない。発行先（``UnitOfWork``
    のコミット後にイベントを配送する経路）が存在しない状態でイベントを溜める
    API だけを用意しても、消費されないリストが増えるだけで誤解を招くため。
    必要になった時点で配送経路と併せて導入する。
    """
