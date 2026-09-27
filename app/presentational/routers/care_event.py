"""業務Eventとイベント種別のHTTPルート。"""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.care_event.create_event import (
    CreateEventCommand,
    EventDto,
)
from app.application.care_event.event_definition import (
    CreateEventDefinitionCommand,
    EventDefinitionDto,
    UpdateEventDefinitionCommand,
)
from app.application.care_event.get_event import GetEventQuery
from app.application.care_event.list_related_candidates import (
    ListRelatedEventCandidatesQuery,
    RelatedEventCandidateDto,
)
from app.presentational.dependencies import CareEventUseCasesDep, get_actor_context
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}",
    tags=["care_event"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.CONFLICT,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class CreateEventDefinitionRequest(RequestModel):
    """法人独自イベント種別の作成入力。"""

    name: str


class UpdateEventDefinitionRequest(RequestModel):
    """法人独自イベント種別の変更入力。"""

    name: str | None = None
    is_active: bool | None = None


class CreateEventRequest(RequestModel):
    """新しい患者対応Eventの入力。"""

    store_id: str
    patient_id: str
    event_type_id: str
    occurred_at: datetime
    related_event_id: str | None = None
    reception_id: str | None = None
    prescription_id: str | None = None
    dispensing_id: str | None = None


@router.get("/event-definitions", response_model=tuple[EventDefinitionDto, ...])
async def list_event_definitions(
    corporate_id: str,
    use_cases: CareEventUseCasesDep,
) -> tuple[EventDefinitionDto, ...]:
    """標準種別と自法人の種別を返す。"""
    return await use_cases.list_definitions.execute(corporate_id)


@router.post(
    "/event-definitions",
    status_code=HTTPStatus.CREATED,
    response_model=EventDefinitionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def create_event_definition(
    corporate_id: str,
    body: CreateEventDefinitionRequest,
    use_cases: CareEventUseCasesDep,
) -> EventDefinitionDto:
    """法人独自のイベント種別を作成する。"""
    return await use_cases.create_definition.execute(
        CreateEventDefinitionCommand(corporate_id=corporate_id, name=body.name)
    )


@router.patch(
    "/event-definitions/{event_type_id}",
    response_model=EventDefinitionDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def update_event_definition(
    corporate_id: str,
    event_type_id: str,
    body: UpdateEventDefinitionRequest,
    use_cases: CareEventUseCasesDep,
) -> EventDefinitionDto:
    """法人独自のイベント種別を改名または無効化する。"""
    return await use_cases.update_definition.execute(
        UpdateEventDefinitionCommand(
            corporate_id=corporate_id,
            event_type_id=event_type_id,
            name=body.name,
            is_active=body.is_active,
        )
    )


@router.post(
    "/events",
    status_code=HTTPStatus.CREATED,
    response_model=EventDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def create_event(
    corporate_id: str,
    body: CreateEventRequest,
    use_cases: CareEventUseCasesDep,
) -> EventDto:
    """許可店舗で患者対応Eventを記録する。"""
    return await use_cases.create.execute(
        CreateEventCommand(
            corporate_id=corporate_id,
            store_id=body.store_id,
            patient_id=body.patient_id,
            event_type_id=body.event_type_id,
            occurred_at=body.occurred_at,
            related_event_id=body.related_event_id,
            reception_id=body.reception_id,
            prescription_id=body.prescription_id,
            dispensing_id=body.dispensing_id,
        )
    )


@router.get("/events/{event_id}", response_model=EventDto)
async def get_event(
    corporate_id: str,
    event_id: str,
    use_cases: CareEventUseCasesDep,
) -> EventDto:
    """Eventのメタデータと関連薬歴IDを返す。"""
    return await use_cases.get.execute(
        GetEventQuery(corporate_id=corporate_id, event_id=event_id)
    )


@router.get(
    "/patients/{patient_id}/events/related-candidates",
    response_model=tuple[RelatedEventCandidateDto, ...],
)
async def list_related_event_candidates(
    corporate_id: str,
    patient_id: str,
    store_id: Annotated[str, Query()],
    use_cases: CareEventUseCasesDep,
) -> tuple[RelatedEventCandidateDto, ...]:
    """許可店舗で選べる同一患者の関連Event候補を返す。"""
    return await use_cases.list_related_candidates.execute(
        ListRelatedEventCandidatesQuery(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
        )
    )


__all__ = ["router"]
