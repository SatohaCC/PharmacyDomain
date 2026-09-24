"""NSIPS受付取込オーケストレーションユースケース。"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.clock import Clock
from app.application.common.optional_conversion import build_optional, unwrap
from app.application.common.unit_of_work import UnitOfWork
from app.application.coverage.register_patient_coverage import (
    RegisterPatientCoverageCommand,
    RegisterPatientCoverageUseCase,
)
from app.application.dispensing.exceptions import DispensingDateRequiredError
from app.application.dispensing.start_dispensing import StartDispensingUseCase
from app.application.dispensing.support import build_dispensed_rps
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
from app.application.prescription.support import (
    build_department,
    build_medical_institution,
    build_prescriber,
    build_rps,
)
from app.application.reception.record_coverage_selection import (
    RecordCoverageSelectionCommand,
    RecordCoverageSelectionUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.patient_coverage import PatientCoverage
from app.domain.coverage.repository import PatientCoverageRepository
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId, DispensingProcessStatus
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    ExternalCorrectionTimestamp,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.value_objects import ExternalPrescriptionCorrection
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientId,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)
from app.domain.prescription.prescription import (
    Prescription,
    PrescriptionRp,
)
from app.domain.prescription.primitives import PrescriptionId, PrescriptionStatus
from app.domain.prescription.repository import PrescriptionRepository
from app.domain.reception.primitives import (
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.reception.reception import Reception, ReceptionCorrection
from app.domain.reception.repository import ReceptionRepository
from app.domain.shared.person_name import PersonNames
from app.domain.store.primitives import StoreId

_SUPPORTED_RAW_NSIPS_VERSIONS: frozenset[str] = frozenset()


@dataclass(frozen=True, kw_only=True)
class IngestNsipsCommand:
    """NSIPS取込コマンド。"""

    corporate_id: str
    store_id: str
    operator_staff_id: str
    reception_id: str | None = None
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
    has_pending_correction_review: bool = False
    patient_attribute_conflicts: tuple[str, ...] = ()
    coverage_review_required: bool = False
    coverage_review_reason: str | None = None
    coverage_selection_record_id: str | None = None
    dispensed_date: str | None = None
    addition_names: tuple[str, ...] = ()


class IngestNsipsUseCase:
    """NSIPS受付データを解析し、各集約の作成・連携を一括実行する。"""

    def __init__(
        self,
        *,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        patient_external_id_repo: PatientExternalIdentifierRepository,
        patient_repo: PatientRepository,
        prescription_repo: PrescriptionRepository,
        dispensing_repo: DispensingProcessRepository,
        register_patient_use_case: RegisterPatientUseCase,
        register_patient_external_id_use_case: RegisterPatientExternalIdentifierUseCase,
        register_prescription_use_case: RegisterPrescriptionUseCase,
        ready_for_dispensing_use_case: ReadyForDispensingUseCase,
        start_dispensing_use_case: StartDispensingUseCase,
        start_medication_history_use_case: StartMedicationHistoryUseCase,
        add_follow_up_use_case: AddFollowUpUseCase | None = None,
        list_medication_histories_use_case: ListMedicationHistoriesByPatientUseCase
        | None = None,
        medication_history_repo: MedicationHistoryRepository | None = None,
        patient_coverage_repo: PatientCoverageRepository | None = None,
        register_coverage_use_case: RegisterPatientCoverageUseCase | None = None,
        record_coverage_selection_use_case: RecordCoverageSelectionUseCase
        | None = None,
        reception_repo: ReceptionRepository,
        parser: NsipsParser | None = None,
        mapper: NsipsDataMapper | None = None,
        clock: Clock,
    ) -> None:
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._patient_external_id_repo = patient_external_id_repo
        self._patient_repo = patient_repo
        self._prescription_repo = prescription_repo
        self._dispensing_repo = dispensing_repo
        self._medication_history_repo = medication_history_repo or getattr(
            start_medication_history_use_case, "_repository", None
        )
        self._patient_coverage_repo = patient_coverage_repo
        self._register_coverage_use_case = register_coverage_use_case
        self._record_coverage_selection_use_case = record_coverage_selection_use_case
        self._reception_repo = reception_repo
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

    @staticmethod
    def _parse_reception_id(raw: str | None) -> ReceptionId:
        """受付呼出元が発行したUUIDv7を検証する。"""
        if raw is None:
            raise NsipsParseError("受付IDが必要です。")
        try:
            return ReceptionId.parse(raw)
        except DomainValidationError as error:
            raise NsipsParseError("受付IDはUUIDv7で指定してください。") from error

    @staticmethod
    def _fingerprint_bundle(
        bundle: NsipsBundle,
    ) -> tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...]:
        """形式メタデータを除くBundleの全業務フィールドを個別に指紋化する。"""
        values: dict[str, object] = {}

        def visit(value: object, path: str) -> None:
            if value is None:
                values[path] = None
                return
            if is_dataclass(value) and not isinstance(value, type):
                for item in fields(value):
                    if not path and item.name == "header_version":
                        continue
                    child_path = f"{path}.{item.name}" if path else item.name
                    visit(getattr(value, item.name), child_path)
                return
            if isinstance(value, tuple):
                values[path] = len(value)
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")
                return
            values[path] = value

        visit(bundle, "")
        fingerprinted = []
        for path, value in values.items():
            if isinstance(value, datetime):
                canonical: object = value.isoformat()
            elif isinstance(value, date):
                canonical = value.isoformat()
            elif isinstance(value, Decimal):
                canonical = str(value)
            else:
                canonical = value
            encoded = json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            fingerprinted.append(
                (
                    ReceptionFieldPath(path),
                    ReceptionFingerprint(hashlib.sha256(encoded).hexdigest()),
                )
            )
        return tuple(sorted(fingerprinted, key=lambda item: item[0].value))

    @staticmethod
    def _combined_fingerprint(
        field_fingerprints: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...],
    ) -> ReceptionFingerprint:
        """フィールド別指紋を順序に依存しない受付指紋へまとめる。"""
        encoded = json.dumps(
            [
                (path.value, fingerprint.value)
                for path, fingerprint in field_fingerprints
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return ReceptionFingerprint(hashlib.sha256(encoded).hexdigest())

    @staticmethod
    def _changed_fields(
        *,
        previous: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...],
        incoming: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...],
    ) -> tuple[ReceptionFieldPath, ...]:
        """フィールドの追加・変更・欠落を名前順で返す。"""
        previous_by_name = {
            path.value: fingerprint.value for path, fingerprint in previous
        }
        incoming_by_name = {
            path.value: fingerprint.value for path, fingerprint in incoming
        }
        return tuple(
            ReceptionFieldPath(name)
            for name in sorted(previous_by_name.keys() | incoming_by_name.keys())
            if previous_by_name.get(name) != incoming_by_name.get(name)
            or (name in previous_by_name) != (name in incoming_by_name)
        )

    async def _record_patient_profile_change(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        reception_id: ReceptionId,
        store_id: StoreId,
        bundle: NsipsBundle,
        changed_fields: tuple[str, ...],
    ) -> None:
        """Patientマスターを変えず、受付で受信したプロフィール差分を保存する。"""
        if not changed_fields:
            return
        patient = await self._patient_repo.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            return
        patient_command = self._mapper.to_patient_command(
            bundle,
            str(corporate_id.value),
        )
        names = PersonNames.create(
            last_name=patient_command.last_name,
            first_name=patient_command.first_name,
            last_name_kana=patient_command.last_name_kana,
            first_name_kana=patient_command.first_name_kana,
        )
        profile = PatientProfileSnapshot(
            names=names,
            birth_date=PatientBirthDate(bundle.patient.birth_date),
            gender=build_optional(bundle.patient.gender, PatientGenderCode),
            postal_code=build_optional(bundle.patient.postal_code, PatientPostalCode),
            address=build_optional(bundle.patient.address, PatientAddress),
            phone_number=build_optional(
                bundle.patient.phone_number,
                PatientPhoneNumber,
            ),
        )
        change = PatientProfileChange(
            reception_id=reception_id,
            store_id=store_id,
            external_patient_id=ExternalPatientId(bundle.patient.external_patient_id),
            recorded_at=self._clock.now(),
            changed_fields=tuple(f"patient.{name}" for name in changed_fields),
            received_profile=profile,
        )
        updated = patient.record_profile_change(change)
        if updated is not patient:
            await self._patient_repo.save(updated)

    async def execute(self, command: IngestNsipsCommand) -> IngestNsipsResultDto:
        """NSIPS取込を一括実行する。"""
        self._unit_of_work.ensure_active()

        corporate_id = CorporateId.parse(command.corporate_id)
        store_id = StoreId.parse(command.store_id)
        reception_id = self._parse_reception_id(command.reception_id)

        # 権限・有効法人・店舗の事前確認
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_PRESCRIPTION,
        )

        # 1. 入力形式の排他とパース処理
        if (command.structured_bundle is None) == (command.raw_nsips_text is None):
            raise NsipsParseError(
                "構造化BundleかNSIPSテキストのどちらか一方を指定してください。"
            )
        if command.structured_bundle is not None:
            bundle = command.structured_bundle
        else:
            assert command.raw_nsips_text is not None
            bundle = self._parser.parse(command.raw_nsips_text)
            if bundle.header_version not in _SUPPORTED_RAW_NSIPS_VERSIONS:
                raise NsipsParseError(
                    "NSIPSのraw形式が対応版として登録されていないため、"
                    "受け付けられません。"
                )

        self._validate_required_insurance_values(bundle)

        if bundle.prescription.rps and bundle.dispensed_date is None:
            raise DispensingDateRequiredError()
        coverage_review_reason = self._coverage_review_reason(bundle)

        # 2. 安定受付IDで受付と関連集約を照合する。
        incoming_fingerprints = self._fingerprint_bundle(bundle)
        incoming_fingerprint = self._combined_fingerprint(incoming_fingerprints)
        existing_reception = await self._reception_repo.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
        doc_num = bundle.prescription.document_number
        existing_prescription: Prescription | None = None
        if existing_reception is not None:
            if (
                existing_reception.field_fingerprints
                and existing_reception.latest_fingerprint == incoming_fingerprint
            ):
                return IngestNsipsResultDto(
                    corporate_id=command.corporate_id,
                    store_id=command.store_id,
                    patient_id=str(existing_reception.patient_id.value),
                    prescription_id=(
                        str(existing_reception.prescription_id.value)
                        if existing_reception.prescription_id is not None
                        else None
                    ),
                    dispensing_id=(
                        str(existing_reception.dispensing_id.value)
                        if existing_reception.dispensing_id is not None
                        else None
                    ),
                    medication_history_id=(
                        str(existing_reception.medication_history_id.value)
                        if existing_reception.medication_history_id is not None
                        else None
                    ),
                    document_number=doc_num,
                    patient_name=bundle.patient.kanji_name,
                    is_new_patient=False,
                    is_duplicate=True,
                    has_pending_correction_review=False,
                    coverage_review_required=coverage_review_reason is not None,
                    coverage_review_reason=coverage_review_reason,
                )

            if existing_reception.prescription_id is not None:
                existing_prescription = await self._prescription_repo.get(
                    corporate_id=corporate_id,
                    prescription_id=existing_reception.prescription_id,
                )
                if existing_prescription is None:
                    raise NsipsParseError("受付に関連付いた処方箋を取得できません。")

            patient_attribute_conflicts = await self._patient_attribute_conflicts(
                corporate_id=corporate_id,
                store_id=store_id,
                patient_id=existing_reception.patient_id,
                bundle=bundle,
            )
            changed_fields = self._changed_fields(
                previous=existing_reception.field_fingerprints,
                incoming=incoming_fingerprints,
            )
            if not existing_reception.field_fingerprints:
                changed_fields = tuple(name for name, _ in incoming_fingerprints)
            if not changed_fields:
                return IngestNsipsResultDto(
                    corporate_id=command.corporate_id,
                    store_id=command.store_id,
                    patient_id=str(existing_reception.patient_id.value),
                    prescription_id=(
                        str(existing_reception.prescription_id.value)
                        if existing_reception.prescription_id is not None
                        else None
                    ),
                    document_number=doc_num,
                    patient_name=bundle.patient.kanji_name,
                    is_new_patient=False,
                    is_duplicate=True,
                    has_pending_correction_review=False,
                    coverage_review_required=coverage_review_reason is not None,
                    coverage_review_reason=coverage_review_reason,
                )

            diff_summary: str | None = None
            if existing_prescription is not None:
                diff_summary = await self._detect_bundle_differences(
                    corporate_id=corporate_id,
                    existing=existing_prescription,
                    bundle=bundle,
                    patient_attribute_conflicts=patient_attribute_conflicts,
                )
            if diff_summary is None:
                diff_summary = "受信項目変更: " + ", ".join(
                    field.value for field in changed_fields
                )

            await self._record_patient_profile_change(
                corporate_id=corporate_id,
                patient_id=existing_reception.patient_id,
                reception_id=reception_id,
                store_id=store_id,
                bundle=bundle,
                changed_fields=patient_attribute_conflicts,
            )

            # 差分あり: 関連集約は安全に訂正できる数量だけ更新し、他は要確認にする。
            has_pending_review = True
            matching_history_id_str = (
                str(existing_reception.medication_history_id.value)
                if existing_reception.medication_history_id is not None
                else None
            )
            matching_dispensing_id_str = (
                str(existing_reception.dispensing_id.value)
                if existing_reception.dispensing_id is not None
                else None
            )

            if (
                existing_prescription is not None
                and self._medication_history_repo is not None
            ):
                records = await self._medication_history_repo.list_by_patient(
                    corporate_id=corporate_id,
                    patient_id=existing_prescription.patient_id,
                )
                matching_record = next(
                    (
                        r
                        for r in records
                        if r.prescription_id == existing_prescription.id
                    ),
                    None,
                )
                if matching_record is not None:
                    matching_history_id_str = str(matching_record.id.value)
                    matching_dispensing_id_str = str(
                        matching_record.dispensing_id.value
                    )
                    has_pending_review = (
                        not await self._try_apply_draft_quantity_correction(
                            existing=existing_prescription,
                            record=matching_record,
                            bundle=bundle,
                            diff_summary=diff_summary,
                        )
                    )
                    if has_pending_review:
                        now_utc = self._clock.now()
                        correction = ExternalPrescriptionCorrection(
                            correction_id=f"corr-{uuid.uuid7()}",
                            corrected_at=ExternalCorrectionTimestamp(now_utc),
                            source_document_number=doc_num,
                            reason=f"レセコン訂正データ受信: {diff_summary}",
                            details=diff_summary,
                        )
                        updated_history = matching_record.record_external_correction(
                            correction
                        )
                        await self._medication_history_repo.save(updated_history)

            reception_correction = ReceptionCorrection(
                fingerprint=incoming_fingerprint,
                changed_fields=changed_fields,
                received_at=self._clock.now(),
            )
            await self._reception_repo.save(
                replace(
                    existing_reception,
                    latest_fingerprint=incoming_fingerprint,
                    field_fingerprints=incoming_fingerprints,
                    correction_history=(
                        *existing_reception.correction_history,
                        reception_correction,
                    ),
                )
            )

            return IngestNsipsResultDto(
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=str(existing_reception.patient_id.value),
                prescription_id=(
                    str(existing_prescription.id.value)
                    if existing_prescription is not None
                    else None
                ),
                dispensing_id=matching_dispensing_id_str,
                medication_history_id=matching_history_id_str,
                document_number=doc_num,
                patient_name=bundle.patient.kanji_name,
                is_new_patient=False,
                is_duplicate=False,
                is_follow_up_only=False,
                has_pending_correction_review=has_pending_review,
                patient_attribute_conflicts=patient_attribute_conflicts,
                coverage_review_required=coverage_review_reason is not None,
                coverage_review_reason=coverage_review_reason,
            )

        # 3. 患者の解決（法人・店舗・連携先・外部患者IDで照合）
        ext_patient_id = bundle.patient.external_patient_id
        active_link = await self._patient_external_id_repo.get_active_by_source(
            corporate_id=corporate_id,
            store_id=store_id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=ExternalPatientId(ext_patient_id),
        )

        if active_link is not None:
            patient_id_str = str(active_link.patient_id.value)
            is_new_patient = False
            patient_attribute_conflicts = await self._patient_attribute_conflicts(
                corporate_id=corporate_id,
                store_id=store_id,
                patient_id=active_link.patient_id,
                bundle=bundle,
            )
            await self._record_patient_profile_change(
                corporate_id=corporate_id,
                patient_id=active_link.patient_id,
                reception_id=reception_id,
                store_id=store_id,
                bundle=bundle,
                changed_fields=patient_attribute_conflicts,
            )
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
                    store_id=command.store_id,
                )
            )
            is_new_patient = True
            patient_attribute_conflicts = ()

        # 4. 通常処方（薬品あり） vs フォローアップ単独受付（薬品0件）
        if bundle.prescription.rps:
            if bundle.dispensed_date is None:
                raise DispensingDateRequiredError()
            # 4.1 保険資格の解決・登録および適用資格選択履歴の記録
            coverage_selection_record_id: str | None = None
            if bundle.insurance is not None and self._patient_coverage_repo is not None:
                pat_id_obj = PatientId.parse(patient_id_str)
                existing_coverages = await self._patient_coverage_repo.list_by_patient(
                    corporate_id=corporate_id,
                    patient_id=pat_id_obj,
                )
                cov_commands = self._mapper.to_coverage_commands(
                    bundle,
                    corporate_id=command.corporate_id,
                    patient_id=patient_id_str,
                )
                applied_coverage_ids: list[str] = []
                for cov_cmd in cov_commands:
                    matched_id: str | None = None
                    matched_coverage = next(
                        (
                            current
                            for current in existing_coverages
                            if self._coverage_matches(current, cov_cmd)
                        ),
                        None,
                    )
                    if matched_coverage is not None:
                        matched_id = str(matched_coverage.id.value)
                    if matched_id is not None:
                        if self._coverage_command_is_selectable(cov_cmd):
                            applied_coverage_ids.append(matched_id)
                    elif self._register_coverage_use_case is not None:
                        new_cov = await self._register_coverage_use_case.execute(
                            cov_cmd
                        )
                        if self._coverage_command_is_selectable(cov_cmd):
                            applied_coverage_ids.append(new_cov.id)

                if (
                    applied_coverage_ids
                    and self._record_coverage_selection_use_case is not None
                ):
                    sel_res = await self._record_coverage_selection_use_case.execute(
                        RecordCoverageSelectionCommand(
                            corporate_id=command.corporate_id,
                            store_id=command.store_id,
                            patient_id=patient_id_str,
                            applied_on=bundle.dispensed_date,
                            coverage_ids=tuple(applied_coverage_ids),
                        )
                    )
                    coverage_selection_record_id = sel_res.id

            # 4.2 処方箋原本の登録
            presc_cmd = self._mapper.to_prescription_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=patient_id_str,
                coverage_selection_record_id=coverage_selection_record_id,
            )
            presc_dto = await self._register_prescription_use_case.execute(presc_cmd)

            # 4.3 調剤待ち化 (READY_FOR_DISPENSING)
            await self._ready_for_dispensing_use_case.execute(
                ReadyForDispensingCommand(
                    corporate_id=command.corporate_id,
                    prescription_id=presc_dto.id,
                )
            )

            # 4.4 調剤セッション作成
            disp_cmd = self._mapper.to_dispensing_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                prescription_id=presc_dto.id,
                dispenser_id=command.operator_staff_id,
            )
            disp_dto = await self._start_dispensing_use_case.execute(disp_cmd)

            # 4.5 薬歴下書き自動起票
            hist_cmd = self._mapper.to_medication_history_command(
                bundle,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                dispensing_id=disp_dto.id,
                counselor_id=command.operator_staff_id,
            )
            hist_dto = await self._start_medication_history_use_case.execute(hist_cmd)

            disp_date_str = bundle.dispensed_date.isoformat()
            addition_names = tuple(add.name for add in bundle.additions)

            await self._reception_repo.save(
                Reception(
                    id=reception_id,
                    corporate_id=corporate_id,
                    store_id=store_id,
                    patient_id=PatientId.parse(patient_id_str),
                    prescription_id=PrescriptionId.parse(presc_dto.id),
                    dispensing_id=DispensingId.parse(disp_dto.id),
                    medication_history_id=MedicationHistoryRecordId.parse(hist_dto.id),
                    latest_fingerprint=incoming_fingerprint,
                    field_fingerprints=incoming_fingerprints,
                )
            )

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
                patient_attribute_conflicts=patient_attribute_conflicts,
                coverage_review_required=coverage_review_reason is not None,
                coverage_review_reason=coverage_review_reason,
                coverage_selection_record_id=coverage_selection_record_id,
                dispensed_date=disp_date_str,
                addition_names=addition_names,
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
                now_dt = self._clock.now()
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

        await self._reception_repo.save(
            Reception(
                id=reception_id,
                corporate_id=corporate_id,
                store_id=store_id,
                patient_id=PatientId.parse(patient_id_str),
                prescription_id=None,
                dispensing_id=None,
                medication_history_id=(
                    MedicationHistoryRecordId.parse(record_id)
                    if record_id is not None
                    else None
                ),
                latest_fingerprint=incoming_fingerprint,
                field_fingerprints=incoming_fingerprints,
            )
        )

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
            patient_attribute_conflicts=patient_attribute_conflicts,
            coverage_review_required=coverage_review_reason is not None,
            coverage_review_reason=coverage_review_reason,
        )

    @staticmethod
    def _is_quantity_only_correction(
        existing: Prescription,
        incoming_rps: tuple[PrescriptionRp, ...],
    ) -> bool:
        """処方構造を変えず、剤の調剤数量だけが異なるか判定する。"""
        if len(existing.rps) != len(incoming_rps):
            return False
        has_quantity_change = False
        for current, incoming in zip(existing.rps, incoming_rps, strict=True):
            if current.rp_number != incoming.rp_number:
                return False
            if current.quantity != incoming.quantity:
                has_quantity_change = True
            if replace(incoming, quantity=current.quantity) != current:
                return False
        return has_quantity_change

    @staticmethod
    def _dispensing_matches_prescription(
        dispensing: DispensingProcess,
        prescription: Prescription,
    ) -> bool:
        """調剤数量訂正前に、調剤セッションが原処方どおりか確認する。"""
        if (
            dispensing.status is not DispensingProcessStatus.IN_PROGRESS
            or dispensing.verification is not None
            or dispensing.audit is not None
        ):
            return False

        if len(dispensing.dispensed_rps) != len(prescription.rps):
            return False
        for dispensed, prescribed in zip(
            dispensing.dispensed_rps, prescription.rps, strict=True
        ):
            if (
                dispensed.rp_number != prescribed.rp_number
                or dispensed.category != prescribed.category
                or dispensed.quantity != prescribed.quantity
                or dispensed.dosage_instruction != prescribed.dosage_instruction
                or dispensed.quantity_adjustment is not None
                or len(dispensed.medicines) != len(prescribed.medicines)
            ):
                return False
            for actual_medicine, prescribed_medicine in zip(
                dispensed.medicines, prescribed.medicines, strict=True
            ):
                if (
                    actual_medicine.line_number != prescribed_medicine.line_number
                    or actual_medicine.identifier != prescribed_medicine.identifier
                    or actual_medicine.name != prescribed_medicine.name
                    or actual_medicine.amount != prescribed_medicine.amount
                    or actual_medicine.unit != prescribed_medicine.unit
                    or actual_medicine.public_expense_burden
                    != prescribed_medicine.public_expense_burden
                    or actual_medicine.substitution is not None
                ):
                    return False
        return True

    async def _try_apply_draft_quantity_correction(
        self,
        *,
        existing: Prescription,
        record: MedicationHistoryRecord,
        bundle: NsipsBundle,
        diff_summary: str,
    ) -> bool:
        """未編集の下書きへ剤数量だけの訂正を反映できたか返す。"""
        if (
            record.is_finalized
            or existing.status is not PrescriptionStatus.READY_FOR_DISPENSING
        ):
            return False
        prescription_difference = self._detect_prescription_differences(
            existing, bundle
        )
        if (
            prescription_difference is None
            or diff_summary != f"処方内容: {prescription_difference}"
        ):
            return False

        prescription_command = self._mapper.to_prescription_command(
            bundle,
            corporate_id=str(existing.corporate_id.value),
            store_id=str(existing.store_id.value),
            patient_id=str(existing.patient_id.value),
        )
        incoming_rps = build_rps(prescription_command.rps)
        if not self._is_quantity_only_correction(existing, incoming_rps):
            return False

        dispensing = await self._dispensing_repo.get(
            corporate_id=existing.corporate_id,
            dispensing_id=record.dispensing_id,
        )
        if dispensing is None or not self._dispensing_matches_prescription(
            dispensing, existing
        ):
            return False

        updated_prescription = existing.replace_rps(incoming_rps)
        quantities = {rp.rp_number: rp.quantity for rp in incoming_rps}
        updated_dispensing = dispensing.update_dispensed_rps(
            tuple(
                replace(rp, quantity=quantities[rp.rp_number])
                for rp in dispensing.dispensed_rps
            )
        )
        await self._prescription_repo.save(updated_prescription)
        await self._dispensing_repo.save(updated_dispensing)
        return True

    @staticmethod
    def _coverage_command_is_selectable(
        command: RegisterPatientCoverageCommand,
    ) -> bool:
        """請求固定値が揃った資格だけを適用選択へ渡す。"""
        if command.coverage_type == "insurance":
            return (
                command.insured_type is not None and command.benefit_ratio is not None
            )
        return command.payer_number is not None and command.recipient_number is not None

    @staticmethod
    def _validate_required_insurance_values(bundle: NsipsBundle) -> None:
        """保険識別値の部分欠損と資格情報の完全欠損を取込前に拒否する。"""
        insurance = bundle.insurance
        if insurance is None:
            return
        required_values = (
            insurance.insurer_number,
            insurance.insured_symbol,
            insurance.insured_number,
        )
        has_insurance_identity = any(value.strip() for value in required_values)
        has_public_expense = any(
            value is not None and value.strip()
            for value in (
                insurance.public_payer_number_1,
                insurance.public_recipient_number_1,
                insurance.public_payer_number_2,
                insurance.public_recipient_number_2,
            )
        )
        if has_insurance_identity and any(
            not value.strip() for value in required_values
        ):
            raise NsipsParseError(
                "保険者番号・被保険者記号・被保険者番号は空にできません。"
            )
        if not has_insurance_identity and not has_public_expense:
            raise NsipsParseError("保険または公費の識別情報が必要です。")

    @staticmethod
    def _coverage_review_reason(bundle: NsipsBundle) -> str | None:
        """不完全な受信資格を選択しない理由を個人値なしで返す。"""
        insurance = bundle.insurance
        if insurance is None:
            return None
        reasons: list[str] = []
        if insurance.insurer_number and (
            not insurance.insured_symbol or not insurance.insured_number
        ):
            reasons.append("insurance_identity_incomplete")
        if insurance.insurer_number and insurance.benefit_ratio is None:
            reasons.append("benefit_ratio_missing")
        if insurance.insurer_number and insurance.insured_type is None:
            reasons.append("insured_type_missing")
        public_pairs = (
            (insurance.public_payer_number_1, insurance.public_recipient_number_1),
            (insurance.public_payer_number_2, insurance.public_recipient_number_2),
        )
        if any(bool(payer) != bool(recipient) for payer, recipient in public_pairs):
            reasons.append("public_expense_incomplete")
        return reasons[0] if reasons else None

    async def _patient_attribute_conflicts(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        patient_id: PatientId,
        bundle: NsipsBundle,
    ) -> tuple[str, ...]:
        """既存Patientを変更せず、受信値と異なる属性名だけを返す。"""
        patient = await self._patient_repo.get(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        if patient is None:
            return ()

        patient_command = self._mapper.to_patient_command(
            bundle, str(corporate_id.value)
        )
        incoming_names = PersonNames.create(
            last_name=patient_command.last_name,
            first_name=patient_command.first_name,
            last_name_kana=patient_command.last_name_kana,
            first_name_kana=patient_command.first_name_kana,
        )
        conflicts: list[str] = []

        external_identifiers = await self._patient_external_id_repo.list_by_patient(
            corporate_id=corporate_id,
            patient_id=patient_id,
        )
        expected_external_id = ExternalPatientId(bundle.patient.external_patient_id)
        if not any(
            identifier.is_active
            and identifier.store_id == store_id
            and identifier.system_name == ExternalSystemName("recept")
            and identifier.external_patient_id == expected_external_id
            for identifier in external_identifiers
        ):
            conflicts.append("external_patient_id")

        if patient.names.kanji != incoming_names.kanji:
            conflicts.append("kanji_name")
        if patient.names.kana != incoming_names.kana:
            conflicts.append("kana_name")
        if (
            patient.birth_date is None
            or patient.birth_date.value != bundle.patient.birth_date
        ):
            conflicts.append("birth_date")

        incoming_fields = (
            (
                "gender",
                unwrap(build_optional(bundle.patient.gender, PatientGenderCode)),
                unwrap(patient.gender),
            ),
            (
                "postal_code",
                unwrap(build_optional(bundle.patient.postal_code, PatientPostalCode)),
                unwrap(patient.postal_code),
            ),
            (
                "address",
                unwrap(build_optional(bundle.patient.address, PatientAddress)),
                unwrap(patient.address),
            ),
            (
                "phone_number",
                unwrap(build_optional(bundle.patient.phone_number, PatientPhoneNumber)),
                unwrap(patient.phone_number),
            ),
        )
        conflicts.extend(
            name
            for name, incoming, existing in incoming_fields
            if incoming is not None and incoming != existing
        )
        return tuple(conflicts)

    @staticmethod
    def _coverage_matches(
        existing: PatientCoverage,
        incoming: RegisterPatientCoverageCommand,
    ) -> bool:
        """制度識別値・枝番・本人区分・給付割合・公費順位を全て照合する。"""
        if existing.coverage_type.value != incoming.coverage_type:
            return False
        if incoming.coverage_type == "insurance":
            details = existing.insurance_details
            return (
                details is not None
                and details.insurer_number.value == incoming.insurer_number
                and details.insured_symbol.value == incoming.insured_symbol
                and details.insured_number.value == incoming.insured_number
                and unwrap(details.branch_number) == incoming.branch_number
                and unwrap(details.insured_type) == incoming.insured_type
                and unwrap(details.benefit_ratio) == incoming.benefit_ratio
            )
        public_details = existing.public_expense_details
        return (
            public_details is not None
            and public_details.payer_number.value == incoming.payer_number
            and public_details.recipient_number.value == incoming.recipient_number
            and existing.priority.value == incoming.priority
        )

    async def _detect_bundle_differences(
        self,
        *,
        corporate_id: CorporateId,
        existing: Prescription,
        bundle: NsipsBundle,
        patient_attribute_conflicts: tuple[str, ...],
    ) -> str | None:
        """同一処方箋番号の処方外受信差分を含めて訂正有無を判定する。"""
        differences: list[str] = []
        prescription_difference = self._detect_prescription_differences(
            existing,
            bundle,
        )
        if prescription_difference is not None:
            differences.append(f"処方内容: {prescription_difference}")
        if existing.period.issued_date.value != bundle.prescription.issued_date:
            differences.append("issued_date変更")
        if patient_attribute_conflicts:
            differences.append(
                f"患者属性変更: {', '.join(patient_attribute_conflicts)}"
            )

        if bundle.insurance is not None and self._patient_coverage_repo is not None:
            incoming_coverages = self._mapper.to_coverage_commands(
                bundle,
                corporate_id=str(corporate_id.value),
                patient_id=str(existing.patient_id.value),
            )
            if incoming_coverages:
                registered = await self._patient_coverage_repo.list_by_patient(
                    corporate_id=corporate_id,
                    patient_id=existing.patient_id,
                )
                if any(
                    not any(
                        self._coverage_matches(current, candidate)
                        for current in registered
                    )
                    for candidate in incoming_coverages
                ):
                    differences.append("保険・公費資格変更")

        if self._medication_history_repo is not None:
            histories = await self._medication_history_repo.list_by_patient(
                corporate_id=corporate_id,
                patient_id=existing.patient_id,
            )
            matching_history = next(
                (item for item in histories if item.prescription_id == existing.id),
                None,
            )
            if matching_history is not None:
                incoming_additions = tuple(
                    (item.code, item.name, item.points, item.quantity)
                    for item in bundle.additions
                )
                existing_additions = tuple(
                    (
                        item.code.value,
                        item.name.value,
                        item.points,
                        item.quantity,
                    )
                    for item in matching_history.billing_additions
                )
                if incoming_additions != existing_additions:
                    differences.append("additions変更")

                dispensing = await self._dispensing_repo.get(
                    corporate_id=corporate_id,
                    dispensing_id=matching_history.dispensing_id,
                )
                if dispensing is not None:
                    if (
                        bundle.dispensed_date is not None
                        and dispensing.dispensed_date.value != bundle.dispensed_date
                    ):
                        differences.append("dispensed_date変更")
                    incoming_dispensing = self._mapper.to_dispensing_command(
                        bundle,
                        corporate_id=str(corporate_id.value),
                        store_id=str(existing.store_id.value),
                        prescription_id=str(existing.id.value),
                        dispenser_id=str(dispensing.dispenser_id.value),
                    )
                    if (
                        dispensing.iteration.value != incoming_dispensing.iteration
                        or unwrap(dispensing.total_split_count)
                        != incoming_dispensing.total_split_count
                        or unwrap(dispensing.split_reason)
                        != incoming_dispensing.split_reason
                    ):
                        differences.append("split_info変更")

                    incoming_dispensed_rps = build_dispensed_rps(
                        incoming_dispensing.dispensed_rps
                    )
                    current_rps = {
                        item.rp_number.value: item for item in dispensing.dispensed_rps
                    }
                    for incoming_rp in incoming_dispensed_rps:
                        current_rp = current_rps.get(incoming_rp.rp_number.value)
                        if current_rp is None:
                            continue
                        current_medicines = {
                            item.line_number.value: item
                            for item in current_rp.medicines
                        }
                        if any(
                            current_medicines.get(medicine.line_number.value)
                            is not None
                            and current_medicines[
                                medicine.line_number.value
                            ].preparations
                            != medicine.preparations
                            for medicine in incoming_rp.medicines
                        ):
                            differences.append("preparation_method変更")

        return " / ".join(dict.fromkeys(differences)) if differences else None

    def _detect_prescription_differences(
        self, existing: Prescription, bundle: NsipsBundle
    ) -> str | None:
        """NSIPSで受信した処方の識別・表示・剤明細差分を全て検出する。"""
        incoming = self._mapper.to_prescription_command(
            bundle,
            corporate_id=str(existing.corporate_id.value),
            store_id=str(existing.store_id.value),
            patient_id=str(existing.patient_id.value),
        )
        incoming_institution = build_medical_institution(incoming.medical_institution)
        incoming_department = build_department(incoming.department)
        incoming_prescriber = build_prescriber(incoming.prescriber)
        incoming_rps = build_rps(incoming.rps)
        diffs: list[str] = []

        current_institution = existing.medical_institution
        if current_institution.code_type != incoming_institution.code_type:
            diffs.append("institution_code_type")
        if current_institution.code != incoming_institution.code:
            diffs.append("institution_code")
        if current_institution.name != incoming_institution.name:
            diffs.append("institution_name")
        if current_institution.prefecture_code != incoming_institution.prefecture_code:
            diffs.append("institution_prefecture_code")

        current_department = existing.department
        if current_department.code_type != incoming_department.code_type:
            diffs.append("department_code_type")
        if current_department.code != incoming_department.code:
            diffs.append("department_code")
        if current_department.name != incoming_department.name:
            diffs.append("department_name")

        if existing.prescriber.names != incoming_prescriber.names:
            diffs.append("doctor_name")
        if existing.prescriber.names_kana != incoming_prescriber.names_kana:
            diffs.append("doctor_kana")
        if existing.prescriber.code != incoming_prescriber.code:
            diffs.append("doctor_code")

        if len(existing.rps) != len(incoming_rps):
            diffs.append("rp_count")
        incoming_rps_by_num = {rp.rp_number.value: rp for rp in incoming_rps}
        for ex_rp in existing.rps:
            rp_num = ex_rp.rp_number.value
            in_rp = incoming_rps_by_num.get(rp_num)
            if in_rp is None:
                diffs.append(f"rp_number_Rp{rp_num}_missing")
                continue

            if ex_rp.category != in_rp.category:
                diffs.append(f"group_name_Rp{rp_num}")
            if ex_rp.quantity != in_rp.quantity:
                diffs.append(
                    f"quantity_Rp{rp_num}: {ex_rp.quantity.value} -> "
                    f"{in_rp.quantity.value}"
                )
            if ex_rp.dosage_instruction != in_rp.dosage_instruction:
                diffs.append(f"instructions_Rp{rp_num}")
            if ex_rp.custom_category_name != in_rp.custom_category_name:
                diffs.append(f"group_name_Rp{rp_num}")
            if ex_rp.dosage_supplements != in_rp.dosage_supplements:
                diffs.append(f"dosage_supplements_Rp{rp_num}")

            if len(ex_rp.medicines) != len(in_rp.medicines):
                diffs.append(f"medicine_count_Rp{rp_num}")
            for index, (ex_medicine, in_medicine) in enumerate(
                zip(ex_rp.medicines, in_rp.medicines, strict=False), start=1
            ):
                if ex_medicine.identifier != in_medicine.identifier:
                    diffs.append(f"medicine_code_Rp{rp_num}_{index}")
                if ex_medicine.name != in_medicine.name:
                    diffs.append(f"medicine_name_Rp{rp_num}_{index}")
                if ex_medicine.amount != in_medicine.amount:
                    diffs.append(f"dosage_Rp{rp_num}_{index}")
                if ex_medicine.unit != in_medicine.unit:
                    diffs.append(f"unit_Rp{rp_num}_{index}")
                if ex_medicine.unit_conversion != in_medicine.unit_conversion:
                    diffs.append(f"unit_conversion_Rp{rp_num}_{index}")
                if ex_medicine.unequal_dosage != in_medicine.unequal_dosage:
                    diffs.append(f"unequal_dosage_Rp{rp_num}_{index}")
                if ex_medicine.single_dose != in_medicine.single_dose:
                    diffs.append(f"single_dose_Rp{rp_num}_{index}")
                if (
                    ex_medicine.substitution_restriction
                    != in_medicine.substitution_restriction
                ):
                    diffs.append(f"substitution_restriction_Rp{rp_num}_{index}")
                if (
                    ex_medicine.public_expense_burden
                    != in_medicine.public_expense_burden
                ):
                    diffs.append(f"public_expense_burden_Rp{rp_num}_{index}")
                if ex_medicine.supplements != in_medicine.supplements:
                    diffs.append(f"medicine_supplements_Rp{rp_num}_{index}")

        if diffs:
            return " / ".join(dict.fromkeys(diffs))
        return None
