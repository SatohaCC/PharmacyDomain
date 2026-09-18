"""業務トランザクションから独立した閲覧・失敗要求の記録。"""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from fastapi import Request, Response

from app.application.access_control.models import ResolvedActorContext

_LOGGER = logging.getLogger("pharmacy.access")


async def log_access(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """本文・資格情報をコピーせず、解決済み主体と結果だけを残す。"""
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        actor = getattr(request.state, "verified_actor", None)
        resource_id = None
        for name, value in request.path_params.items():
            if name.endswith("_id"):
                try:
                    resource_id = str(UUID(str(value)))
                except ValueError:
                    continue
        _LOGGER.info(
            "API要求",
            extra={
                "person_id": str(actor.person_id.value)
                if isinstance(actor, ResolvedActorContext)
                else None,
                "account_id": str(actor.account_id.value)
                if isinstance(actor, ResolvedActorContext)
                else None,
                "resource_id": resource_id,
                "status_code": status_code,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", None),
            },
        )
