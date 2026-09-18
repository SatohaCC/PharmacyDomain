"""ベンダー向け法人検索の公開インターフェース。"""

import base64
import binascii
import json
from dataclasses import dataclass

from app.application.access_control import AuthorizationService, Permission
from app.application.corporate.get_corporate import CorporateResponseDto
from app.domain.corporate.primitives import CorporateId, CorporateName, CorporateStatus
from app.domain.corporate.search import CorporateSearch, CorporateSearchRepository
from app.domain.foundation.exceptions import DomainValidationError


@dataclass(frozen=True, kw_only=True)
class ListCorporatesQuery:
    """法人一覧の検索条件。"""

    name: str | None = None
    status: str | None = None
    cursor: str | None = None
    limit: int = 50


@dataclass(frozen=True, kw_only=True)
class CorporatePageDto:
    """法人一覧の一ページ。"""

    items: tuple[CorporateResponseDto, ...]
    next_cursor: str | None


class ListCorporatesUseCase:
    """認可されたベンダーに法人をページ単位で返す。"""

    def __init__(
        self,
        repository: CorporateSearchRepository,
        authorization: AuthorizationService,
    ) -> None:
        self._repository = repository
        self._authorization = authorization

    async def execute(self, query: ListCorporatesQuery) -> CorporatePageDto:
        """検索結果を返す。"""
        self._authorization.require_vendor_system_admin(
            permission=Permission.REGISTER_CORPORATE
        )
        if isinstance(query.limit, bool) or not 1 <= query.limit <= 100:
            raise DomainValidationError("取得件数は1から100まで指定してください。")
        name = (
            CorporateName(query.name).value
            if query.name and query.name.strip()
            else None
        )
        try:
            status = CorporateStatus(query.status) if query.status is not None else None
        except ValueError as error:
            raise DomainValidationError("法人の状態が不正です。") from error
        conditions = {"name": name, "status": query.status}
        after_id = None
        if query.cursor is not None:
            try:
                decoded = json.loads(
                    base64.b64decode(query.cursor, altchars=b"-_", validate=True)
                )
                if (
                    not isinstance(decoded, dict)
                    or decoded.get("conditions") != conditions
                    or not isinstance(decoded.get("after"), str)
                ):
                    raise ValueError("検索条件が一致しません。")
                after_id = CorporateId.parse(decoded["after"])
            except (
                ValueError,
                binascii.Error,
                UnicodeError,
                DomainValidationError,
            ) as error:
                raise DomainValidationError(
                    "カーソルが不正、または検索条件が一致しません。"
                ) from error
        found = await self._repository.search(
            CorporateSearch(
                name=name, status=status, after_id=after_id, limit=query.limit + 1
            )
        )
        items = found[: query.limit]
        next_cursor = None
        if len(found) > query.limit:
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {"conditions": conditions, "after": str(items[-1].id.value)},
                    ensure_ascii=False,
                ).encode()
            ).decode()
        return CorporatePageDto(
            items=tuple(CorporateResponseDto.from_entity(item) for item in items),
            next_cursor=next_cursor,
        )
