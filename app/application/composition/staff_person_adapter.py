"""スタッフと本人の対応を、店舗の管理薬剤師任命へ供給する。"""

from app.application.store.management import StaffPersonBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.identity.repository import StaffPersonLinkRepository
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.primitives import StaffId


class StaffPersonAdapter(StaffPersonBoundary):
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


__all__ = ["StaffPersonAdapter"]
