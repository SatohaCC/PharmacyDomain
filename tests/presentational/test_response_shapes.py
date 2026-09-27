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


def test_tc45_60_Event公開APIが_OpenAPIに反映される() -> None:
    """承認されたEvent・種別・薬歴入口を生成クライアントへ公開する。"""
    openapi = create_app().openapi()
    required_routes = {
        ("get", "/corporates/{corporate_id}/event-definitions"),
        ("post", "/corporates/{corporate_id}/event-definitions"),
        (
            "patch",
            "/corporates/{corporate_id}/event-definitions/{event_type_id}",
        ),
        ("post", "/corporates/{corporate_id}/events"),
        ("get", "/corporates/{corporate_id}/events/{event_id}"),
        (
            "get",
            "/corporates/{corporate_id}/patients/{patient_id}/events/related-candidates",
        ),
        (
            "post",
            "/corporates/{corporate_id}/events/{event_id}/medication-history",
        ),
    }

    assert required_routes <= {
        (method, path)
        for path, methods in openapi["paths"].items()
        for method in methods
    }


def _request_schema(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    """Event作成のOpenAPI本文Schemaを返す。"""
    assert path in openapi["paths"]
    operation = openapi["paths"][path]["post"]
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    reference = schema.get("$ref")
    if reference is not None:
        name = reference.rsplit("/", maxsplit=1)[-1]
        schema = openapi["components"]["schemas"][name]
    return typing.cast(dict[str, Any], schema)


def test_tc45_11_Event作成では発生日時が必須である() -> None:
    openapi = create_app().openapi()
    schema = _request_schema(openapi, "/corporates/{corporate_id}/events")

    assert "occurred_at" in schema.get("required", [])


def test_tc45_12_Event作成本文から登録日時とActorを指定できない() -> None:
    openapi = create_app().openapi()
    schema = _request_schema(openapi, "/corporates/{corporate_id}/events")
    properties = set(schema.get("properties", {}))

    assert not {"created_at", "actor", "actor_id"} & properties


def test_tc45_60_Event作成と取得の応答にEvent情報と薬歴有無がある() -> None:
    openapi = create_app().openapi()
    path = "/corporates/{corporate_id}/events"
    assert path in openapi["paths"]
    operation = openapi["paths"][path]["post"]
    response_schema = operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]
    reference = response_schema.get("$ref")
    if reference is not None:
        name = reference.rsplit("/", maxsplit=1)[-1]
        response_schema = openapi["components"]["schemas"][name]

    assert {
        "event_id",
        "event_type_id",
        "event_type_name",
        "occurred_at",
        "created_at",
        "related_event_id",
        "medication_history_id",
    } <= set(response_schema.get("properties", {}))


@pytest.mark.parametrize(
    ("route", "model"), _response_models(), ids=lambda item: str(item)
)
def test_応答モデルに_ドメインプリミティブが現れない(route: str, model: Any) -> None:
    """IDや値オブジェクトは素の型へ落としてから応答に載せる。"""
    # Act
    found = _violations(model, seen=set(), trail=getattr(model, "__name__", str(model)))

    # Assert
    assert found == [], f"{route} の応答にドメインの語彙が残っている: {found}"
