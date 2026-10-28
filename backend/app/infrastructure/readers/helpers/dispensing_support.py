"""Applicationのdispensing_supportを定義する。"""

from __future__ import annotations

from app.application.dispensing.errors import DispensingNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.repositories import DispensingProcessRepository


async def load_dispensing_or_raise(
    repository: DispensingProcessRepository,
    *,
    corporate_id: CorporateId,
    dispensing_id: DispensingId,
) -> DispensingProcess:
    """指定法人の調剤セッションを取得し、存在しなければ404相当を送出する。"""
    process = await repository.get(
        corporate_id=corporate_id, dispensing_id=dispensing_id
    )
    if process is None:
        raise DispensingNotFoundError()
    return process
