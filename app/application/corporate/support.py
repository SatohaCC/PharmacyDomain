"""法人集約の取得と有効状態確認を共通化する処理。"""

from app.application.corporate.exceptions import (
    CorporateInactiveError,
    CorporateNotFoundError,
)
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId
from app.domain.corporate.repository import CorporateRepository


def _ensure_active(corporate: Corporate) -> Corporate:
    """法人が利用可能状態（ACTIVE）であることを確認して返す。"""
    if not corporate.is_active:
        raise CorporateInactiveError(
            f"法人（ID: {corporate.id.value}）は現在利用できません。"
        )
    return corporate


async def load_corporate_or_raise(
    repository: CorporateRepository,
    corporate_id: CorporateId,
) -> Corporate:
    """指定された法人を取得し、存在しなければ例外を送出する。"""
    corporate = await repository.get(corporate_id)
    if corporate is None:
        raise CorporateNotFoundError(
            f"指定された法人（ID: {corporate_id.value}）が見つかりません。"
        )
    return corporate


async def load_active_corporate_or_raise(
    repository: CorporateRepository,
    corporate_id: CorporateId,
) -> Corporate:
    """指定された法人が存在し、利用可能であることを確認して返す。"""
    corporate = await load_corporate_or_raise(repository, corporate_id)
    return _ensure_active(corporate)


__all__ = [
    "load_active_corporate_or_raise",
    "load_corporate_or_raise",
]
