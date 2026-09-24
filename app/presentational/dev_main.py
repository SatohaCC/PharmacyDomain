"""開発用のASGI起動点。**本番では使わない。**

認証基盤が未実装の間、`app.main:app` は全ての業務操作を401で拒否する。設計として
正しいが、`/docs` から動きを確かめられない。そこで「1つの固定トークンを、1人の
固定した操作主体として通す」だけの起動点を分けて置く。

本番と分ける理由は、環境変数の付け忘れよりも**起動点の取り違え**のほうが起きにくい
からである。`Dockerfile` の `CMD` は `app.main:app` のまま変えず、この起動点は
`compose.yaml` の開発用サービスからしか呼ばない。仮にこのモジュールが本番イメージ
へ入っても、起動されない限り何も通さない。取り違えは
``tests/presentational/test_dev_main.py`` が `Dockerfile` を読んで検出する。

環境変数（すべて `create_dev_app()` を呼んだ時点で読む）:

- ``DEV_ACTOR_TOKEN``: 通す唯一のトークン。**必須**。既定値は用意しない。
- ``DEV_ACTOR_PERSON_ID`` / ``DEV_ACTOR_ACCOUNT_ID``: 操作主体の本人IDと
  アカウントID。**必須**。更新は監査を伴い、監査行は ``user_accounts`` への
  複合外部キーを持つので、実在する行を指していないと保存が失敗する。
  開発用DBへ ``account_people`` と ``user_accounts`` を1件ずつ入れてから指定する。
- ``DEV_ACTOR_ROLE``: ``vendor_system_admin``（既定） / ``corporate_admin`` /
  ``store_operator`` / ``store_viewer``。
- ``DEV_ACTOR_CORPORATE_ID``: ``vendor_system_admin`` 以外のときの所属法人ID。
- ``DEV_ACTOR_STORE_IDS``: 店舗ロールのときの許可店舗ID（カンマ区切り）。
- ``DEV_ACTOR_PRINCIPAL_ID``: 監査に残る主体の識別子。既定は ``dev-actor``。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import assert_never

from fastapi import FastAPI

from app.application.access_control.models import (
    ActorContext,
    ActorRole,
    ResolvedActorContext,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.store.primitives import StoreId
from app.presentational.app_factory import create_app
from app.presentational.authentication import ActorContextProvider
from app.presentational.exceptions import AuthenticationError

_DEFAULT_PRINCIPAL_ID = "dev-actor"
_TITLE_SUFFIX = "（開発用・固定トークン認証）"
_DESCRIPTION = (
    "**開発用の起動点です。** 認証は `DEV_ACTOR_TOKEN` の固定トークン1つだけで、"
    "誰が来ても同じ操作主体になります。本番は `app.main:app` を使ってください。"
)


class DevActorConfigurationError(ValueError):
    """開発用の操作主体の設定が不足または不正な場合の例外。"""


class StaticTokenActorContextProvider(ActorContextProvider):
    """1つの固定トークンだけを通す開発用の認証基盤。

    トークンからロールも法人も導かない。導けるように見せると、開発用の仕組みが
    そのまま本物の認証に見えてしまう。ここが決めるのは「通すか通さないか」だけで、
    主体は起動時に固定する。
    """

    def __init__(self, *, token: str, actor: ActorContext) -> None:
        self._token = token
        self._actor = actor

    async def authenticate(self, credential: str | None) -> ActorContext:
        """固定トークンと一致したときだけ操作主体を返す。"""
        if credential != self._token:
            raise AuthenticationError()
        return self._actor


def build_actor_provider(
    environment: Mapping[str, str] | None = None,
) -> StaticTokenActorContextProvider:
    """環境変数から開発用の認証基盤を組み立てる。

    Raises:
        DevActorConfigurationError: 設定が不足または不正な場合。起動を続けない。
            トークン未設定を「何でも通す」に倒すと、開発用の起動点が無条件の
            穴になる。
    """
    values = os.environ if environment is None else environment
    token = values.get("DEV_ACTOR_TOKEN", "").strip()
    if not token:
        raise DevActorConfigurationError(
            "DEV_ACTOR_TOKEN が設定されていません。"
            "開発用の起動点は、通すトークンを明示しない限り起動しません。"
        )
    if not token.isascii():
        # HTTPヘッダへ載らない値を許すと、起動はできるのに全リクエストが401に
        # なり、原因がトークンの文字種だと気づきにくい。
        raise DevActorConfigurationError(
            "DEV_ACTOR_TOKEN はASCII文字だけで指定してください"
            "（Authorization ヘッダへ載せられません）。"
        )
    principal_id = (
        values.get("DEV_ACTOR_PRINCIPAL_ID", "").strip() or _DEFAULT_PRINCIPAL_ID
    )
    return StaticTokenActorContextProvider(
        token=token,
        actor=_build_actor(values, principal_id=principal_id),
    )


def _build_actor(values: Mapping[str, str], *, principal_id: str) -> ActorContext:
    """本人とアカウントを特定済みの操作主体を組み立てる。

    素の :class:`ActorContext` を返してはならない。更新は監査の追記を伴い、
    追記は本人とアカウントを要求するので、本人未特定の主体では保存が拒否される。
    開発用の起動点だけ通す抜け道を作ると、本番で守っている規則が開発中に一度も
    実行されないまま残る。
    """
    role = _parse_role(values.get("DEV_ACTOR_ROLE", "").strip())
    person_id = _parse_person_id(values.get("DEV_ACTOR_PERSON_ID", "").strip())
    account_id = _parse_account_id(values.get("DEV_ACTOR_ACCOUNT_ID", "").strip())
    if role is ActorRole.VENDOR_SYSTEM_ADMIN:
        return ResolvedActorContext(
            principal_id=principal_id,
            person_id=person_id,
            account_id=account_id,
            roles=frozenset({role}),
        )
    corporate_id = _parse_corporate_id(values.get("DEV_ACTOR_CORPORATE_ID", "").strip())
    if role is ActorRole.CORPORATE_ADMIN:
        return ResolvedActorContext(
            principal_id=principal_id,
            person_id=person_id,
            account_id=account_id,
            roles=frozenset({role}),
            corporate_id=corporate_id,
        )
    if role is ActorRole.STORE_OPERATOR or role is ActorRole.STORE_VIEWER:
        return ResolvedActorContext(
            principal_id=principal_id,
            person_id=person_id,
            account_id=account_id,
            roles=frozenset({role}),
            corporate_id=corporate_id,
            store_ids=_parse_store_ids(values.get("DEV_ACTOR_STORE_IDS", "").strip()),
        )
    # ロールが増えたときに、ここで mypy が分岐漏れを指摘する。
    assert_never(role)


def _parse_person_id(raw_person_id: str) -> AccountPersonId:
    if not raw_person_id:
        raise DevActorConfigurationError(
            "DEV_ACTOR_PERSON_ID が設定されていません。更新は監査を伴い、"
            "監査行は user_accounts への外部キーを持つので、実在する本人IDが必要です。"
        )
    try:
        return AccountPersonId.parse(raw_person_id)
    except DomainValidationError as error:
        raise DevActorConfigurationError(
            f"DEV_ACTOR_PERSON_ID を本人IDとして読めません: {error}"
        ) from error


def _parse_account_id(raw_account_id: str) -> UserAccountId:
    if not raw_account_id:
        raise DevActorConfigurationError(
            "DEV_ACTOR_ACCOUNT_ID が設定されていません。更新は監査を伴い、"
            "監査行は user_accounts への外部キーを持つので、"
            "実在するアカウントIDが必要です。"
        )
    try:
        return UserAccountId.parse(raw_account_id)
    except DomainValidationError as error:
        raise DevActorConfigurationError(
            f"DEV_ACTOR_ACCOUNT_ID をアカウントIDとして読めません: {error}"
        ) from error


def _parse_store_ids(raw_store_ids: str) -> frozenset[StoreId]:
    if not raw_store_ids:
        raise DevActorConfigurationError(
            "DEV_ACTOR_ROLE に店舗ロールを指定した場合は "
            "DEV_ACTOR_STORE_IDS が必要です。"
        )
    try:
        return frozenset(
            StoreId.parse(item.strip())
            for item in raw_store_ids.split(",")
            if item.strip()
        )
    except DomainValidationError as error:
        raise DevActorConfigurationError(
            f"DEV_ACTOR_STORE_IDS を店舗IDの一覧として読めません: {error}"
        ) from error


def _parse_role(raw_role: str) -> ActorRole:
    if not raw_role:
        return ActorRole.VENDOR_SYSTEM_ADMIN
    try:
        return ActorRole(raw_role)
    except ValueError as error:
        allowed = "', '".join(role.value for role in ActorRole)
        raise DevActorConfigurationError(
            f"DEV_ACTOR_ROLE は '{allowed}' のいずれかで指定してください。"
            f"受け取った値: '{raw_role}'。"
        ) from error


def _parse_corporate_id(raw_corporate_id: str) -> CorporateId:
    if not raw_corporate_id:
        raise DevActorConfigurationError(
            "DEV_ACTOR_ROLE に vendor_system_admin 以外を指定した場合は "
            "DEV_ACTOR_CORPORATE_ID が必要です。"
        )
    try:
        return CorporateId.parse(raw_corporate_id)
    except DomainValidationError as error:
        raise DevActorConfigurationError(
            f"DEV_ACTOR_CORPORATE_ID を法人IDとして読めません: {error}"
        ) from error


def create_dev_app() -> FastAPI:
    """開発用の設定でアプリケーションを組み立てる。

    uvicorn の ``--factory`` から呼ぶ。モジュール読み込み時に環境変数を読まないので、
    静的チェッカやテストがこのモジュールを import しても、設定の有無で落ちない。
    """
    app = create_app(actor_provider=build_actor_provider())
    # 開いている `/docs` がどちらの起動点かを、画面上で見分けられるようにする。
    app.title = f"{app.title}{_TITLE_SUFFIX}"
    app.description = _DESCRIPTION
    return app


__all__ = [
    "DevActorConfigurationError",
    "StaticTokenActorContextProvider",
    "build_actor_provider",
    "create_dev_app",
]
