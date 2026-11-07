"""患者一覧取得の抽象インターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.application.patient.queries.dtos.list_patients import PatientSummaryDto
from app.application.patient.queries.models import ListPatientsQuery


class ListPatientsQueryReader(Protocol):
    """認可済みの対象法人に所属する患者一覧を取得するクエリリーダー。"""

    async def read(self, query: ListPatientsQuery) -> list[PatientSummaryDto]: ...
