"""薬歴コンテキストのHTTPルート。

頭書き（``medical-profile``）に個別の編集ルートを作らない。頭書きは薬歴からの
投影であり、薬歴に由来しない要素を作れると再構築できなくなる。書き込みは薬歴側の
``profile_updates`` と、薬歴から作り直す ``rebuild`` の2つだけとする。

確定済みの薬歴は上書きしない。訂正は ``amendments`` として積み、元の記載を残す。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.medication_history import (
    AmendMedicationHistoryCommand,
    FinalizeMedicationHistoryCommand,
    GetMedicationHistoryQuery,
    GetPatientMedicalProfileQuery,
    HandbookStatusInput,
    ListMedicationHistoriesQuery,
    MedicationHistoryDto,
    PatientMedicalProfileDto,
    ProfileUpdateInput,
    RebuildPatientMedicalProfileCommand,
    ResidualDrugInput,
    SoapInput,
    StartMedicationHistoryCommand,
    UpdateMedicationHistoryDraftCommand,
)
from app.presentational.dependencies import (
    MedicationHistoryUseCasesDep,
    get_actor_context,
)
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["medication_history"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class StartMedicationHistoryRequest(RequestModel):
    """薬歴の起票の入力。"""

    store_id: str
    dispensing_id: str
    counselor_id: str
    method: str
    soap: SoapInput
    handbook_status: HandbookStatusInput
    residual_drug: ResidualDrugInput
    information_sheet_provided: bool = False
    profile_updates: ProfileUpdateInput | None = None


class UpdateMedicationHistoryDraftRequest(RequestModel):
    """下書きの更新の入力。送られた内容で SOAP を置き換える。"""

    soap: SoapInput
    profile_updates: ProfileUpdateInput | None = None


class AmendMedicationHistoryRequest(RequestModel):
    """確定済み薬歴の訂正の入力。元の記載は残り、訂正が積まれる。"""

    amended_by: str
    reason: str
    amended_soap: SoapInput


class RebuildMedicalProfileRequest(RequestModel):
    """頭書きの再構築の入力。"""

    as_of: date


@router.post(
    "/medication-histories",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def start_medication_history(
    corporate_id: str,
    body: StartMedicationHistoryRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """完了した調剤に対する薬歴を起票する。"""
    return await use_cases.start.execute(
        StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            dispensing_id=body.dispensing_id,
            counselor_id=body.counselor_id,
            method=body.method,
            soap=body.soap,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            profile_updates=body.profile_updates,
        )
    )


@router.get(
    "/medication-histories/{record_id}",
    response_model=MedicationHistoryDto,
)
async def get_medication_history(
    corporate_id: str,
    record_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """薬歴を1件取得する。"""
    return await use_cases.get.execute(
        GetMedicationHistoryQuery(corporate_id=corporate_id, record_id=record_id)
    )


@router.put(
    "/medication-histories/{record_id}/draft",
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def update_medication_history_draft(
    corporate_id: str,
    record_id: str,
    body: UpdateMedicationHistoryDraftRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """下書きを更新する。確定済みの薬歴には使えない。"""
    return await use_cases.update_draft.execute(
        UpdateMedicationHistoryDraftCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            soap=body.soap,
            profile_updates=body.profile_updates,
        )
    )


@router.post(
    "/medication-histories/{record_id}/finalization",
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def finalize_medication_history(
    corporate_id: str,
    record_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """薬歴を確定する。頭書きへの投影も同じトランザクションで確定する。"""
    return await use_cases.finalize.execute(
        FinalizeMedicationHistoryCommand(corporate_id=corporate_id, record_id=record_id)
    )


@router.post(
    "/medication-histories/{record_id}/amendments",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def amend_medication_history(
    corporate_id: str,
    record_id: str,
    body: AmendMedicationHistoryRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """確定済みの薬歴を訂正する。元の記載は消えず、訂正として積まれる。"""
    return await use_cases.amend.execute(
        AmendMedicationHistoryCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            amended_by=body.amended_by,
            reason=body.reason,
            amended_soap=body.amended_soap,
        )
    )


@router.get(
    "/patients/{patient_id}/medication-histories",
    response_model=list[MedicationHistoryDto],
)
async def list_medication_histories(
    corporate_id: str,
    patient_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> list[MedicationHistoryDto]:
    """患者の薬歴を一覧する。"""
    records = await use_cases.list_by_patient.execute(
        ListMedicationHistoriesQuery(corporate_id=corporate_id, patient_id=patient_id)
    )
    return list(records)


@router.get(
    "/patients/{patient_id}/medical-profile",
    response_model=PatientMedicalProfileDto,
)
async def get_medical_profile(
    corporate_id: str,
    patient_id: str,
    use_cases: MedicationHistoryUseCasesDep,
    as_of: Annotated[date, Query(description="併用薬の継続判定に使う基準日。")],
) -> PatientMedicalProfileDto:
    """頭書きを取得する。継続中の併用薬は基準日で判定する。"""
    return await use_cases.get_medical_profile.execute(
        GetPatientMedicalProfileQuery(
            corporate_id=corporate_id, patient_id=patient_id, as_of=as_of
        )
    )


@router.post(
    "/patients/{patient_id}/medical-profile/rebuild",
    response_model=PatientMedicalProfileDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def rebuild_medical_profile(
    corporate_id: str,
    patient_id: str,
    body: RebuildMedicalProfileRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> PatientMedicalProfileDto:
    """確定済みの薬歴から頭書きを作り直す。"""
    return await use_cases.rebuild_medical_profile.execute(
        RebuildPatientMedicalProfileCommand(
            corporate_id=corporate_id, patient_id=patient_id, as_of=body.as_of
        )
    )


__all__ = ["router"]
