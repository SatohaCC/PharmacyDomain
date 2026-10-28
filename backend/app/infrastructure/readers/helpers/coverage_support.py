"""Applicationのcoverage_supportを定義する。"""

from __future__ import annotations

from app.application.coverage.errors import PatientCoverageNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.entities import PatientCoverage
from app.domain.coverage.identifiers import PatientCoverageId
from app.domain.coverage.repositories import PatientCoverageRepository


async def load_coverage_or_raise(
    repository: PatientCoverageRepository,
    *,
    corporate_id: CorporateId,
    coverage_id: PatientCoverageId,
) -> PatientCoverage:
    """指定法人の患者資格を取得し、存在しなければ404相当を送出する。"""
    coverage = await repository.get(corporate_id=corporate_id, coverage_id=coverage_id)
    if coverage is None:
        raise PatientCoverageNotFoundError()
    return coverage
