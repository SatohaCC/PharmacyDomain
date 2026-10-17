"""薬歴集約のフォローアップとトレーシング報告の子エンティティ。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import ClassVar, Self

from app.domain.foundation.entity import Entity
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import (
    SoapContentRequiredError,
    TracingReportAlreadyRespondedError,
    TracingReportResponseDateBeforeProvidedError,
)
from app.domain.medication_history.identifiers import (
    FollowUpId,
    TracingReportId,
)
from app.domain.medication_history.primitives import (
    CounselingMethod,
    CounselingTimestamp,
    FollowUpRecordedTimestamp,
    MedicationHistorySourceSystem,
    PhysicianName,
    TracingReportCategory,
    TracingReportContent,
    TracingReportDeliveryMethod,
    TracingReportFeeCategory,
    TracingReportTimestamp,
)
from app.domain.medication_history.reference_primitives import (
    MedicalInstitutionName,
)
from app.domain.medication_history.value_objects import (
    CategorizedNote,
    HandbookStatus,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
    TracingReportResponse,
)
from app.domain.staff.identifiers import StaffId


@dataclass(frozen=True, eq=False, kw_only=True)
class FollowUpRecord(Entity[FollowUpId]):
    """服薬期間中のフォローアップ（調剤後フォロー）記録。

    固有の識別子（FollowUpId）で同一性を持つ集約内子エンティティ。
    """

    id: FollowUpId
    counselor_id: StaffId
    followed_up_at: CounselingTimestamp
    method: CounselingMethod | None
    soap: SoapRecord
    handbook_status: HandbookStatus | None
    residual_drug: ResidualDrugRecord | None
    information_sheet_provided: bool | None = False
    source_system: MedicationHistorySourceSystem | None = None
    recorded_at: FollowUpRecordedTimestamp | None = None
    recorded_by: StaffId | None = None
    profile_updates: ProfileUpdateIntents = field(default_factory=ProfileUpdateIntents)
    additional_notes: tuple[CategorizedNote, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "フォローアップID",
        "counselor_id": "指導薬剤師",
        "followed_up_at": "フォローアップ日時",
        "method": "実施方法",
        "soap": "SOAP記録",
        "handbook_status": "お薬手帳確認",
        "residual_drug": "残薬確認",
        "information_sheet_provided": "情報提供文書有無",
        "source_system": "記録由来システム",
        "profile_updates": "頭書き差分",
        "additional_notes": "追加記載メモ",
    }

    def validate(self) -> None:
        """白紙のフォローアップ記録を拒否する。"""
        if (self.recorded_at is None) != (self.recorded_by is None):
            raise DomainValidationError(
                "フォローアップ登録日時と登録者は両方設定するか、両方未設定にしてください。"
            )
        has_soap = self.soap.has_content
        has_additional = any(note.has_content for note in self.additional_notes)
        if not has_soap and not has_additional:
            raise SoapContentRequiredError()


@dataclass(frozen=True, eq=False, kw_only=True)
class TracingReport(Entity[TracingReportId]):
    """処方医への服薬情報等提供（トレーシングレポート）記録。

    固有の識別子（TracingReportId）を持ち、処方医返答の受領・記録という
    状態遷移（ライフサイクル）を持つ集約内子エンティティ。
    """

    id: TracingReportId
    reporter_id: StaffId
    provided_at: TracingReportTimestamp
    medical_institution_name: MedicalInstitutionName
    physician_name: PhysicianName
    category: TracingReportCategory
    fee_category: TracingReportFeeCategory
    delivery_method: TracingReportDeliveryMethod
    content: TracingReportContent
    response: TracingReportResponse | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "id": "トレーシングレポートID",
        "reporter_id": "作成薬剤師",
        "provided_at": "提供日時",
        "medical_institution_name": "提供先医療機関",
        "physician_name": "提供先処方医",
        "category": "提供区分",
        "fee_category": "算定区分",
        "delivery_method": "提供手段",
        "content": "提供内容",
        "response": "医師返答",
    }

    @property
    def is_responded(self) -> bool:
        """医師からの返答が記録されているか。"""
        return self.response is not None

    def record_response(self, response: TracingReportResponse) -> Self:
        """処方医からの返答を記録する。

        Raises:
            TracingReportAlreadyRespondedError: 既に返答が記録されている場合。
            TracingReportResponseDateBeforeProvidedError: 返答日時が提供日時より前の場合。
        """
        if self.response is not None:
            raise TracingReportAlreadyRespondedError()
        if response.responded_at.value < self.provided_at.value:
            raise TracingReportResponseDateBeforeProvidedError()
        return replace(self, response=response)
