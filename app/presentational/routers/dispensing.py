"""調剤コンテキストのHTTPルート。

処方箋ごとの調剤一覧だけ ``/prescriptions/{prescription_id}/dispensings`` に置く。
リフィルや分割調剤で1枚の処方箋に複数の調剤がぶら下がるため、処方箋を起点に
引けないと回数の抜けに気づけない。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from fastapi import APIRouter, Depends

from app.application.dispensing import (
    CompleteDispensingCommand,
    DispensedRpInput,
    DispensingProcessDto,
    GetDispensingQuery,
    ListDispensingsByPrescriptionQuery,
    RecordAuditCommand,
    RecordDispensedContentCommand,
    StartDispensingCommand,
    VerifyDispensingCommand,
)
from app.presentational.dependencies import DispensingUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["dispensing"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class StartDispensingRequest(RequestModel):
    """調剤開始の入力。"""

    store_id: str
    prescription_id: str
    dispenser_id: str
    #: リフィル・分割調剤の何回目か。1から始まる。
    iteration: int
    dispensed_date: date
    dispensed_rps: list[DispensedRpInput]
    split_reason: str | None = None


class RecordDispensedContentRequest(RequestModel):
    """調剤内容の記録の入力。送った内容で調剤内容を置き換える。"""

    dispensed_rps: list[DispensedRpInput]


class VerifyDispensingRequest(RequestModel):
    """鑑査の入力。"""

    verifier_id: str
    result: str
    notes: str | None = None


class RecordAuditRequest(RequestModel):
    """監査の入力。"""

    auditor_id: str
    has_issues: bool
    notes: str | None = None


class CompleteDispensingRequest(RequestModel):
    """調剤完了の入力。分割調剤では次回予定日を伴う。"""

    completion_type: str
    next_dispensing_date: date | None = None


@router.post(
    "/dispensings",
    status_code=HTTPStatus.CREATED,
    response_model=DispensingProcessDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def start_dispensing(
    corporate_id: str,
    body: StartDispensingRequest,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """調剤を開始する。処方箋が調剤可能な状態でなければ拒否される。"""
    return await use_cases.start.execute(
        StartDispensingCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            prescription_id=body.prescription_id,
            dispenser_id=body.dispenser_id,
            iteration=body.iteration,
            dispensed_date=body.dispensed_date,
            dispensed_rps=tuple(body.dispensed_rps),
            split_reason=body.split_reason,
        )
    )


@router.get("/dispensings/{dispensing_id}", response_model=DispensingProcessDto)
async def get_dispensing(
    corporate_id: str,
    dispensing_id: str,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """調剤を1件取得する。"""
    return await use_cases.get.execute(
        GetDispensingQuery(corporate_id=corporate_id, dispensing_id=dispensing_id)
    )


@router.put(
    "/dispensings/{dispensing_id}/dispensed-content",
    response_model=DispensingProcessDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def record_dispensed_content(
    corporate_id: str,
    dispensing_id: str,
    body: RecordDispensedContentRequest,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """調剤内容を記録する。

    PUT なのは、送られた内容で調剤内容一式を置き換えるからである。差分を足す
    操作にすると、代替調剤の取り消しを表現できない。
    """
    return await use_cases.record_dispensed_content.execute(
        RecordDispensedContentCommand(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
            dispensed_rps=tuple(body.dispensed_rps),
        )
    )


@router.post(
    "/dispensings/{dispensing_id}/verification",
    response_model=DispensingProcessDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def verify_dispensing(
    corporate_id: str,
    dispensing_id: str,
    body: VerifyDispensingRequest,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """鑑査の結果を記録する。"""
    return await use_cases.verify.execute(
        VerifyDispensingCommand(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
            verifier_id=body.verifier_id,
            result=body.result,
            notes=body.notes,
        )
    )


@router.post(
    "/dispensings/{dispensing_id}/audit",
    response_model=DispensingProcessDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def record_audit(
    corporate_id: str,
    dispensing_id: str,
    body: RecordAuditRequest,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """監査の結果を記録する。"""
    return await use_cases.record_audit.execute(
        RecordAuditCommand(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
            auditor_id=body.auditor_id,
            has_issues=body.has_issues,
            notes=body.notes,
        )
    )


@router.post(
    "/dispensings/{dispensing_id}/completion",
    response_model=DispensingProcessDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def complete_dispensing(
    corporate_id: str,
    dispensing_id: str,
    body: CompleteDispensingRequest,
    use_cases: DispensingUseCasesDep,
) -> DispensingProcessDto:
    """調剤を完了する。処方箋の状態更新と同じトランザクションで確定する。"""
    return await use_cases.complete.execute(
        CompleteDispensingCommand(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
            completion_type=body.completion_type,
            next_dispensing_date=body.next_dispensing_date,
        )
    )


@router.get(
    "/prescriptions/{prescription_id}/dispensings",
    response_model=list[DispensingProcessDto],
)
async def list_dispensings_by_prescription(
    corporate_id: str,
    prescription_id: str,
    use_cases: DispensingUseCasesDep,
) -> list[DispensingProcessDto]:
    """処方箋にぶら下がる調剤を回数順に一覧する。"""
    dispensings = await use_cases.list_by_prescription.execute(
        ListDispensingsByPrescriptionQuery(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
    )
    return list(dispensings)


__all__ = ["router"]
