"""HTTPの実行をApplicationの例外変換境界で包む。"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute

from app.application.failure_mapping import translate_errors


class ApplicationRoute(APIRoute):
    """入力解決と操作を通じた業務失敗をApplicationの公開失敗へ変換する。"""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """依存の解決も含む実行境界を返す。"""
        handler = super().get_route_handler()
        operation = translate_errors(handler)

        async def execute(request: Request) -> Response:
            return await operation(request)

        return execute
