"""Applicationのstaff_person_adapterを定義する。"""

from __future__ import annotations

from app.application.dispensing.interfaces.references import (
    StaffPersonBoundary as DispensingStaffPersonBoundary,
)
from app.application.store.interfaces.management import StaffPersonBoundary
from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.repositories import StaffPersonLinkRepository
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.identifiers import StaffId


class StaffPersonAdapter(StaffPersonBoundary, DispensingStaffPersonBoundary):
    """固定済みの対応だけを返し、他法人の対応は存在ごと隠す。

    店舗コンテキストへ Identity のユースケースを持ち込まないための接続点。
    対応そのものは付け替えを封じてあるので、ここで得た本人は後から変わらない。
    """

    def __init__(self, links: StaffPersonLinkRepository) -> None:
        self._links = links

    async def person_of(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> AccountPersonId | None:
        """対応が無い場合と他法人の場合を区別せず ``None`` を返す。"""
        link = await self._links.get(staff_id)
        if link is None or link.corporate_id != corporate_id:
            return None
        return link.person_id
