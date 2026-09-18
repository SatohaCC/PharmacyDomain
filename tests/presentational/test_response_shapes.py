"""応答の形にドメインの語彙が漏れていないことを確かめる。

Application層のDTOはドメインプリミティブを保持してよい。しかしそのDTOをそのまま
HTTPの応答モデルに使うと、``StoreId`` のようなプリミティブが ``{"value": "..."}``
という入れ子のオブジェクトとして本文に出る。型検査もlintも通り、DBなしのテストも
緑のまま、生成クライアントだけが「IDは文字列ではなくオブジェクト」という契約を
受け取る。実際 ``GET /me`` は本人IDをこの形で返していた。

ここでは応答モデルを再帰的にたどり、プリミティブと値オブジェクトが現れたら落とす。
"""

from __future__ import annotations

import dataclasses
import typing
from collections.abc import Iterable, Iterator
from types import UnionType
from typing import Any, get_args, get_origin

import pytest
from fastapi.routing import APIRoute

from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.foundation.value_object import ValueObject
from app.presentational.app_factory import create_app

#: 応答に出てはいけない基底。どちらも「値1つ」または「複数項目の塊」を表す
#: ドメイン内部の語彙で、外向きの契約としては素の型へ落とす。
_FORBIDDEN_BASES = (DomainPrimitive, ValueObject)


def _api_routes(routes: Iterable[Any]) -> Iterator[APIRoute]:
    """入れ子のルータを平らにして ``APIRoute`` だけを取り出す。

    ``include_router`` で取り込んだルートは、FastAPI の版によっては入れ子の
    ルータのまま ``app.routes`` に並ぶ。外側だけを見ると0件になり、検査が
    「何も確かめていないのに緑」になる。
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        for attribute in ("routes", "original_router"):
            nested = getattr(route, attribute, None)
            if nested is None:
                continue
            yield from _api_routes(getattr(nested, "routes", nested))


def _response_models() -> list[tuple[str, Any]]:
    """登録済みルートの応答モデルを、経路の名前付きで集める。"""
    found: list[tuple[str, Any]] = []
    for route in _api_routes(create_app().routes):
        model = route.response_model
        if model is None:
            continue
        for method in sorted(route.methods or set()):
            found.append((f"{method} {route.path}", model))
    return found


def _violations(annotation: Any, *, seen: set[Any], trail: str) -> list[str]:
    """注釈をたどり、ドメイン語彙が現れた経路を列挙する。

    合併型・``tuple`` や ``list`` の要素・``Page[T]`` のような総称型の中まで
    見る。外側だけを見ると、一覧の要素に混ざったプリミティブを見逃す。
    """
    origin = get_origin(annotation)
    if origin is not None:
        # 合併型は同じ項目の別の可能性なので、経路の名前を増やさない。
        label = trail if origin in {typing.Union, UnionType} else f"{trail}[]"
        found = []
        for argument in get_args(annotation):
            found.extend(_violations(argument, seen=seen, trail=label))
        return found
    if not isinstance(annotation, type):
        return []
    if issubclass(annotation, _FORBIDDEN_BASES):
        return [f"{trail}: {annotation.__name__}"]
    if not dataclasses.is_dataclass(annotation) or annotation in seen:
        return []
    seen = seen | {annotation}
    hints = typing.get_type_hints(annotation)
    found = []
    for field in dataclasses.fields(annotation):
        found.extend(
            _violations(
                hints.get(field.name, field.type),
                seen=seen,
                trail=f"{trail}.{field.name}",
            )
        )
    return found


def test_応答モデルの一覧が_空でない() -> None:
    """走査の対象が0件なら、以下の検査は何も確かめていない。"""
    # Act
    models = _response_models()

    # Assert
    assert len(models) > 20


@pytest.mark.parametrize(
    ("route", "model"), _response_models(), ids=lambda item: str(item)
)
def test_応答モデルに_ドメインプリミティブが現れない(route: str, model: Any) -> None:
    """IDや値オブジェクトは素の型へ落としてから応答に載せる。"""
    # Act
    found = _violations(model, seen=set(), trail=getattr(model, "__name__", str(model)))

    # Assert
    assert found == [], f"{route} の応答にドメインの語彙が残っている: {found}"
