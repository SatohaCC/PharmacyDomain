"""ルータ間で共有するリクエスト・レスポンスの型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """リクエスト本文の基底。

    未知のフィールドを拒否する。黙って捨てると、項目名を打ち間違えた変更要求が
    「成功したのに何も変わらない」応答になり、呼び出し側が気づけない。
    """

    model_config = ConfigDict(extra="forbid")


class RegisteredIdResponse(BaseModel):
    """新規登録で採番されたIDだけを返す応答。"""

    id: str


__all__ = [
    "RegisteredIdResponse",
    "RequestModel",
]
