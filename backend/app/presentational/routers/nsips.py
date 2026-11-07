"""NSIPS連携のHTTPルート。"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import field_validator, model_validator

from app.application.integration.boundary_models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsDrugSupplementInfo,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsNarcoticInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRemarkInfo,
    NsipsRpInfo,
    NsipsRpUsageSupplementInfo,
    NsipsSplitInfo,
)
from app.application.integration.commands.dtos.ingest_nsips import IngestNsipsResultDto
from app.application.integration.commands.ingest_nsips import IngestNsipsCommand
from app.application.integration.queries.dtos.get_nsips_source import NsipsSourceDto
from app.application.integration.queries.models import GetNsipsSourceQuery
from app.presentational.dependencies import (
    IntegrationUseCasesDep,
    get_actor_context,
)
from app.presentational.errors import error_responses
from app.presentational.routing import ApplicationRoute
from app.presentational.schemas import RequestModel

router = APIRouter(
    route_class=ApplicationRoute,
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


class NsipsDrugSupplementRequest(RequestModel):
    """薬品補足情報。"""

    category_code: str
    text: str
    supplementary_usage_code: str = ""


class NsipsMedicineRequest(RequestModel):
    """構造化入力の薬品明細。"""

    medicine_code: str = ""
    medicine_name: str
    dosage: Decimal
    unit: str
    days_supply: int | None = None
    yj_code: str = ""
    info_category: str = "drug"
    drug_code_type: str = ""
    dosage_quantity: Decimal | None = None
    dosage_unit: str = ""
    is_potency: bool = False
    unit_conversion_factor: Decimal | None = None
    uneven_doses: tuple[Decimal | None, ...] = ()
    supplements: tuple[NsipsDrugSupplementRequest, ...] = ()


class NsipsRpUsageSupplementRequest(RequestModel):
    """用法補足情報。"""

    category_code: str
    text: str
    supplementary_usage_code: str = ""
    body_site_code: str = ""


class NsipsRpRequest(RequestModel):
    """構造化入力のRp。"""

    rp_number: int
    group_name: str
    instructions: str
    dispensing_quantity: int
    medicines: tuple[NsipsMedicineRequest, ...]
    preparation_method: str | None = None
    dosage_form_code: str = ""
    dosage_form_name: str = ""
    usage_code: str = ""
    daily_frequency: int | None = None
    usage_supplements: tuple[NsipsRpUsageSupplementRequest, ...] = ()


class NsipsSplitRequest(RequestModel):
    """構造化入力の分割調剤情報。"""

    iteration: int
    total_split_count: int
    split_reason: str


class NsipsNarcoticRequest(RequestModel):
    """麻薬施用情報。"""

    license_number: str
    patient_address: str
    patient_phone: str


class NsipsRemarkRequest(RequestModel):
    """処方備考情報。"""

    sequence_number: int
    remark_type_code: str = ""
    text: str


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
    expiration_date: date | None = None
    narcotic_info: NsipsNarcoticRequest | None = None
    remaining_medication_check_code: str = ""
    refill_total_uses: int | None = None
    remarks: tuple[NsipsRemarkRequest, ...] = ()


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
    category: str = "addition"


class NsipsBundleRequest(RequestModel):
    """構造化入力のNSIPS Bundle。"""

    header_version: str = "unverified"
    patient: NsipsPatientRequest
    prescription: NsipsPrescriptionRequest
    dispensed_date: date | None = None
    insurance: NsipsInsuranceRequest | None = None
    additions: tuple[NsipsAdditionRequest, ...] = ()
    correction_kind: Literal["update", "delete"] | None = None


class IngestNsipsRequest(RequestModel):
    """NSIPS取込リクエストボディ。"""

    reception_id: str | None = None
    file_name: str | None = None
    raw_nsips_text: str | None = None
    structured_bundle: NsipsBundleRequest | None = None
    expected_fingerprint: str | None = None

    @field_validator("reception_id")
    @classmethod
    def require_uuid7_reception_id(cls, value: str | None) -> str | None:
        """受付呼出元が指定する場合はUUIDv7を要求する。"""
        if value is None:
            return None
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError, TypeError) as error:
            raise ValueError("reception_idはUUIDv7で指定してください。") from error
        if parsed.version != 7:
            raise ValueError("reception_idはUUIDv7で指定してください。")
        return value

    @model_validator(mode="after")
    def validate_inputs(self) -> IngestNsipsRequest:
        """入力の整合性を検証する。"""
        if self.reception_id is None and self.file_name is None:
            raise ValueError("reception_idまたはfile_nameのどちらか一方が必要です。")
        is_deletion_file = (
            self.file_name is not None and self.file_name.strip()[:1].upper() == "D"
        )
        if not is_deletion_file and (self.raw_nsips_text is None) == (
            self.structured_bundle is None
        ):
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
                        days_supply=medicine.days_supply,
                        yj_code=medicine.yj_code,
                        info_category=medicine.info_category,
                        drug_code_type=medicine.drug_code_type,
                        dosage_quantity=medicine.dosage_quantity,
                        dosage_unit=medicine.dosage_unit,
                        is_potency=medicine.is_potency,
                        unit_conversion_factor=medicine.unit_conversion_factor,
                        uneven_doses=medicine.uneven_doses,
                        supplements=tuple(
                            NsipsDrugSupplementInfo(
                                category_code=supp.category_code,
                                text=supp.text,
                                supplementary_usage_code=supp.supplementary_usage_code,
                            )
                            for supp in medicine.supplements
                        ),
                    )
                    for medicine in rp.medicines
                ),
                preparation_method=rp.preparation_method,
                dosage_form_code=rp.dosage_form_code,
                dosage_form_name=rp.dosage_form_name,
                usage_code=rp.usage_code,
                daily_frequency=rp.daily_frequency,
                usage_supplements=tuple(
                    NsipsRpUsageSupplementInfo(
                        category_code=supp.category_code,
                        text=supp.text,
                        supplementary_usage_code=supp.supplementary_usage_code,
                        body_site_code=supp.body_site_code,
                    )
                    for supp in rp.usage_supplements
                ),
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
        expiration_date=raw.prescription.expiration_date,
        narcotic_info=(
            NsipsNarcoticInfo(
                license_number=raw.prescription.narcotic_info.license_number,
                patient_address=raw.prescription.narcotic_info.patient_address,
                patient_phone=raw.prescription.narcotic_info.patient_phone,
            )
            if raw.prescription.narcotic_info is not None
            else None
        ),
        remaining_medication_check_code=raw.prescription.remaining_medication_check_code,
        refill_total_uses=raw.prescription.refill_total_uses,
        remarks=tuple(
            NsipsRemarkInfo(
                sequence_number=rem.sequence_number,
                remark_type_code=rem.remark_type_code,
                text=rem.text,
            )
            for rem in raw.prescription.remarks
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
                category=addition.category,
            )
            for addition in raw.additions
        ),
        correction_kind=(
            raw.correction_kind if raw.correction_kind is not None else None
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
            reception_id=body.reception_id,
            raw_nsips_text=body.raw_nsips_text,
            structured_bundle=bundle,
            expected_fingerprint=body.expected_fingerprint,
            file_name=body.file_name,
        )
    )

    if result.is_duplicate or result.was_already_applied:
        response.status_code = HTTPStatus.OK

    return result


@router.get(
    "/{reception_id}",
    status_code=HTTPStatus.OK,
    response_model=NsipsSourceDto,
    responses=error_responses(HTTPStatus.NOT_FOUND),
)
async def get_nsips_source(
    corporate_id: str,
    store_id: str,
    reception_id: str,
    use_cases: IntegrationUseCasesDep,
) -> NsipsSourceDto:
    """NSIPS受付原本データを取得する。"""
    return await use_cases.get_nsips_source.execute(
        GetNsipsSourceQuery(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
    )
