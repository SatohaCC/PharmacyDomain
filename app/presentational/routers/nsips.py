"""NSIPS連携のHTTPルート。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, Depends, Response

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
    IngestNsipsResultDto,
)
from app.application.integration.nsips.models import (
    NsipsBundle,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)
from app.presentational.dependencies import (
    IntegrationUseCasesDep,
    get_actor_context,
)
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/corporates/{corporate_id}/stores/{store_id}/integrations/nsips",
    tags=["integration"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class IngestNsipsRequest(RequestModel):
    """NSIPS取込リクエストボディ。"""

    operator_staff_id: str
    raw_nsips_text: str | None = None
    structured_bundle: dict[str, Any] | None = None


def _build_bundle_from_dict(raw: dict[str, Any]) -> NsipsBundle:
    raw_pat = raw["patient"]
    raw_presc = raw["prescription"]

    patient = NsipsPatientInfo(
        external_patient_id=raw_pat["external_patient_id"],
        kanji_name=raw_pat["kanji_name"],
        kana_name=raw_pat["kana_name"],
        birth_date=date.fromisoformat(raw_pat["birth_date"])
        if isinstance(raw_pat["birth_date"], str)
        else raw_pat["birth_date"],
        gender=raw_pat["gender"],
        postal_code=raw_pat.get("postal_code"),
        address=raw_pat.get("address"),
        phone_number=raw_pat.get("phone_number"),
    )

    rps: list[NsipsRpInfo] = []
    for raw_rp in raw_presc.get("rps", []):
        meds: list[NsipsMedicineInfo] = []
        for raw_med in raw_rp.get("medicines", []):
            meds.append(
                NsipsMedicineInfo(
                    medicine_code=raw_med.get("medicine_code", ""),
                    medicine_name=raw_med["medicine_name"],
                    dosage=Decimal(str(raw_med["dosage"])),
                    unit=raw_med["unit"],
                )
            )
        rps.append(
            NsipsRpInfo(
                rp_number=raw_rp["rp_number"],
                group_name=raw_rp.get("group_name", "内服"),
                instructions=raw_rp.get("instructions", ""),
                dispensing_quantity=raw_rp.get("dispensing_quantity", 1),
                medicines=tuple(meds),
                preparation_method=raw_rp.get("preparation_method"),
            )
        )

    split_info = None
    if raw_presc.get("split_info"):
        raw_split = raw_presc["split_info"]
        split_info = NsipsSplitInfo(
            iteration=raw_split["iteration"],
            total_split_count=raw_split["total_split_count"],
            split_reason=raw_split["split_reason"],
        )

    prescription = NsipsPrescriptionInfo(
        document_number=raw_presc["document_number"],
        issued_date=date.fromisoformat(raw_presc["issued_date"])
        if isinstance(raw_presc["issued_date"], str)
        else raw_presc["issued_date"],
        institution_code=raw_presc["institution_code"],
        institution_name=raw_presc["institution_name"],
        department_code=raw_presc.get("department_code"),
        department_name=raw_presc.get("department_name"),
        doctor_name=raw_presc["doctor_name"],
        rps=tuple(rps),
        split_info=split_info,
    )

    return NsipsBundle(
        header_version=raw.get("header_version", "1.0"),
        patient=patient,
        prescription=prescription,
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=IngestNsipsResultDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def ingest_nsips(
    corporate_id: str,
    store_id: str,
    body: IngestNsipsRequest,
    use_cases: IntegrationUseCasesDep,
    response: Response,
) -> IngestNsipsResultDto:
    """NSIPS受付データを取り込む。"""
    bundle: NsipsBundle | None = None
    if body.structured_bundle is not None:
        bundle = _build_bundle_from_dict(body.structured_bundle)

    result = await use_cases.ingest_nsips.execute(
        IngestNsipsCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            operator_staff_id=body.operator_staff_id,
            raw_nsips_text=body.raw_nsips_text,
            structured_bundle=bundle,
        )
    )

    if result.is_duplicate:
        response.status_code = HTTPStatus.OK

    return result
