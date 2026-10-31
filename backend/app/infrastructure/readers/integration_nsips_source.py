"""ReceptionRepositoryからNSIPS原本参照用DTOを投影するアダプタ。"""

from __future__ import annotations

import json

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.integration.interfaces.get_nsips_source_query_reader import (
    GetNsipsSourceQueryReader,
)
from app.application.integration.queries.dtos.get_nsips_source import (
    NsipsSourceAdditionDto,
    NsipsSourceCorrectionDto,
    NsipsSourceDto,
    NsipsSourceInsuranceDto,
    NsipsSourceMedicineDto,
    NsipsSourcePrescriptionDto,
    NsipsSourceRpDto,
)
from app.application.integration.queries.models import GetNsipsSourceQuery
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.primitives import ExternalCorrectionStatus
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.repositories import ReceptionRepository
from app.domain.store.identifiers import StoreId


class PostgresGetNsipsSourceQueryReader(GetNsipsSourceQueryReader):
    """受付集約からNSIPS原本DTOを構築するReader実装。"""

    def __init__(
        self,
        reception_repository: ReceptionRepository,
        medication_history_repository: MedicationHistoryRepository | None = None,
    ) -> None:
        self._reception_repository = reception_repository
        self._medication_history_repository = medication_history_repository

    async def read(self, query: GetNsipsSourceQuery) -> NsipsSourceDto:
        """指定された受付IDの原本データを返す。他店舗または未存在は404。"""
        corporate_id = CorporateId.parse(query.corporate_id)
        store_id = StoreId.parse(query.store_id)
        reception_id = ReceptionId.parse(query.reception_id)

        reception = await self._reception_repository.get(
            corporate_id=corporate_id, store_id=store_id, reception_id=reception_id
        )
        if reception is None:
            raise TenantBoundaryNotFoundError()

        prescription_dto: NsipsSourcePrescriptionDto | None = None
        insurance_dto: NsipsSourceInsuranceDto | None = None
        additions_dtos: list[NsipsSourceAdditionDto] = []
        dispensed_date_str: str | None = None
        imported_at_str: str = ""

        if reception.source_data is not None:
            imported_at_str = reception.source_data.imported_at.isoformat()
            bundle = json.loads(reception.source_data.bundle_json.value)
            dispensed_date_str = bundle.get("dispensed_date")

            presc_data = bundle.get("prescription")
            if presc_data:
                rps_dtos: list[NsipsSourceRpDto] = []
                for rp in presc_data.get("rps", ()):
                    meds = tuple(
                        NsipsSourceMedicineDto(
                            medicine_code=m.get("medicine_code", ""),
                            medicine_name=m.get("medicine_name", ""),
                            dosage=str(m.get("dosage", "")),
                            unit=m.get("unit", ""),
                        )
                        for m in rp.get("medicines", ())
                    )
                    rps_dtos.append(
                        NsipsSourceRpDto(
                            rp_number=rp.get("rp_number", 0),
                            group_name=rp.get("group_name", ""),
                            instructions=rp.get("instructions", ""),
                            dispensing_quantity=rp.get("dispensing_quantity", 0),
                            medicines=meds,
                            preparation_method=rp.get("preparation_method"),
                        )
                    )
                prescription_dto = NsipsSourcePrescriptionDto(
                    document_number=presc_data.get("document_number", ""),
                    issued_date=presc_data.get("issued_date", ""),
                    institution_code=presc_data.get("institution_code", ""),
                    institution_name=presc_data.get("institution_name", ""),
                    department_code=presc_data.get("department_code"),
                    department_name=presc_data.get("department_name"),
                    doctor_name=presc_data.get("doctor_name", ""),
                    institution_prefecture_code=presc_data.get(
                        "institution_prefecture_code"
                    ),
                    doctor_kana=presc_data.get("doctor_kana"),
                    rps=tuple(rps_dtos),
                )

            ins_data = bundle.get("insurance")
            if ins_data:
                insurance_dto = NsipsSourceInsuranceDto(
                    insurer_number=ins_data.get("insurer_number", ""),
                    insured_symbol=ins_data.get("insured_symbol", ""),
                    insured_number=ins_data.get("insured_number", ""),
                    branch_number=ins_data.get("branch_number"),
                    insured_type=ins_data.get("insured_type"),
                    benefit_ratio=ins_data.get("benefit_ratio"),
                    public_payer_number_1=ins_data.get("public_payer_number_1"),
                    public_recipient_number_1=ins_data.get("public_recipient_number_1"),
                    public_payer_number_2=ins_data.get("public_payer_number_2"),
                    public_recipient_number_2=ins_data.get("public_recipient_number_2"),
                )

            for add in bundle.get("additions", ()):
                additions_dtos.append(
                    NsipsSourceAdditionDto(
                        code=add.get("code", ""),
                        name=add.get("name", ""),
                        points=add.get("points"),
                        quantity=add.get("quantity"),
                    )
                )

        has_pending_review = False
        if (
            reception.medication_history_id is not None
            and self._medication_history_repository is not None
        ):
            history = await self._medication_history_repository.get(
                corporate_id=corporate_id,
                record_id=reception.medication_history_id,
            )
            if history is not None:
                has_pending_review = any(
                    c.status is not ExternalCorrectionStatus.RESOLVED
                    and not c.is_acknowledged
                    for c in history.external_corrections
                )

        corrections_dtos = tuple(
            NsipsSourceCorrectionDto(
                fingerprint=c.fingerprint.value,
                changed_fields=tuple(f.value for f in c.changed_fields),
                received_at=c.received_at.isoformat(),
            )
            for c in reception.correction_history
        )

        return NsipsSourceDto(
            reception_id=str(reception.id.value),
            corporate_id=str(corporate_id.value),
            store_id=str(store_id.value),
            patient_id=str(reception.patient_id.value),
            source_fingerprint=reception.latest_fingerprint.value,
            source_status=reception.source_status.value,
            imported_at=imported_at_str,
            prescription=prescription_dto,
            dispensed_date=dispensed_date_str,
            insurance=insurance_dto,
            additions=tuple(additions_dtos),
            correction_history=corrections_dtos,
            event_id=str(reception.event_id.value) if reception.event_id else None,
            medication_history_id=str(reception.medication_history_id.value)
            if reception.medication_history_id
            else None,
            prescription_id=str(reception.prescription_id.value)
            if reception.prescription_id
            else None,
            dispensing_id=str(reception.dispensing_id.value)
            if reception.dispensing_id
            else None,
            has_pending_correction_review=has_pending_review,
        )
