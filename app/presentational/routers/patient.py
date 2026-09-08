"""患者コンテキストのHTTPルート。

外部患者IDの取得・無効化は患者IDを受け取らない（識別子IDだけで足りる）。
そのため患者の下へ入れ子にせず、``/patient-external-identifiers`` に置く。
ユースケースが照合できないIDをパスへ載せると、URLが検証されない主張を持つ
（別患者のIDを混ぜても素通りする）。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from fastapi import APIRouter, Depends, Response

from app.application.patient import (
    ChangePatientBirthDateCommand,
    ChangePatientNamesCommand,
    DeactivatePatientExternalIdentifierCommand,
    GetPatientExternalIdentifierQuery,
    GetPatientQuery,
    ListPatientExternalIdentifiersQuery,
    PatientDto,
    PatientExternalIdentifierDto,
    RegisterPatientCommand,
    RegisterPatientExternalIdentifierCommand,
)
from app.presentational.dependencies import PatientUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RegisteredIdResponse, RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["patient"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterPatientRequest(RequestModel):
    """患者登録の入力。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str
    birth_date: date | None = None


class ChangePatientNamesRequest(RequestModel):
    """氏名変更の入力。"""

    last_name: str
    first_name: str
    last_name_kana: str
    first_name_kana: str


class ChangePatientBirthDateRequest(RequestModel):
    """生年月日変更の入力。``None`` は解除を意味する。"""

    birth_date: date | None = None


class RegisterExternalIdentifierRequest(RequestModel):
    """外部患者IDの登録の入力。"""

    system_name: str
    external_patient_id: str


@router.post(
    "/patients",
    status_code=HTTPStatus.CREATED,
    response_model=RegisteredIdResponse,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_patient(
    corporate_id: str,
    body: RegisterPatientRequest,
    use_cases: PatientUseCasesDep,
) -> RegisteredIdResponse:
    """患者を新規登録する。"""
    patient_id = await use_cases.register.execute(
        RegisterPatientCommand(
            corporate_id=corporate_id,
            last_name=body.last_name,
            first_name=body.first_name,
            last_name_kana=body.last_name_kana,
            first_name_kana=body.first_name_kana,
            birth_date=body.birth_date,
        )
    )
    return RegisteredIdResponse(id=str(patient_id.value))


@router.get("/patients/{patient_id}", response_model=PatientDto)
async def get_patient(
    corporate_id: str,
    patient_id: str,
    use_cases: PatientUseCasesDep,
) -> PatientDto:
    """患者を1件取得する。"""
    return await use_cases.get.execute(
        GetPatientQuery(corporate_id=corporate_id, patient_id=patient_id)
    )


@router.patch(
    "/patients/{patient_id}/names",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_patient_names(
    corporate_id: str,
    patient_id: str,
    body: ChangePatientNamesRequest,
    use_cases: PatientUseCasesDep,
) -> None:
    """氏名を変更する。"""
    await use_cases.change_names.execute(
        ChangePatientNamesCommand(
            corporate_id=corporate_id,
            patient_id=patient_id,
            last_name=body.last_name,
            first_name=body.first_name,
            last_name_kana=body.last_name_kana,
            first_name_kana=body.first_name_kana,
        )
    )


@router.patch(
    "/patients/{patient_id}/birth-date",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def change_patient_birth_date(
    corporate_id: str,
    patient_id: str,
    body: ChangePatientBirthDateRequest,
    use_cases: PatientUseCasesDep,
) -> None:
    """生年月日を変更または解除する。"""
    await use_cases.change_birth_date.execute(
        ChangePatientBirthDateCommand(
            corporate_id=corporate_id,
            patient_id=patient_id,
            birth_date=body.birth_date,
        )
    )


@router.post(
    "/patients/{patient_id}/external-identifiers",
    status_code=HTTPStatus.CREATED,
    response_model=PatientExternalIdentifierDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_external_identifier(
    corporate_id: str,
    patient_id: str,
    body: RegisterExternalIdentifierRequest,
    use_cases: PatientUseCasesDep,
) -> PatientExternalIdentifierDto:
    """外部システムの患者IDを紐付ける。"""
    return await use_cases.register_external_identifier.execute(
        RegisterPatientExternalIdentifierCommand(
            corporate_id=corporate_id,
            patient_id=patient_id,
            system_name=body.system_name,
            external_patient_id=body.external_patient_id,
        )
    )


@router.get(
    "/patients/{patient_id}/external-identifiers",
    response_model=list[PatientExternalIdentifierDto],
)
async def list_external_identifiers(
    corporate_id: str,
    patient_id: str,
    use_cases: PatientUseCasesDep,
) -> list[PatientExternalIdentifierDto]:
    """患者に紐付いた外部患者IDを一覧する。"""
    return await use_cases.list_external_identifiers.execute(
        ListPatientExternalIdentifiersQuery(
            corporate_id=corporate_id, patient_id=patient_id
        )
    )


@router.get(
    "/patient-external-identifiers/{identifier_id}",
    response_model=PatientExternalIdentifierDto,
)
async def get_external_identifier(
    corporate_id: str,
    identifier_id: str,
    use_cases: PatientUseCasesDep,
) -> PatientExternalIdentifierDto:
    """外部患者IDを1件取得する。"""
    return await use_cases.get_external_identifier.execute(
        GetPatientExternalIdentifierQuery(
            corporate_id=corporate_id, identifier_id=identifier_id
        )
    )


@router.post(
    "/patient-external-identifiers/{identifier_id}/deactivation",
    status_code=HTTPStatus.NO_CONTENT,
    response_class=Response,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def deactivate_external_identifier(
    corporate_id: str,
    identifier_id: str,
    use_cases: PatientUseCasesDep,
) -> None:
    """外部患者IDを無効化する。

    無効化した外部IDは他の患者へ付け替えられる。誤った紐付けを直すための操作で
    あり、その外部IDを恒久的に使えなくするものではない。
    """
    await use_cases.deactivate_external_identifier.execute(
        DeactivatePatientExternalIdentifierCommand(
            corporate_id=corporate_id, identifier_id=identifier_id
        )
    )


__all__ = ["router"]
