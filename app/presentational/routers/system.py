"""稼働確認用のエンドポイント。

認証も業務ユースケースも通さない。ここに認証を掛けると、認証基盤が落ちている
ときに死活監視まで同時に落ちて、原因の切り分けができなくなる。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class ServiceStatusResponse(BaseModel):
    """稼働状態の応答。"""

    status: str


@router.get("/health", response_model=ServiceStatusResponse)
def check_health() -> ServiceStatusResponse:
    """プロセスが応答できることだけを返す。

    DBへは触らない。接続不能を含めた依存の健全性は、業務エンドポイントの
    結果と監視側で判断する。
    """
    return ServiceStatusResponse(status="ok")


__all__ = ["router"]
