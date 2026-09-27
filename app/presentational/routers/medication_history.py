"""薬歴コンテキストのHTTPルート。

頭書き（``medical-profile``）に個別の編集ルートを作らない。頭書きは薬歴からの
投影であり、薬歴に由来しない要素を作れると再構築できなくなる。書き込みは薬歴側の
``profile_updates`` と、薬歴から作り直す ``rebuild`` の2つだけとする。

確定済みの薬歴は上書きしない。訂正は ``amendments`` として積み、元の記載を残す。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from http import HTTPStatus
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.application.care_event.create_event import CreateEventCommand
from app.application.care_event.get_event import GetEventQuery
from app.application.common.exceptions import NotFoundError
from app.application.common.pagination import Page
from app.application.dispensing.get_dispensing import GetDispensingQuery
from app.application.medication_history.amend_medication_history import (
    AmendMedicationHistoryCommand,
)
from app.application.medication_history.category_catalog import CategoryCatalogDto
from app.application.medication_history.correct_medication_history_fact import (
    CorrectMedicationHistoryFactCommand,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
)
from app.application.medication_history.get_medication_history import (
    GetFollowUpSourceQuery,
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
from app.application.medication_history.list_pending_external_corrections import (
    ListPendingExternalCorrectionsQuery,
    PendingExternalCorrectionDto,
)
from app.application.medication_history.review_external_prescription_correction import (
    ReviewExternalPrescriptionCorrectionCommand,
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
    CareEventUseCasesDep,
    DispensingUseCasesDep,
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
    soap: SoapInput = Field(default_factory=SoapInput)
    method: str | None = None
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    profile_updates: ProfileUpdateInput | None = None
    counselor_id: str | None = None
    counseled_at: datetime | None = None
    occurred_at: datetime


class StartEventMedicationHistoryRequest(RequestModel):
    """既存Eventから薬歴下書きを起こす入力。"""

    soap: SoapInput = Field(default_factory=SoapInput)
    method: str | None = None
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    profile_updates: ProfileUpdateInput | None = None
    additional_notes: tuple[CategorizedNoteInput, ...] = ()
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
    event_occurred_at: datetime | None = None
    delay_reason: str | None = None
    review_result: str | None = None


class AmendMedicationHistoryRequest(RequestModel):
    """確定済み薬歴の訂正の入力。元の記載は残り、訂正が積まれる。"""

    amended_by: str
    reason: str
    amended_soap: SoapInput


class CorrectMedicationHistoryFactRequest(RequestModel):
    """確定済み薬歴の事実訂正。訂正者と時刻はサーバ側で決める。"""

    target: str
    operation: Literal["replace", "retract", "append"] = "replace"
    reason: str
    value: object | None = None


class ReviewExternalPrescriptionCorrectionRequest(RequestModel):
    """外部訂正判断の入力。監査担当者と処理時刻は指定できない。"""

    decision: Literal[
        "amend",
        "no_action",
        "investigating",
        "match_reregistered_prescription",
    ]
    reason: str
    amended_soap: SoapInput | None = None
    matched_prescription_id: str | None = None


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
    event_use_cases: CareEventUseCasesDep,
    dispensing_use_cases: DispensingUseCasesDep,
) -> MedicationHistoryDto:
    """既存の初回薬歴入口をEvent作成と薬歴起票へ接続する。"""
    dispensing = await dispensing_use_cases.get.execute(
        GetDispensingQuery(
            corporate_id=corporate_id,
            dispensing_id=body.dispensing_id,
        )
    )
    definitions = await event_use_cases.list_definitions.execute(corporate_id)
    definition = next(
        (
            item
            for item in definitions
            if item.standard_code == "prescription_reception"
        ),
        None,
    )
    if definition is None:
        raise RuntimeError("標準の処方箋受付Event種別が登録されていません。")
    event = await event_use_cases.create.execute(
        CreateEventCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            patient_id=dispensing.patient_id,
            event_type_id=definition.id,
            occurred_at=body.occurred_at,
            reception_id=body.reception_id,
            prescription_id=dispensing.prescription_id,
            dispensing_id=dispensing.id,
        )
    )
    if event.medication_history_id is not None:
        return await use_cases.get.execute(
            GetMedicationHistoryQuery(
                corporate_id=corporate_id,
                record_id=event.medication_history_id,
            )
        )
    return await use_cases.start.execute(
        StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            event_id=event.event_id,
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


@router.post(
    "/events/{event_id}/medication-history",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def start_event_medication_history(
    corporate_id: str,
    event_id: str,
    body: StartEventMedicationHistoryRequest,
    use_cases: MedicationHistoryUseCasesDep,
    event_use_cases: CareEventUseCasesDep,
) -> MedicationHistoryDto:
    """指定Eventに対する共通薬歴下書きを作成する。"""
    event = await event_use_cases.get.execute(
        GetEventQuery(corporate_id=corporate_id, event_id=event_id)
    )
    return await use_cases.start.execute(
        StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=event.store_id,
            event_id=event.event_id,
            dispensing_id=event.dispensing_id,
            method=body.method,
            soap=body.soap,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            profile_updates=body.profile_updates,
            counselor_id=body.counselor_id,
            counseled_at=body.counseled_at,
            reception_id=event.reception_id,
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


@router.get(
    "/medication-history-external-corrections",
)
async def list_external_prescription_corrections(
    corporate_id: str,
    use_cases: MedicationHistoryUseCasesDep,
    store_id: str | None = None,
    status: Literal["pending", "investigating", "resolved"] | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> Page[PendingExternalCorrectionDto]:
    """薬歴の外部訂正を法人・店舗・状態でページ取得する。"""
    return await use_cases.list_external_corrections.execute(
        ListPendingExternalCorrectionsQuery(
            corporate_id=corporate_id,
            store_id=store_id,
            status=status,
            cursor=cursor,
            limit=limit,
        )
    )


@router.post(
    "/medication-histories/{record_id}/external-corrections/{correction_id}/reviews",
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def review_external_prescription_correction(
    corporate_id: str,
    record_id: str,
    correction_id: str,
    body: ReviewExternalPrescriptionCorrectionRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """外部訂正に理由付き判断を記録し、元の確定記録は保持する。"""
    return await use_cases.review_external_correction.execute(
        ReviewExternalPrescriptionCorrectionCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            correction_id=correction_id,
            decision=body.decision,
            reason=body.reason,
            amended_soap=body.amended_soap,
            matched_prescription_id=body.matched_prescription_id,
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
            event_occurred_at=(body.event_occurred_at if body is not None else None),
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
    "/medication-histories/{record_id}/corrections",
    status_code=HTTPStatus.CREATED,
    response_model=MedicationHistoryDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def correct_medication_history_fact(
    corporate_id: str,
    record_id: str,
    body: CorrectMedicationHistoryFactRequest,
    use_cases: MedicationHistoryUseCasesDep,
) -> MedicationHistoryDto:
    """原本を保ったまま事実訂正を追記し、頭書きを再投影する。"""
    command = CorrectMedicationHistoryFactCommand(
        corporate_id=corporate_id,
        record_id=record_id,
        target=body.target,
        operation=body.operation,
        reason=body.reason,
    )
    if "value" in body.model_fields_set:
        command = replace(command, value=body.value)
    return await use_cases.correct_fact.execute(command)


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
    event_use_cases: CareEventUseCasesDep,
) -> MedicationHistoryDto:
    """旧フォローアップ入口から独立Eventと薬歴を作成する。"""
    source = await use_cases.get_follow_up_source.execute(
        GetFollowUpSourceQuery(corporate_id=corporate_id, record_id=record_id)
    )
    if str(source.patient_id.value) != body.patient_id:
        raise NotFoundError(
            "指定された確定済み薬歴が見つかりません。",
            code="MEDICATION_HISTORY_NOT_FOUND",
        )
    definition = next(
        (
            item
            for item in await event_use_cases.list_definitions.execute(corporate_id)
            if item.standard_code == "medication_period_follow_up"
        ),
        None,
    )
    if definition is None:
        raise RuntimeError("標準の服薬期間中フォローアップEvent種別がありません。")
    event = await event_use_cases.create.execute(
        CreateEventCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            patient_id=body.patient_id,
            event_type_id=definition.id,
            occurred_at=body.followed_up_at,
            related_event_id=str(source.event_id.value),
        )
    )
    return await use_cases.start.execute(
        StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            event_id=event.event_id,
            dispensing_id=None,
            method=body.method,
            soap=body.soap,
            handbook_status=body.handbook_status,
            residual_drug=body.residual_drug,
            information_sheet_provided=body.information_sheet_provided,
            profile_updates=body.profile_updates,
            additional_notes=body.additional_notes,
            counselor_id=body.counselor_id,
            counseled_at=body.followed_up_at,
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
