"""NSIPS受付取込オーケストレーションユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common import UnitOfWork
from app.application.common.clock import Clock
from app.application.dispensing.start_dispensing import StartDispensingUseCase
from app.application.integration.nsips.exceptions import NsipsParseError
from app.application.integration.nsips.mapper import NsipsDataMapper
from app.application.integration.nsips.models import NsipsBundle
from app.application.integration.nsips.parser import NsipsParser
from app.application.medication_history.add_follow_up import AddFollowUpUseCase
from app.application.medication_history.get_medication_history import (
    ListMedicationHistoriesByPatientUseCase,
    ListMedicationHistoriesQuery,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryUseCase,
)
from app.application.patient.register_patient import RegisterPatientUseCase
from app.application.patient.register_patient_external_identifier import (
    RegisterPatientExternalIdentifierCommand,
    RegisterPatientExternalIdentifierUseCase,
)
from app.application.prescription.ready_for_dispensing import (
    ReadyForDispensingCommand,
    ReadyForDispensingUseCase,
)
from app.application.prescription.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import ExternalPatientId, ExternalSystemName
from app.domain.patient.repository import PatientExternalIdentifierRepository
from app.domain.prescription import (
    PrescriptionDocumentNumber,
    PrescriptionRepository,
)
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class IngestNsipsCommand:
    """NSIPS取込コマンド。"""

    corporate_id: str
    store_id: str
    operator_staff_id: str
    raw_nsips_text: str | None = None
    structured_bundle: NsipsBundle | None = None


@dataclass(frozen=True, kw_only=True)
class IngestNsipsResultDto:
    """NSIPS取込結果DTO。"""

    corporate_id: str
    store_id: str
    patient_id: str
    prescription_id: str | None = None
    dispensing_id: str | None = None
    medication_history_id: str | None = None
    follow_up_id: str | None = None
    document_number: str | None = None
    patient_name: str
    is_new_patient: bool
    is_duplicate: bool = False
    is_follow_up_only: bool = False


class IngestNsipsUseCase:
    """NSIPS受付データを解析し、各集約の作成・連携を一括実行する。"""

    def __init__(
        self,
        *,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        patient_external_id_repo: PatientExternalIdentifierRepository,
        prescription_repo: PrescriptionRepository,
        register_patient_use_case: RegisterPatientUseCase,
        register_patient_external_id_use_case: RegisterPatientExternalIdentifierUseCase,
        register_prescription_use_case: RegisterPrescriptionUseCase,
        ready_for_dispensing_use_case: ReadyForDispensingUseCase,
        start_dispensing_use_case: StartDispensingUseCase,
        start_medication_history_use_case: StartMedicationHistoryUseCase,
        add_follow_up_use_case: AddFollowUpUseCase | None = None,
        list_medication_histories_use_case: ListMedicationHistoriesByPatientUseCase
        | None = None,
        parser: NsipsParser | None = None,
        mapper: NsipsDataMapper | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._patient_external_id_repo = patient_external_id_repo
        self._prescription_repo = prescription_repo
        self._register_patient_use_case = register_patient_use_case
        self._register_patient_external_id_use_case = (
            register_patient_external_id_use_case
        )
        self._register_prescription_use_case = register_prescription_use_case
        self._ready_for_dispensing_use_case = ready_for_dispensing_use_case
        self._start_dispensing_use_case = start_dispensing_use_case
        self._start_medication_history_use_case = start_medication_history_use_case
        self._add_follow_up_use_case = add_follow_up_use_case
        self._list_medication_histories_use_case = list_medication_histories_use_case
        self._parser = parser or NsipsParser()
        self._mapper = mapper or NsipsDataMapper()
        self._clock = clock

    async def execute(self, command: IngestNsipsCommand) -> IngestNsipsResultDto:
        """NSIPS取込を一括実行する。"""
        self._unit_of_work.ensure_active()

        corporate_id = CorporateId.parse(command.corporate_id)
        StoreId.parse(command.store_id)

        # 権限・有効法人・店舗の事前確認
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PRESCRIPTION,
        )

        # 1. パース処理
        if command.structured_bundle is not None:
            bundle = command.structured_bundle
        elif command.raw_nsips_text is not None:
            bundle = self._parser.parse(command.raw_nsips_text)
        else:
            raise NsipsParseError("NSIPSデータが指定されていません。")

        # 2. 冪等性チェック（同一処方箋番号の重複検知）
        doc_num = bundle.prescription.document_number
        existing_prescription = await self._prescription_repo.get_by_document_number(
            corporate_id=corporate_id,
            document_number=PrescriptionDocumentNumber(doc_num),
        )
        if existing_prescription is not None:
            return IngestNsipsResultDto(
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=str(existing_prescription.patient_id.value),
                prescription_id=str(existing_prescription.id.value),
                document_number=doc_num,
                patient_name=bundle.patient.kanji_name,
                is_new_patient=False,
                is_duplicate=True,
                is_follow_up_only=False,
            )

        # 3. 患者の解決（照合または新規登録）
        ext_patient_id = bundle.patient.external_patient_id
        active_link = await self._patient_external_id_repo.get_active_by_source(
            corporate_id=corporate_id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=ExternalPatientId(ext_patient_id),
        )

        if active_link is not None:
            patient_id_str = str(active_link.patient_id.value)
            is_new_patient = False
        else:
            # 新規患者登録
            patient_cmd = self._mapper.to_patient_command(bundle, command.corporate_id)
            new_patient_id = await self._register_patient_use_case.execute(patient_cmd)
            patient_id_str = str(new_patient_id.value)

            # 外部患者IDの対応付け
            await self._register_patient_external_id_use_case.execute(
                RegisterPatientExternalIdentifierCommand(
                    corporate_id=command.corporate_id,
                    patient_id=patient_id_str,
                    system_name="recept",
                    external_patient_id=ext_patient_id,
                )
            )
            is_new_patient = True

        # 4. 通常処方（薬品あり） vs フォローアップ単独受付（薬品0件）
        if bundle.prescription.rps:
            # 処方箋原本の登録
            presc_cmd = self._mapper.to_prescription_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=patient_id_str,
            )
            presc_dto = await self._register_prescription_use_case.execute(presc_cmd)

            # 調剤待ち化 (READY_FOR_DISPENSING)
            await self._ready_for_dispensing_use_case.execute(
                ReadyForDispensingCommand(
                    corporate_id=command.corporate_id,
                    prescription_id=presc_dto.id,
                )
            )

            # 調剤セッション作成
            disp_cmd = self._mapper.to_dispensing_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                prescription_id=presc_dto.id,
                dispenser_id=command.operator_staff_id,
            )
            disp_dto = await self._start_dispensing_use_case.execute(disp_cmd)

            # 薬歴下書き自動起票
            hist_cmd = self._mapper.to_medication_history_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                dispensing_id=disp_dto.id,
                counselor_id=command.operator_staff_id,
            )
            hist_dto = await self._start_medication_history_use_case.execute(hist_cmd)

            return IngestNsipsResultDto(
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=patient_id_str,
                prescription_id=presc_dto.id,
                dispensing_id=disp_dto.id,
                medication_history_id=hist_dto.id,
                document_number=doc_num,
                patient_name=bundle.patient.kanji_name,
                is_new_patient=is_new_patient,
                is_duplicate=False,
                is_follow_up_only=False,
            )

        # 薬品0件（フォローアップ単独受付）
        follow_up_id: str | None = None
        record_id: str | None = None

        if (
            self._list_medication_histories_use_case is not None
            and self._add_follow_up_use_case is not None
        ):
            histories = await self._list_medication_histories_use_case.execute(
                ListMedicationHistoriesQuery(
                    corporate_id=command.corporate_id,
                    patient_id=patient_id_str,
                )
            )
            if histories:
                record_id = histories[0].id
                now_dt = self._clock.now() if self._clock is not None else None
                fu_cmd = self._mapper.to_follow_up_command(
                    bundle,
                    corporate_id=command.corporate_id,
                    record_id=record_id,
                    counselor_id=command.operator_staff_id,
                    followed_up_at=now_dt,
                )
                updated_history = await self._add_follow_up_use_case.execute(fu_cmd)
                if updated_history.follow_ups:
                    follow_up_id = updated_history.follow_ups[-1].id

        return IngestNsipsResultDto(
            corporate_id=command.corporate_id,
            store_id=command.store_id,
            patient_id=patient_id_str,
            prescription_id=None,
            dispensing_id=None,
            medication_history_id=record_id,
            follow_up_id=follow_up_id,
            document_number=doc_num,
            patient_name=bundle.patient.kanji_name,
            is_new_patient=is_new_patient,
            is_duplicate=False,
            is_follow_up_only=True,
        )
