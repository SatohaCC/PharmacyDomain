"""資格台帳コンテキストのHTTPルート。

無効化は削除ではないので ``DELETE`` にしない。発効日を持つ事実の追加であり、
発効日当日は既に無効、それ以前は有効のまま残る。``DELETE`` にすると、日付を
持てないうえに「消えた」ように見える。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from fastapi import APIRouter, Depends

from app.application.coverage import (
    ChangePatientCoveragePeriodCommand,
    DeactivatePatientCoverageCommand,
    GetPatientCoverageQuery,
    ListPatientCoveragesQuery,
    PatientCoverageDto,
    RegisterPatientCoverageCommand,
)
from app.presentational.dependencies import CoverageUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["coverage"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterCoverageRequest(RequestModel):
    """資格登録の入力。

    ``valid_from`` / ``valid_to`` は終了日を含む閉区間、``activated_on`` は
    無効化発効日を含まない区間の開始である。実効期間は両者の交差になる。
    """

    coverage_type: str
    valid_from: date
    activated_on: date
    valid_to: date | None = None
    priority: int = 1
    insurer_number: str | None = None
    insured_symbol: str | None = None
    insured_number: str | None = None
    branch_number: str | None = None
    insured_type: str | None = None
    benefit_ratio: int | None = None
    payer_number: str | None = None
    recipient_number: str | None = None


class ChangeCoveragePeriodRequest(RequestModel):
    """資格期間変更の入力。``valid_to`` の ``None`` は無期限を意味する。"""

    valid_from: date
    valid_to: date | None = None


class DeactivateCoverageRequest(RequestModel):
    """資格無効化の入力。発効日当日は既に無効として扱う。"""

    effective_on: date


@router.post(
    "/patients/{patient_id}/coverages",
    status_code=HTTPStatus.CREATED,
    response_model=PatientCoverageDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_coverage(
    corporate_id: str,
    patient_id: str,
    body: RegisterCoverageRequest,
    use_cases: CoverageUseCasesDep,
) -> PatientCoverageDto:
    """患者の資格を登録する。"""
    return await use_cases.register.execute(
        RegisterPatientCoverageCommand(
            corporate_id=corporate_id,
            patient_id=patient_id,
            coverage_type=body.coverage_type,
            valid_from=body.valid_from,
            activated_on=body.activated_on,
            valid_to=body.valid_to,
            priority=body.priority,
            insurer_number=body.insurer_number,
            insured_symbol=body.insured_symbol,
            insured_number=body.insured_number,
            branch_number=body.branch_number,
            insured_type=body.insured_type,
            benefit_ratio=body.benefit_ratio,
            payer_number=body.payer_number,
            recipient_number=body.recipient_number,
        )
    )


@router.get(
    "/patients/{patient_id}/coverages",
    response_model=list[PatientCoverageDto],
)
async def list_coverages(
    corporate_id: str,
    patient_id: str,
    use_cases: CoverageUseCasesDep,
) -> list[PatientCoverageDto]:
    """患者の資格を一覧する。"""
    return await use_cases.list_by_patient.execute(
        ListPatientCoveragesQuery(corporate_id=corporate_id, patient_id=patient_id)
    )


@router.get("/coverages/{coverage_id}", response_model=PatientCoverageDto)
async def get_coverage(
    corporate_id: str,
    coverage_id: str,
    use_cases: CoverageUseCasesDep,
) -> PatientCoverageDto:
    """資格を1件取得する。"""
    return await use_cases.get.execute(
        GetPatientCoverageQuery(corporate_id=corporate_id, coverage_id=coverage_id)
    )


@router.patch(
    "/coverages/{coverage_id}/period",
    response_model=PatientCoverageDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_coverage_period(
    corporate_id: str,
    coverage_id: str,
    body: ChangeCoveragePeriodRequest,
    use_cases: CoverageUseCasesDep,
) -> PatientCoverageDto:
    """資格の有効期間を変更する。"""
    return await use_cases.change_period.execute(
        ChangePatientCoveragePeriodCommand(
            corporate_id=corporate_id,
            coverage_id=coverage_id,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
        )
    )


@router.post(
    "/coverages/{coverage_id}/deactivation",
    response_model=PatientCoverageDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def deactivate_coverage(
    corporate_id: str,
    coverage_id: str,
    body: DeactivateCoverageRequest,
    use_cases: CoverageUseCasesDep,
) -> PatientCoverageDto:
    """資格を無効化する。同じ発効日の再無効化だけを冪等として許す。"""
    return await use_cases.deactivate.execute(
        DeactivatePatientCoverageCommand(
            corporate_id=corporate_id,
            coverage_id=coverage_id,
            effective_on=body.effective_on,
        )
    )


__all__ = ["router"]
