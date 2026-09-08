"""処方箋コンテキストのHTTPルート。

剤（Rp）と薬品明細は入れ子のまま受け取る。平坦なフィールド列にすると「何番目の
要素が何番目の薬品か」が並び順の規約になり、件数一致しか検証できなくなる。
入力の型はApplication層の ``*Input`` をそのまま使う。ここで写し取ると、
Application側の項目が増えたときに黙って落ちる項目ができる。

**用量は文字列で受け取る。** 数値型にすると ``0.1`` のような刻みで誤差が入り、
不均等服用の合計一致が正当な処方を弾く。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from fastapi import APIRouter, Depends

from app.application.prescription import (
    CancelPrescriptionCommand,
    DepartmentInput,
    GetPrescriptionQuery,
    MedicalInstitutionInput,
    PrescriberInput,
    PrescriptionDto,
    PrescriptionManagementInput,
    ReadyForDispensingCommand,
    RegisterPrescriptionCommand,
    ResolveInquiryCommand,
    RpInput,
    StartInquiryCommand,
)
from app.presentational.dependencies import PrescriptionUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}/prescriptions",
    tags=["prescription"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterPrescriptionRequest(RequestModel):
    """処方箋登録の入力。"""

    store_id: str
    patient_id: str
    source_type: str
    document_number: str
    issued_date: date
    medical_institution: MedicalInstitutionInput
    department: DepartmentInput
    prescriber: PrescriberInput
    rps: list[RpInput]
    valid_to: date | None = None
    management_info: PrescriptionManagementInput | None = None
    coverage_selection_record_id: str | None = None


class StartInquiryRequest(RequestModel):
    """疑義照会の開始の入力。"""

    pharmacist_id: str
    category: str
    content: str


class ResolveInquiryRequest(RequestModel):
    """疑義照会の回答の入力。"""

    responded_by: str
    result_type: str
    content: str


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=PrescriptionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_prescription(
    corporate_id: str,
    body: RegisterPrescriptionRequest,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """処方箋を登録する。

    麻薬区分などを医薬品マスタから判定できない場合は失敗する。判定できないことを
    「該当しない」に倒すと、麻薬処方箋の必須項目チェックが素通りする。
    """
    return await use_cases.register.execute(
        RegisterPrescriptionCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            patient_id=body.patient_id,
            source_type=body.source_type,
            document_number=body.document_number,
            issued_date=body.issued_date,
            medical_institution=body.medical_institution,
            department=body.department,
            prescriber=body.prescriber,
            rps=tuple(body.rps),
            valid_to=body.valid_to,
            management_info=body.management_info,
            coverage_selection_record_id=body.coverage_selection_record_id,
        )
    )


@router.get("/{prescription_id}", response_model=PrescriptionDto)
async def get_prescription(
    corporate_id: str,
    prescription_id: str,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """処方箋を1件取得する。"""
    return await use_cases.get.execute(
        GetPrescriptionQuery(corporate_id=corporate_id, prescription_id=prescription_id)
    )


@router.post(
    "/{prescription_id}/readiness",
    response_model=PrescriptionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def ready_for_dispensing(
    corporate_id: str,
    prescription_id: str,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """調剤可能な状態にする。未回答の疑義照会が残っていれば拒否される。"""
    return await use_cases.ready_for_dispensing.execute(
        ReadyForDispensingCommand(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
    )


@router.post(
    "/{prescription_id}/cancellation",
    response_model=PrescriptionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def cancel_prescription(
    corporate_id: str,
    prescription_id: str,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """処方箋を取消する。"""
    return await use_cases.cancel.execute(
        CancelPrescriptionCommand(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
    )


@router.post(
    "/{prescription_id}/inquiries",
    status_code=HTTPStatus.CREATED,
    response_model=PrescriptionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def start_inquiry(
    corporate_id: str,
    prescription_id: str,
    body: StartInquiryRequest,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """疑義照会を開始する。"""
    return await use_cases.start_inquiry.execute(
        StartInquiryCommand(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
            pharmacist_id=body.pharmacist_id,
            category=body.category,
            content=body.content,
        )
    )


@router.post(
    "/{prescription_id}/inquiries/{inquiry_number}/resolution",
    response_model=PrescriptionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def resolve_inquiry(
    corporate_id: str,
    prescription_id: str,
    inquiry_number: int,
    body: ResolveInquiryRequest,
    use_cases: PrescriptionUseCasesDep,
) -> PrescriptionDto:
    """疑義照会に回答する。"""
    return await use_cases.resolve_inquiry.execute(
        ResolveInquiryCommand(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
            inquiry_number=inquiry_number,
            responded_by=body.responded_by,
            result_type=body.result_type,
            content=body.content,
        )
    )


__all__ = ["router"]
