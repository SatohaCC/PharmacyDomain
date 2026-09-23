"""NSIPS連携のHTTPルート。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import model_validator

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
    IngestNsipsResultDto,
)
from app.application.integration.nsips.models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
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


class NsipsPatientRequest(RequestModel):
    """構造化入力の患者情報。"""

    external_patient_id: str
    kanji_name: str
    kana_name: str
    birth_date: date
    gender: str | None = None
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None


class NsipsMedicineRequest(RequestModel):
    """構造化入力の薬品明細。"""

    medicine_code: str = ""
    medicine_name: str
    dosage: Decimal
    unit: str


class NsipsRpRequest(RequestModel):
    """構造化入力のRp。"""

    rp_number: int
    group_name: str
    instructions: str
    dispensing_quantity: int
    medicines: tuple[NsipsMedicineRequest, ...]
    preparation_method: str | None = None


class NsipsSplitRequest(RequestModel):
    """構造化入力の分割調剤情報。"""

    iteration: int
    total_split_count: int
    split_reason: str


class NsipsPrescriptionRequest(RequestModel):
    """構造化入力の処方情報。"""

    document_number: str
    issued_date: date
    institution_code: str
    institution_name: str
    department_code: str | None = None
    department_name: str | None = None
    doctor_name: str
    institution_prefecture_code: str | None = None
    doctor_kana: str | None = None
    rps: tuple[NsipsRpRequest, ...]
    split_info: NsipsSplitRequest | None = None


class NsipsInsuranceRequest(RequestModel):
    """構造化入力の保険・公費情報。"""

    insurer_number: str
    insured_symbol: str
    insured_number: str
    branch_number: str | None = None
    insured_type: Literal["self", "family"] | None = None
    benefit_ratio: int | None = None
    public_payer_number_1: str | None = None
    public_recipient_number_1: str | None = None
    public_payer_number_2: str | None = None
    public_recipient_number_2: str | None = None


class NsipsAdditionRequest(RequestModel):
    """構造化入力の算定加算情報。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None


class NsipsBundleRequest(RequestModel):
    """構造化入力のNSIPS Bundle。"""

    header_version: str = "unverified"
    patient: NsipsPatientRequest
    prescription: NsipsPrescriptionRequest
    dispensed_date: date | None = None
    insurance: NsipsInsuranceRequest | None = None
    additions: tuple[NsipsAdditionRequest, ...] = ()


class IngestNsipsRequest(RequestModel):
    """NSIPS取込リクエストボディ。"""

    operator_staff_id: str
    raw_nsips_text: str | None = None
    structured_bundle: NsipsBundleRequest | None = None

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> IngestNsipsRequest:
        """rawと構造化入力の片方だけが指定されていることを検証する。"""
        if (self.raw_nsips_text is None) == (self.structured_bundle is None):
            raise ValueError(
                "raw_nsips_textかstructured_bundleのどちらか一方が必要です。"
            )
        return self


def _build_bundle_from_request(raw: NsipsBundleRequest) -> NsipsBundle:
    """型検証済みリクエストからアプリケーションBundleを組み立てる。"""
    patient = NsipsPatientInfo(
        external_patient_id=raw.patient.external_patient_id,
        kanji_name=raw.patient.kanji_name,
        kana_name=raw.patient.kana_name,
        birth_date=raw.patient.birth_date,
        gender=raw.patient.gender,
        postal_code=raw.patient.postal_code,
        address=raw.patient.address,
        phone_number=raw.patient.phone_number,
    )
    prescription = NsipsPrescriptionInfo(
        document_number=raw.prescription.document_number,
        issued_date=raw.prescription.issued_date,
        institution_code=raw.prescription.institution_code,
        institution_name=raw.prescription.institution_name,
        department_code=raw.prescription.department_code,
        department_name=raw.prescription.department_name,
        doctor_name=raw.prescription.doctor_name,
        institution_prefecture_code=raw.prescription.institution_prefecture_code,
        doctor_kana=raw.prescription.doctor_kana,
        rps=tuple(
            NsipsRpInfo(
                rp_number=rp.rp_number,
                group_name=rp.group_name,
                instructions=rp.instructions,
                dispensing_quantity=rp.dispensing_quantity,
                medicines=tuple(
                    NsipsMedicineInfo(
                        medicine_code=medicine.medicine_code,
                        medicine_name=medicine.medicine_name,
                        dosage=medicine.dosage,
                        unit=medicine.unit,
                    )
                    for medicine in rp.medicines
                ),
                preparation_method=rp.preparation_method,
            )
            for rp in raw.prescription.rps
        ),
        split_info=(
            NsipsSplitInfo(
                iteration=raw.prescription.split_info.iteration,
                total_split_count=raw.prescription.split_info.total_split_count,
                split_reason=raw.prescription.split_info.split_reason,
            )
            if raw.prescription.split_info is not None
            else None
        ),
    )
    insurance = (
        NsipsInsuranceInfo(
            insurer_number=raw.insurance.insurer_number,
            insured_symbol=raw.insurance.insured_symbol,
            insured_number=raw.insurance.insured_number,
            branch_number=raw.insurance.branch_number,
            insured_type=raw.insurance.insured_type,
            benefit_ratio=raw.insurance.benefit_ratio,
            public_payer_number_1=raw.insurance.public_payer_number_1,
            public_recipient_number_1=raw.insurance.public_recipient_number_1,
            public_payer_number_2=raw.insurance.public_payer_number_2,
            public_recipient_number_2=raw.insurance.public_recipient_number_2,
        )
        if raw.insurance is not None
        else None
    )
    return NsipsBundle(
        header_version=raw.header_version,
        patient=patient,
        prescription=prescription,
        dispensed_date=raw.dispensed_date,
        insurance=insurance,
        additions=tuple(
            NsipsAdditionInfo(
                code=addition.code,
                name=addition.name,
                points=addition.points,
                quantity=addition.quantity,
            )
            for addition in raw.additions
        ),
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
    bundle = (
        _build_bundle_from_request(body.structured_bundle)
        if body.structured_bundle is not None
        else None
    )

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
