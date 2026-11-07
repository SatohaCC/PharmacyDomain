"""Repositoryから患者一覧DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.patient.interfaces.list_patients_query_reader import (
    ListPatientsQueryReader,
)
from app.application.patient.queries.dtos.list_patients import PatientSummaryDto
from app.application.patient.queries.models import ListPatientsQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import Patient
from app.domain.patient.repositories import PatientRepository


def _matches_keyword(patient: Patient, keyword: str) -> bool:
    """患者が検索キーワードに合致するか判定する。"""
    kw = keyword.strip().lower()
    if not kw:
        return True
    # 患者番号
    if str(patient.patient_number.value) == kw:
        return True
    # 漢字氏名
    full_name = f"{patient.names.kanji.last_name.value}{patient.names.kanji.first_name.value}".lower()
    if kw in full_name:
        return True
    # カナ氏名
    full_name_kana = f"{patient.names.kana.last_name.value}{patient.names.kana.first_name.value}".lower()
    if kw in full_name_kana:
        return True
    # 電話番号
    return bool(patient.phone_number is not None and kw in patient.phone_number.value)


class ListPatientsProjection(ListPatientsQueryReader):
    """認可済みの対象法人に所属する患者一覧を取得するプロジェクション。"""

    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    async def read(self, query: ListPatientsQuery) -> list[PatientSummaryDto]:
        corporate_id = CorporateId.parse(query.corporate_id)
        patients = await self._repository.list_by_corporate(corporate_id)
        if query.keyword:
            patients = [p for p in patients if _matches_keyword(p, query.keyword)]
        return [PatientSummaryDto.from_entity(p) for p in patients]
