"""DDD エンティティおよび集約ルートの基底クラス定義（Shared Kernel）。"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any

from app.base.domain.primitives.base import DomainPrimitive


@dataclass(frozen=True, eq=False, kw_only=True)
class Entity[ID: DomainPrimitive[Any]](ABC):
    """すべてのエンティティの基底クラス。

    エンティティは属性の値ではなく、識別子（ID）によって同一性が判定される。
    派生クラスの `@dataclass` で `eq=False` を指定することで、
    この ID に基づく同値判定（__eq__）が維持される。
    """

    id: ID

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
