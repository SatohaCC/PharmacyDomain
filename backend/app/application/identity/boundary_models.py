"""Applicationのvaluesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class LoginSession:
    """秘密は応答時だけ渡し、通常の文字列表現には含めない。"""

    access_token: str = field(repr=False)
    password_change_required: bool


@dataclass(frozen=True, kw_only=True)
class VerifiedSubject:
    """本人確認基盤が実際に検証できた唯一の事実 —— 発行元を含む外部主体。

    内部の本人IDを持たせてはならない。外部の認証基盤が知っているのは自分が
    発行した主体までで、このシステムの本人IDは知らない。持たせられる形にすると、
    本物の認証基盤には埋められない項目をテストのダブルだけが埋められる状態に
    なり、その経路は本番で一度も実行されない。
    """

    principal_id: str
