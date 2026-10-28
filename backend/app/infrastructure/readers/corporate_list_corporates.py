"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

import base64
import binascii
import json

from app.application.corporate.interfaces.list_corporates_query_reader import (
    ListCorporatesQueryReader,
)
from app.application.corporate.queries.dtos.get_corporate import CorporateResponseDto
from app.application.corporate.queries.dtos.list_corporates import CorporatePageDto
from app.application.corporate.queries.models import ListCorporatesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateName,
    CorporatePageSize,
    CorporateSearchText,
    CorporateStatus,
)
from app.domain.corporate.repositories import CorporateSearchRepository
from app.domain.corporate.value_objects import CorporateSearch
from app.domain.foundation.exceptions import DomainValidationError


class ListCorporatesProjection(ListCorporatesQueryReader):
    """認可されたベンダーに法人をページ単位で返す。"""

    def __init__(self, repository: CorporateSearchRepository) -> None:
        self._repository = repository

    async def read(self, query: ListCorporatesQuery) -> CorporatePageDto:
        """検索結果を返す。"""
        if isinstance(query.limit, bool) or not 1 <= query.limit <= 100:
            raise DomainValidationError("取得件数は1から100まで指定してください。")
        name = (
            CorporateName(query.name).value
            if query.name and query.name.strip()
            else None
        )
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
                    or (not isinstance(decoded.get("after"), str))
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
        status = CorporateStatus(query.status) if query.status is not None else None
        found = await self._repository.search(
            CorporateSearch(
                name=CorporateSearchText(name) if name is not None else None,
                status=status,
                after_id=after_id,
                limit=CorporatePageSize(query.limit + 1),
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
