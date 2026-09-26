"""受付コンテキストのHTTPルート。

最新の選択履歴は「次に使う候補」であって、そのまま適用してよい選択ではない。
応答の ``is_still_valid`` が偽なら、資格が適用日時点で切れている。呼び出し側は
候補を自動適用せず、選び直しを求めること。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.reception.associate_reception_medication_history import (
    AssociateReceptionMedicationHistoryCommand,
)
from app.application.reception.get_coverage_selection import CoverageSelectionRecordDto
from app.application.reception.get_last_coverage_selection import (
    GetLastCoverageSelectionQuery,
    LastCoverageSelectionCandidateDto,
)
from app.application.reception.record_coverage_selection import (
    RecordCoverageSelectionCommand,
)
from app.presentational.dependencies import ReceptionUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["reception"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RecordCoverageSelectionRequest(RequestModel):
    """受付時の資格選択の入力。"""

    store_id: str
    patient_id: str
    applied_on: date
    #: 適用する資格のID。医療保険は0〜1件、公費は0〜4件まで。
    coverage_ids: list[str]


class AssociateReceptionMedicationHistoryRequest(RequestModel):
    """受付を薬歴へ関連付ける入力。"""

    store_id: str
    medication_history_id: str


class AssociateReceptionMedicationHistoryResponse(RequestModel):
    """受付と薬歴の関連結果。"""

    reception_id: str
    medication_history_id: str


@router.post(
    "/coverage-selections",
    status_code=HTTPStatus.CREATED,
    response_model=CoverageSelectionRecordDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def record_coverage_selection(
    corporate_id: str,
    body: RecordCoverageSelectionRequest,
    use_cases: ReceptionUseCasesDep,
) -> CoverageSelectionRecordDto:
    """受付で選んだ資格の組み合わせを履歴として残す。"""
    return await use_cases.record_coverage_selection.execute(
        RecordCoverageSelectionCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            patient_id=body.patient_id,
            applied_on=body.applied_on,
            coverage_ids=tuple(body.coverage_ids),
        )
    )


@router.get(
    "/coverage-selections/latest",
    response_model=LastCoverageSelectionCandidateDto | None,
)
async def get_last_coverage_selection(
    corporate_id: str,
    use_cases: ReceptionUseCasesDep,
    store_id: Annotated[str, Query(description="受付を行う店舗のID。")],
    patient_id: Annotated[str, Query(description="対象患者のID。")],
    applied_on: Annotated[date, Query(description="資格の有効性を判定する業務日。")],
) -> LastCoverageSelectionCandidateDto | None:
    """同一法人・店舗・患者の直近の選択を候補として返す。

    履歴が無ければ ``null`` を返す。``is_still_valid`` が偽の候補をそのまま
    適用してはならない（適用日時点で資格が切れている）。
    """
    return await use_cases.get_last_coverage_selection.execute(
        GetLastCoverageSelectionQuery(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            applied_on=applied_on,
        )
    )


@router.post(
    "/receptions/{reception_id}/medication-history",
    response_model=AssociateReceptionMedicationHistoryResponse,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def associate_reception_medication_history(
    corporate_id: str,
    reception_id: str,
    body: AssociateReceptionMedicationHistoryRequest,
    use_cases: ReceptionUseCasesDep,
) -> AssociateReceptionMedicationHistoryResponse:
    """薬剤師が選んだ薬歴を受付へ関連付ける。"""
    reception = await use_cases.associate_medication_history.execute(
        AssociateReceptionMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            reception_id=reception_id,
            medication_history_id=body.medication_history_id,
        )
    )
    return AssociateReceptionMedicationHistoryResponse(
        reception_id=reception.reception_id,
        medication_history_id=reception.medication_history_id,
    )


__all__ = ["router"]
