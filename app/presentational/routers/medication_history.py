"""薬歴コンテキストのHTTPルート。

頭書き（``medical-profile``）に個別の編集ルートを作らない。頭書きは薬歴からの
投影であり、薬歴に由来しない要素を作れると再構築できなくなる。書き込みは薬歴側の
``profile_updates`` と、薬歴から作り直す ``rebuild`` の2つだけとする。

確定済みの薬歴は上書きしない。訂正は ``amendments`` として積み、元の記載を残す。
"""

from __future__ import annotations

from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryCommand,
)
from app.application.medication_history.category_catalog import CategoryCatalogDto
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_follow_up_sources import (
    FollowUpSourceDto,
    GetFollowUpSourcesQuery,
)
from app.application.medication_history.get_medication_history import (
    GetMedicationHistoryQuery,
    ListMedicationHistoriesQuery,
    MedicationHistoryDto,
)
from app.application.medication_history.get_medication_history_view import (
    GetMedicationHistoryViewQuery,
    MedicationHistoryViewDto,
)
from app.application.medication_history.get_patient_medical_profile import (
    GetPatientMedicalProfileQuery,
    PatientMedicalProfileDto,
    RebuildPatientMedicalProfileCommand,
)
from app.application.medication_history.inputs import (
    AddFollowUpCommand,
    BillingAdditionInput,
    CategorizedNoteInput,
    HandbookStatusInput,
    MajorCategoryInput,
    MediumCategoryInput,
    ProfileUpdateInput,
    RecordTracingReportCommand,
    RecordTracingReportResponseCommand,
    ResidualDrugInput,
    SoapInput,
    UpdateCategoryCatalogCommand,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryCommand,
)
from app.application.medication_history.update_medication_history_draft import (
    UpdateMedicationHistoryDraftCommand,
)
from app.application.medication_history.verify_statutory_record import (
    StatutoryRecordSufficiencyDto,
    VerifyStatutoryRecordQuery,
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
    """薬歴の初回保存の入力。"""

    store_id: str
    dispensing_id: str
    reception_id: str | None = None
    soap: SoapInput
    method: str | None = None
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    profile_updates: ProfileUpdateInput | None = None
    counselor_id: str | None = None
    counseled_at: datetime | None = None


class BillingAdditionRequest(RequestModel):
    """下書き編集で受け取る算定加算。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None


class UpdateMedicationHistoryDraftRequest(RequestModel):
    """下書きの更新の入力。"""

    soap: SoapInput | None = None
    profile_updates: ProfileUpdateInput | None = None
    method: str | None = None
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    additional_notes: tuple[CategorizedNoteInput, ...] | None = None
    billing_additions: tuple[BillingAdditionRequest, ...] | None = None


class FinalizeMedicationHistoryRequest(RequestModel):
    """薬歴確定の入力。"""

    counseled_at: datetime | None = None
    delay_reason: str | None = None
    review_result: str | None = None


class AmendMedicationHistoryRequest(RequestModel):
    """確定済み薬歴の訂正の入力。元の記載は残り、訂正が積まれる。"""

    amended_by: str
    reason: str
    amended_soap: SoapInput


class AddFollowUpRequest(RequestModel):
    """フォローアップ記録の追加入力。"""

    store_id: str
    patient_id: str
    counselor_id: str
    followed_up_at: datetime
    method: str
    soap: SoapInput = Field(default_factory=SoapInput)
    additional_notes: tuple[CategorizedNoteInput, ...] = ()
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    profile_updates: ProfileUpdateInput | None = None


class RecordTracingReportRequest(RequestModel):
    """トレーシングレポート記録の入力。"""

    reporter_id: str
    provided_at: datetime
    medical_institution_name: str
    physician_name: str
    category: str
    fee_category: str
    delivery_method: str
    content: str
    follow_up_id: str | None = None


class RecordTracingReportResponseRequest(RequestModel):
    """トレーシングレポート医師返答の入力。"""

    responded_at: datetime
    content: str
    action_type: str
    received_by: str
    acknowledged_physician_name: str | None = None


class RebuildMedicalProfileRequest(RequestModel):
    """頭書きの再構築の入力。"""

    as_of: date


class UpdateCategoryCatalogRequest(RequestModel):
    """区分カタログの更新入力。"""

    major_categories: tuple[MajorCategoryInput, ...] = ()
    medium_categories: tuple[MediumCategoryInput, ...] = ()


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
    """薬剤師が記入した薬歴を初回保存する。"""
    return await use_cases.start.execute(
        StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            dispensing_id=body.dispensing_id,
            reception_id=body.reception_id,
            method=body.method,
            soap=body.soap,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            profile_updates=body.profile_updates,
            counselor_id=body.counselor_id,
            counseled_at=body.counseled_at,
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


@router.get(
    "/medication-histories/{record_id}/view",
    response_model=MedicationHistoryViewDto,
)
async def get_medication_history_view(
    corporate_id: str,
    record_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryViewDto:
    """薬歴本文と読取時点の患者プロフィールを返す。"""
    return await use_cases.get_view.execute(
        GetMedicationHistoryViewQuery(
            corporate_id=corporate_id,
            record_id=record_id,
        )
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
            method=body.method,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            additional_notes=body.additional_notes,
            billing_additions=(
                tuple(
                    BillingAdditionInput(
                        code=item.code,
                        name=item.name,
                        points=item.points,
                        quantity=item.quantity,
                    )
                    for item in body.billing_additions
                )
                if body.billing_additions is not None
                else None
            ),
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
    body: FinalizeMedicationHistoryRequest | None = None,
) -> MedicationHistoryDto:
    """薬歴を確定する。頭書きへの投影も同じトランザクションで確定する。"""
    return await use_cases.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            counseled_at=body.counseled_at if body is not None else None,
            delay_reason=body.delay_reason if body is not None else None,
            review_result=body.review_result if body is not None else None,
        )
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


@router.post(
    "/medication-histories/{record_id}/follow-ups",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)
async def add_follow_up(
    corporate_id: str,
    record_id: str,
    body: AddFollowUpRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """服薬期間中のフォローアップ記録を追加する。"""
    return await use_cases.add_follow_up.execute(
        AddFollowUpCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            store_id=body.store_id,
            patient_id=body.patient_id,
            counselor_id=body.counselor_id,
            followed_up_at=body.followed_up_at,
            method=body.method,
            soap=body.soap,
            additional_notes=body.additional_notes,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            profile_updates=body.profile_updates,
        )
    )


@router.post(
    "/medication-histories/{record_id}/tracing-reports",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)
async def record_tracing_report(
    corporate_id: str,
    record_id: str,
    body: RecordTracingReportRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """確定済み薬歴に処方医へのトレーシングレポート記録を追加する。"""
    return await use_cases.record_tracing_report.execute(
        RecordTracingReportCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            reporter_id=body.reporter_id,
            provided_at=body.provided_at,
            medical_institution_name=body.medical_institution_name,
            physician_name=body.physician_name,
            category=body.category,
            fee_category=body.fee_category,
            delivery_method=body.delivery_method,
            content=body.content,
            follow_up_id=body.follow_up_id,
        )
    )


@router.post(
    "/medication-histories/{record_id}/tracing-reports/{report_id}/response",
    status_code=HTTPStatus.OK,
    response_model=MedicationHistoryDto,
    responses=error_responses(
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)
async def record_tracing_report_response(
    corporate_id: str,
    record_id: str,
    report_id: str,
    body: RecordTracingReportResponseRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """トレーシングレポートに対する処方医からの返答を記録する。"""
    return await use_cases.record_tracing_report_response.execute(
        RecordTracingReportResponseCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            tracing_report_id=report_id,
            responded_at=body.responded_at,
            content=body.content,
            action_type=body.action_type,
            received_by=body.received_by,
            acknowledged_physician_name=body.acknowledged_physician_name,
        )
    )


@router.get(
    "/medication-histories/{record_id}/statutory-record-sufficiency",
    response_model=StatutoryRecordSufficiencyDto,
)
async def verify_statutory_record(
    corporate_id: str,
    record_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> StatutoryRecordSufficiencyDto:
    """薬歴が調剤録の記載事項を満たすかを確認する。

    足りないものを報告するだけで、確定や交付は止めない。
    """
    return await use_cases.verify_statutory_record.execute(
        VerifyStatutoryRecordQuery(corporate_id=corporate_id, record_id=record_id)
    )


@router.get(
    "/patients/{patient_id}/medication-histories/follow-up-sources",
    response_model=tuple[FollowUpSourceDto, ...],
)
async def get_follow_up_sources(
    corporate_id: str,
    patient_id: str,
    store_id: Annotated[str, Query()],
    use_cases: MedicationHistoryUseCasesDep,
) -> tuple[FollowUpSourceDto, ...]:
    """独立フォローアップの参照候補を本文なしで返す。"""
    return await use_cases.get_follow_up_sources.execute(
        GetFollowUpSourcesQuery(
            corporate_id=corporate_id,
            patient_id=patient_id,
            store_id=store_id,
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


@router.get(
    "/medication-history-category-catalog",
    response_model=CategoryCatalogDto,
)
async def get_medication_history_category_catalog(
    corporate_id: str,
    use_cases: MedicationHistoryUseCasesDep,
) -> CategoryCatalogDto:
    """法人の薬歴記載区分カタログを取得する。"""
    return await use_cases.get_category_catalog.execute(corporate_id)


@router.put(
    "/medication-history-category-catalog",
    response_model=CategoryCatalogDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def update_medication_history_category_catalog(
    corporate_id: str,
    body: UpdateCategoryCatalogRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> CategoryCatalogDto:
    """法人の薬歴記載区分カタログを更新する。"""
    return await use_cases.update_category_catalog.execute(
        UpdateCategoryCatalogCommand(
            corporate_id=corporate_id,
            major_categories=body.major_categories,
            medium_categories=body.medium_categories,
        )
    )


__all__ = ["router"]
