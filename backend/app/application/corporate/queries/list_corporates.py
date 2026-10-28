"""Applicationのlist_corporatesを定義する。"""

from __future__ import annotations

import base64
import binascii
import json

from app.application.access_control.boundary_models import Permission
from app.application.access_control.policies import AuthorizationService
from app.application.corporate.interfaces.list_corporates_query_reader import (
    ListCorporatesQueryReader,
)
from app.application.corporate.queries.dtos.list_corporates import CorporatePageDto
from app.application.corporate.queries.models import ListCorporatesQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import CorporateName, CorporateStatus
from app.domain.foundation.exceptions import DomainValidationError


class ListCorporatesUseCase:
    def __init__(
        self, reader: ListCorporatesQueryReader, authorization: AuthorizationService
    ) -> None:
        self._reader = reader
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
            CorporateStatus(query.status) if query.status is not None else None
        except ValueError as error:
            raise DomainValidationError("法人の状態が不正です。") from error
        conditions = {"name": name, "status": query.status}
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
                CorporateId.parse(decoded["after"])
            except (
                ValueError,
                binascii.Error,
                UnicodeError,
                DomainValidationError,
            ) as error:
                raise DomainValidationError(
                    "カーソルが不正、または検索条件が一致しません。"
                ) from error
        return await self._reader.read(query)
