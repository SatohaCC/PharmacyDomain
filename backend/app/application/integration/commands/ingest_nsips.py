"""Applicationのingest_nsipsを定義する。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal

from app.application.access_control.boundary_models import Permission
from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock
from app.application.common.optional_conversion import build_optional
from app.application.common.unit_of_work import UnitOfWork
from app.application.integration.boundary_models import (
    NsipsBundle,
    _PatientProfileApplication,
)
from app.application.integration.commands.dtos.ingest_nsips import IngestNsipsResultDto
from app.application.integration.commands.models import (
    _EXTERNAL_PATIENT_ID_FIELD_PATH,
    _OPTIONAL_PATIENT_PROFILE_FIELD_PATHS,
    _PATIENT_PROFILE_CONFLICT_NAMES,
    _PATIENT_PROFILE_FIELD_PATHS,
    _SUPPORTED_RAW_NSIPS_VERSIONS,
)
from app.application.integration.commands.services.mapper import NsipsDataMapper
from app.application.integration.commands.services.parser import NsipsParser
from app.application.integration.commands.services.source_mapping import map_bundle
from app.application.integration.errors import (
    NsipsParseError,
    NsipsPatientIdentityConflictError,
    NsipsReceptionNotFoundError,
    NsipsSourceConflictError,
)
from app.application.integration.interfaces.registration_operations import (
    RegisterPatientExternalIdentifierOperation,
    RegisterPatientOperation,
)
from app.application.patient.commands.models import (
    RegisterPatientExternalIdentifierCommand,
)
from app.application.patient.commands.services.support import load_patient_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.identifiers import (
    ExternalCorrectionId,
)
from app.domain.medication_history.primitives import (
    CorrectionDocumentNumber,
    ExternalCorrectionDetails,
    ExternalCorrectionKind,
    ExternalCorrectionReason,
    ExternalCorrectionTimestamp,
)
from app.domain.medication_history.repositories import MedicationHistoryRepository
from app.domain.medication_history.value_objects import ExternalPrescriptionCorrection
from app.domain.patient.identifiers import PatientId
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientPhoneNumber,
    PatientPostalCode,
    PatientProfileField,
)
from app.domain.patient.repositories import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)
from app.domain.patient.value_objects import (
    PatientProfileChange,
    PatientProfileSnapshot,
)
from app.domain.reception.entities import Reception
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import (
    ReceptionBillingCode,
    ReceptionBillingName,
    ReceptionBillingPoints,
    ReceptionBillingQuantity,
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionOriginalJson,
    ReceptionSourceStatus,
)
from app.domain.reception.repositories import ReceptionRepository
from app.domain.reception.value_objects import (
    ReceptionBillingAddition,
    ReceptionCorrection,
    ReceptionSourceData,
)
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.store.exceptions import StoreStateConflictError
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import StoreStatus
from app.domain.store.repositories import StoreRepository


@dataclass(frozen=True, kw_only=True)
class IngestNsipsCommand:
    """NSIPS取込コマンド。"""

    corporate_id: str
    store_id: str
    reception_id: str | None = None
    raw_nsips_text: str | None = None
    structured_bundle: NsipsBundle | None = None
    expected_fingerprint: str | None = None


class IngestNsipsUseCase:
    """NSIPS受付原本データを受信・解析し、原本と患者情報を原子的に保存する。"""

    def __init__(
        self,
        *,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        patient_external_id_repo: PatientExternalIdentifierRepository,
        patient_repo: PatientRepository,
        reception_repo: ReceptionRepository,
        store_repo: StoreRepository,
        register_patient_use_case: RegisterPatientOperation,
        register_patient_external_id_use_case: RegisterPatientExternalIdentifierOperation,
        medication_history_repo: MedicationHistoryRepository | None = None,
        parser: NsipsParser | None = None,
        mapper: NsipsDataMapper | None = None,
        clock: Clock,
    ) -> None:
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._patient_external_id_repo = patient_external_id_repo
        self._patient_repo = patient_repo
        self._reception_repo = reception_repo
        self._store_repo = store_repo
        self._register_patient_use_case = register_patient_use_case
        self._register_patient_external_id_use_case = (
            register_patient_external_id_use_case
        )
        self._medication_history_repo = medication_history_repo
        self._parser = parser or NsipsParser()
        self._mapper = mapper or NsipsDataMapper()
        self._clock = clock

    @staticmethod
    def _parse_reception_id(raw: str | None) -> ReceptionId:
        """受付ID（UUIDv7形式）をパースして検証する。"""
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
        """受信Bundle内の各業務フィールド（ヘッダーバージョン等のメタ情報を除く）のハッシュ値を計算する。"""
        values: dict[str, object] = {}

        def visit(value: object, path: str) -> None:
            if value is None:
                values[path] = None
                return
            if is_dataclass(value) and (not isinstance(value, type)):
                for item in fields(value):
                    if not path and item.name in ("header_version", "correction_kind"):
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
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
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
        """各フィールドのハッシュ値を統合し、項目順序に左右されない受付全体のハッシュ値を計算する。"""
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
    def _external_correction_id(
        *,
        record_id_str: str,
        document_number: str,
        fingerprint: ReceptionFingerprint,
    ) -> str:
        """薬歴ID・処方箋番号・ハッシュ値から、同一訂正内容を一意に識別する訂正IDを生成する。"""
        identity = ":".join((record_id_str, document_number, fingerprint.value))
        return "corr-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_data(
        bundle: NsipsBundle, *, imported_at: datetime, is_follow_up: bool
    ) -> ReceptionSourceData:
        """受信したBundleデータ全体をJSON文字列としてシリアライズし、保管用スナップショットを作成する。"""

        def encode(value: object) -> str:
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            if isinstance(value, Decimal):
                return str(value)
            raise TypeError(f"受付Bundleに未対応の値があります: {type(value).__name__}")

        return ReceptionSourceData(
            bundle_json=ReceptionOriginalJson(
                json.dumps(
                    map_bundle(bundle),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=encode,
                )
            ),
            imported_at=imported_at,
            is_follow_up=is_follow_up,
            billing_additions=tuple(
                ReceptionBillingAddition(
                    code=ReceptionBillingCode(addition.code),
                    name=ReceptionBillingName(addition.name),
                    points=ReceptionBillingPoints(addition.points)
                    if addition.points is not None
                    else None,
                    quantity=ReceptionBillingQuantity(addition.quantity)
                    if addition.quantity is not None
                    else None,
                )
                for addition in bundle.additions
            ),
        )

    @staticmethod
    def _replace_source_data(
        reception: Reception, source_data: ReceptionSourceData
    ) -> Reception:
        """新しい受信データを最新スナップショットとして設定し、過去のデータを受信履歴へ追加する。"""
        history = reception.source_data_history
        if reception.source_data is not None:
            history = (*history, reception.source_data)
        return replace(reception, source_data=source_data, source_data_history=history)

    @staticmethod
    def _changed_fields(
        *,
        previous: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...],
        incoming: tuple[tuple[ReceptionFieldPath, ReceptionFingerprint], ...],
    ) -> tuple[ReceptionFieldPath, ...]:
        """前回受信データと今回受信データの差分（追加・変更・削除されたフィールド）をソート順で抽出する。"""
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
        changed_fields: tuple[str, ...] | None,
        missing_values_require_review: bool = False,
    ) -> _PatientProfileApplication:
        """直前の受付データからの変更差分を履歴として記録する。患者属性の自動上書きは行わない。"""
        patient = await load_patient_or_raise(
            self._patient_repo, corporate_id=corporate_id, patient_id=patient_id
        )
        patient_command = self._mapper.to_patient_command(
            bundle, str(corporate_id.value)
        )
        received_profile = PatientProfileSnapshot(
            names=PersonNames(
                kanji=PersonName(
                    last_name=PersonNamePart(patient_command.last_name),
                    first_name=PersonNamePart(patient_command.first_name),
                ),
                kana=PersonNameKana(
                    last_name=PersonNameKanaPart(patient_command.last_name_kana),
                    first_name=PersonNameKanaPart(patient_command.first_name_kana),
                ),
            ),
            birth_date=PatientBirthDate(bundle.patient.birth_date),
            gender=build_optional(bundle.patient.gender, PatientGenderCode),
            postal_code=build_optional(bundle.patient.postal_code, PatientPostalCode),
            address=build_optional(bundle.patient.address, PatientAddress),
            phone_number=build_optional(
                bundle.patient.phone_number, PatientPhoneNumber
            ),
        )
        before_profile = patient.profile_snapshot()
        incoming_values = self._profile_values(received_profile)
        current_values = self._profile_values(before_profile)
        if changed_fields is None:
            event_fields = tuple(
                field
                for field in _PATIENT_PROFILE_FIELD_PATHS
                if incoming_values[field] is not None
                and incoming_values[field] != current_values[field]
            )
        else:
            event_fields = tuple(
                field
                for field in changed_fields
                if field in _PATIENT_PROFILE_FIELD_PATHS
                or field == _EXTERNAL_PATIENT_ID_FIELD_PATH
            )
        conflicts: list[str] = []
        if (
            _EXTERNAL_PATIENT_ID_FIELD_PATH in event_fields
            and changed_fields is not None
        ):
            conflicts.append("external_patient_id")
        for field in _OPTIONAL_PATIENT_PROFILE_FIELD_PATHS:
            if (
                field in event_fields
                and incoming_values[field] is None
                and missing_values_require_review
            ):
                conflicts.append(_PATIENT_PROFILE_CONFLICT_NAMES[field])

        # 現在属性を自動上書きしないため、applied_profile は before_profile のまま維持する
        if not event_fields:
            return _PatientProfileApplication(conflicts=tuple(conflicts))
        change = PatientProfileChange(
            reception_id=reception_id,
            store_id=store_id,
            external_patient_id=ExternalPatientId(bundle.patient.external_patient_id),
            recorded_at=self._clock.now(),
            changed_fields=tuple(PatientProfileField(item) for item in event_fields),
            received_profile=received_profile,
            before_profile=before_profile,
            applied_profile=before_profile,
        )
        updated = patient.record_profile_change(change)
        await self._patient_repo.save(updated)
        return _PatientProfileApplication(
            conflicts=tuple(
                field
                for field in (
                    "external_patient_id",
                    "gender",
                    "postal_code",
                    "address",
                    "phone_number",
                )
                if field in conflicts
            ),
            updated_fields=(),
        )

    @staticmethod
    def _validate_required_insurance_values(bundle: NsipsBundle) -> None:
        """保険数値の文字種と受領情報の完全性を取込前に検証する。"""
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
                "保険者番号・保険者記号・保険者番号は空にできません。"
            )
        if not has_insurance_identity and not has_public_expense:
            raise NsipsParseError("保険または公費の識別情報が必要です。")

    @staticmethod
    def _coverage_review_reason(bundle: NsipsBundle) -> str | None:
        """不完全な受信で資格自動選択しない理由を、優先順位付きで返す。"""
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

    @staticmethod
    def _profile_values(
        profile: PatientProfileSnapshot,
    ) -> dict[str, object | None]:
        """患者プロフィールスナップショットの各属性値をパス形式で辞書へ展開する。"""
        return {
            "patient.kanji_name": profile.names.kanji.full_name,
            "patient.kana_name": profile.names.kana.full_name,
            "patient.birth_date": (
                profile.birth_date.value if profile.birth_date else None
            ),
            "patient.gender": profile.gender.value if profile.gender else None,
            "patient.postal_code": profile.postal_code.value
            if profile.postal_code
            else None,
            "patient.address": profile.address.value if profile.address else None,
            "patient.phone_number": profile.phone_number.value
            if profile.phone_number
            else None,
        }

    async def execute(self, command: IngestNsipsCommand) -> IngestNsipsResultDto:
        """NSIPS取込を一括実行する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        store_id = StoreId.parse(command.store_id)
        reception_id = self._parse_reception_id(command.reception_id)

        # 認可・店舗セッション・有効店舗検証
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_RECEPTION
        )
        AuthorizationService(self._corporate_access.actor).require_store(
            permission=Permission.MANAGE_RECEPTION,
            target_corporate_id=corporate_id,
            target_store_id=store_id,
        )
        store = await self._store_repo.get(store_id=store_id)
        if store is None or store.corporate_id != corporate_id:
            raise TenantBoundaryNotFoundError()
        if store.status != StoreStatus.ACTIVE:
            raise StoreStateConflictError(
                "現在の店舗状態ではこの操作を実行できません。"
            )

        # 入力検証
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
                    "NSIPSのraw形式が対応版として登録されていないため、受け付けられません。"
                )
        self._validate_required_insurance_values(bundle)

        coverage_review_reason = self._coverage_review_reason(bundle)
        incoming_fingerprints = self._fingerprint_bundle(bundle)
        incoming_fingerprint = self._combined_fingerprint(incoming_fingerprints)
        received_at = self._clock.now()
        source_data = self._source_data(
            bundle,
            imported_at=received_at,
            is_follow_up=not bool(bundle.prescription.rps),
        )

        existing_reception = await self._reception_repo.get(
            corporate_id=corporate_id, store_id=store_id, reception_id=reception_id
        )

        # 既存受付の患者同一性検証
        if existing_reception is not None:
            patient_id_path = ReceptionFieldPath(_EXTERNAL_PATIENT_ID_FIELD_PATH)
            previous_patient_id = dict(existing_reception.field_fingerprints).get(
                patient_id_path
            )
            if (
                previous_patient_id is not None
                and previous_patient_id != dict(incoming_fingerprints)[patient_id_path]
            ):
                raise NsipsPatientIdentityConflictError()
            patient_link = await self._patient_external_id_repo.get_active_by_source(
                corporate_id=corporate_id,
                store_id=store_id,
                system_name=ExternalSystemName("recept"),
                external_patient_id=ExternalPatientId(
                    bundle.patient.external_patient_id
                ),
            )
            if (
                patient_link is None
                or patient_link.patient_id != existing_reception.patient_id
            ):
                raise NsipsPatientIdentityConflictError()

        # 初回で更新・削除が指定された場合は404
        if existing_reception is None and bundle.correction_kind in (
            ExternalCorrectionKind.UPDATE,
            ExternalCorrectionKind.DELETE,
        ):
            raise NsipsReceptionNotFoundError(
                "訂正または削除対象の受付が見つかりません。"
            )

        # 既存受付がある場合
        if existing_reception is not None:
            is_deletion = bundle.correction_kind == ExternalCorrectionKind.DELETE
            is_withdrawn = (
                existing_reception.source_status == ReceptionSourceStatus.WITHDRAWN
            )
            # 同一原本の再送（重複）: 通常原本の再送、または取下原本への削除通知の再送
            if existing_reception.latest_fingerprint == incoming_fingerprint and (
                is_deletion == is_withdrawn
            ):
                return IngestNsipsResultDto(
                    reception_id=str(reception_id.value),
                    source_fingerprint=incoming_fingerprint.value,
                    source_status=existing_reception.source_status.value,
                    corporate_id=command.corporate_id,
                    store_id=command.store_id,
                    patient_id=str(existing_reception.patient_id.value),
                    prescription_id=str(existing_reception.prescription_id.value)
                    if existing_reception.prescription_id is not None
                    else None,
                    dispensing_id=str(existing_reception.dispensing_id.value)
                    if existing_reception.dispensing_id is not None
                    else None,
                    medication_history_id=str(
                        existing_reception.medication_history_id.value
                    )
                    if existing_reception.medication_history_id is not None
                    else None,
                    document_number=bundle.prescription.document_number,
                    patient_name=bundle.patient.kanji_name,
                    is_new_patient=False,
                    is_duplicate=True,
                    is_follow_up_only=existing_reception.prescription_id is None
                    and not bool(bundle.prescription.rps),
                    has_pending_correction_review=False,
                    coverage_review_required=coverage_review_reason is not None,
                    coverage_review_reason=coverage_review_reason,
                    dispensed_date=bundle.dispensed_date.isoformat()
                    if bundle.dispensed_date
                    else None,
                    addition_names=tuple(add.name for add in bundle.additions),
                )

            # 内容が異なる訂正: correction_kind と expected_fingerprint の一致を検証
            if bundle.correction_kind not in (
                ExternalCorrectionKind.UPDATE,
                ExternalCorrectionKind.DELETE,
            ):
                raise NsipsSourceConflictError(
                    "既存受付への変更には correction_kind の指定が必要です。"
                )
            if (
                command.expected_fingerprint is None
                or command.expected_fingerprint
                != existing_reception.latest_fingerprint.value
            ):
                raise NsipsSourceConflictError()

            if bundle.correction_kind == ExternalCorrectionKind.DELETE:
                return await self._process_external_deletion_notice(
                    command=command,
                    corporate_id=corporate_id,
                    store_id=store_id,
                    reception=existing_reception,
                    bundle=bundle,
                    source_data=source_data,
                    incoming_fingerprint=incoming_fingerprint,
                    incoming_fingerprints=incoming_fingerprints,
                    received_at=received_at,
                )

            # UPDATE処理
            changed_fields = self._changed_fields(
                previous=existing_reception.field_fingerprints,
                incoming=incoming_fingerprints,
            )
            profile_application = await self._record_patient_profile_change(
                corporate_id=corporate_id,
                patient_id=existing_reception.patient_id,
                reception_id=reception_id,
                store_id=store_id,
                bundle=bundle,
                changed_fields=tuple(path.value for path in changed_fields),
                missing_values_require_review=True,
            )
            patient_attribute_conflicts = profile_application.conflicts

            prescription_changed_fields = [
                path for path in changed_fields if not path.value.startswith("patient.")
            ]
            has_pending_review = False
            if (
                self._medication_history_repo is not None
                and existing_reception.medication_history_id is not None
                and prescription_changed_fields
            ):
                matching_record = await self._medication_history_repo.get(
                    corporate_id=corporate_id,
                    record_id=existing_reception.medication_history_id,
                )
                if matching_record is not None:
                    diff_summary = f"差分項目: {', '.join(path.value for path in prescription_changed_fields)}"
                    external_correction = ExternalPrescriptionCorrection(
                        correction_id=ExternalCorrectionId(
                            self._external_correction_id(
                                record_id_str=str(matching_record.id.value),
                                document_number=bundle.prescription.document_number,
                                fingerprint=incoming_fingerprint,
                            )
                        ),
                        corrected_at=ExternalCorrectionTimestamp(received_at),
                        source_document_number=CorrectionDocumentNumber(
                            bundle.prescription.document_number
                        ),
                        reason=ExternalCorrectionReason(
                            f"レセコン訂正データ受信: {diff_summary}"
                        ),
                        details=ExternalCorrectionDetails(diff_summary),
                        kind=ExternalCorrectionKind.UPDATE,
                    )
                    updated_history = matching_record.record_external_correction(
                        external_correction
                    )
                    await self._medication_history_repo.save(updated_history)
                    has_pending_review = True

            reception_correction = ReceptionCorrection(
                fingerprint=incoming_fingerprint,
                changed_fields=changed_fields,
                received_at=received_at,
            )
            updated_reception = self._replace_source_data(
                existing_reception, source_data
            )
            await self._reception_repo.save(
                replace(
                    updated_reception,
                    latest_fingerprint=incoming_fingerprint,
                    field_fingerprints=incoming_fingerprints,
                    source_status=ReceptionSourceStatus.CURRENT,
                    correction_history=(
                        *existing_reception.correction_history,
                        reception_correction,
                    ),
                )
            )
            return IngestNsipsResultDto(
                reception_id=str(existing_reception.id.value),
                source_fingerprint=incoming_fingerprint.value,
                source_status=ReceptionSourceStatus.CURRENT.value,
                corporate_id=command.corporate_id,
                store_id=command.store_id,
                patient_id=str(existing_reception.patient_id.value),
                prescription_id=str(existing_reception.prescription_id.value)
                if existing_reception.prescription_id is not None
                else None,
                dispensing_id=str(existing_reception.dispensing_id.value)
                if existing_reception.dispensing_id is not None
                else None,
                medication_history_id=str(
                    existing_reception.medication_history_id.value
                )
                if existing_reception.medication_history_id is not None
                else None,
                document_number=bundle.prescription.document_number,
                patient_name=bundle.patient.kanji_name,
                is_new_patient=False,
                is_duplicate=False,
                is_follow_up_only=existing_reception.prescription_id is None
                and not bool(bundle.prescription.rps),
                has_pending_correction_review=has_pending_review
                or bool(patient_attribute_conflicts),
                patient_attribute_conflicts=patient_attribute_conflicts,
                patient_profile_updated_fields=(),
                coverage_review_required=coverage_review_reason is not None,
                coverage_review_reason=coverage_review_reason,
                dispensed_date=bundle.dispensed_date.isoformat()
                if bundle.dispensed_date
                else None,
                addition_names=tuple(add.name for add in bundle.additions),
            )

        # 初回受信処理
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
            profile_application = await self._record_patient_profile_change(
                corporate_id=corporate_id,
                patient_id=active_link.patient_id,
                reception_id=reception_id,
                store_id=store_id,
                bundle=bundle,
                changed_fields=None,
            )
            patient_attribute_conflicts = profile_application.conflicts
        else:
            patient_cmd = self._mapper.to_patient_command(bundle, command.corporate_id)
            new_patient_id = await self._register_patient_use_case.execute(patient_cmd)
            patient_id_str = str(new_patient_id.value)
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

        # 原本Receptionの保存（内部処方・調剤・薬歴は初回 null）
        await self._reception_repo.save(
            Reception(
                id=reception_id,
                corporate_id=corporate_id,
                store_id=store_id,
                patient_id=PatientId.parse(patient_id_str),
                prescription_id=None,
                dispensing_id=None,
                medication_history_id=None,
                latest_fingerprint=incoming_fingerprint,
                field_fingerprints=incoming_fingerprints,
                source_data=source_data,
                source_status=ReceptionSourceStatus.CURRENT,
            )
        )
        return IngestNsipsResultDto(
            reception_id=str(reception_id.value),
            source_fingerprint=incoming_fingerprint.value,
            source_status=ReceptionSourceStatus.CURRENT.value,
            corporate_id=command.corporate_id,
            store_id=command.store_id,
            patient_id=patient_id_str,
            prescription_id=None,
            dispensing_id=None,
            medication_history_id=None,
            follow_up_id=None,
            document_number=bundle.prescription.document_number,
            patient_name=bundle.patient.kanji_name,
            is_new_patient=is_new_patient,
            is_duplicate=False,
            is_follow_up_only=not bool(bundle.prescription.rps),
            has_pending_correction_review=False,
            patient_attribute_conflicts=patient_attribute_conflicts,
            patient_profile_updated_fields=(),
            coverage_review_required=coverage_review_reason is not None,
            coverage_review_reason=coverage_review_reason,
            dispensed_date=bundle.dispensed_date.isoformat()
            if bundle.dispensed_date
            else None,
            addition_names=tuple(add.name for add in bundle.additions),
        )

    async def _process_external_deletion_notice(
        self,
        *,
        command: IngestNsipsCommand,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception: Reception,
        bundle: NsipsBundle,
        source_data: ReceptionSourceData,
        incoming_fingerprint: ReceptionFingerprint,
        incoming_fingerprints: tuple[
            tuple[ReceptionFieldPath, ReceptionFingerprint], ...
        ],
        received_at: datetime,
    ) -> IngestNsipsResultDto:
        """外部削除通知を受理し、原本状態をwithdrawnにし、接続薬歴があれば未判断通知を記録する。

        内部の処方・調剤・薬歴の物理削除や自動取消は行わない。
        """
        has_pending_review = False
        history_id = reception.medication_history_id
        if history_id is not None and self._medication_history_repo is not None:
            history = await self._medication_history_repo.get(
                corporate_id=corporate_id, record_id=history_id
            )
            if history is not None:
                correction = ExternalPrescriptionCorrection(
                    correction_id=ExternalCorrectionId(
                        self._external_correction_id(
                            record_id_str=str(history.id.value),
                            document_number=bundle.prescription.document_number,
                            fingerprint=incoming_fingerprint,
                        )
                    ),
                    corrected_at=ExternalCorrectionTimestamp(received_at),
                    source_document_number=CorrectionDocumentNumber(
                        bundle.prescription.document_number
                    ),
                    reason=ExternalCorrectionReason("NSIPS削除通知を受信しました。"),
                    details=ExternalCorrectionDetails(
                        "対象処方の削除が通知されました。"
                    ),
                    kind=ExternalCorrectionKind.DELETE,
                )
                await self._medication_history_repo.save(
                    history.record_external_correction(correction)
                )
                has_pending_review = True

        changed_fields = self._changed_fields(
            previous=reception.field_fingerprints, incoming=incoming_fingerprints
        )
        updated_reception = self._replace_source_data(reception, source_data)
        await self._reception_repo.save(
            replace(
                updated_reception,
                latest_fingerprint=incoming_fingerprint,
                field_fingerprints=incoming_fingerprints,
                source_status=ReceptionSourceStatus.WITHDRAWN,
                correction_history=(
                    *reception.correction_history,
                    ReceptionCorrection(
                        fingerprint=incoming_fingerprint,
                        changed_fields=changed_fields,
                        received_at=received_at,
                    ),
                ),
            )
        )
        return IngestNsipsResultDto(
            reception_id=str(reception.id.value),
            source_fingerprint=incoming_fingerprint.value,
            source_status=ReceptionSourceStatus.WITHDRAWN.value,
            corporate_id=command.corporate_id,
            store_id=command.store_id,
            patient_id=str(reception.patient_id.value),
            prescription_id=str(reception.prescription_id.value)
            if reception.prescription_id is not None
            else None,
            dispensing_id=str(reception.dispensing_id.value)
            if reception.dispensing_id is not None
            else None,
            medication_history_id=str(history_id.value)
            if history_id is not None
            else None,
            document_number=bundle.prescription.document_number,
            patient_name=bundle.patient.kanji_name,
            is_new_patient=False,
            is_duplicate=False,
            has_pending_correction_review=has_pending_review,
            dispensed_date=bundle.dispensed_date.isoformat()
            if bundle.dispensed_date
            else None,
            addition_names=tuple(add.name for add in bundle.additions),
        )
