"""薬歴が調剤録の代替になるかを確認する処理。

薬剤師法第28条の調剤録の記載事項（施行規則第16条第1項）は、薬歴・調剤・処方箋・
患者に分かれて存在する。ここは材料を集めて Domain Service へ渡す運び役であり、
充足の判定そのものは持たない。

**報告であって強制ではない。** 記載が足りない薬歴の確定をここで止めはしない。
所在地の未記録や患者生年月日の欠落は服薬指導そのものの瑕疵ではなく、指導記録を
残せなくするほうが害が大きい。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.medication_history.reference import (
    DispensingReferenceBoundary,
    StatutoryRecordSourceBoundary,
)
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import (
    MedicationHistoryRecordId,
    StatutoryRecordBlocker,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import StatutoryDispensingRecordService
from app.domain.medication_history.value_objects import (
    StatutoryItemAssessment,
    StatutoryRecordSufficiency,
)


@dataclass(frozen=True, kw_only=True)
class StatutoryItemAssessmentDto:
    """記載事項1つの判定結果の出力DTO。"""

    item: str
    item_label: str
    article_clause: str
    state: str
    state_label: str

    @classmethod
    def from_value(cls, value: StatutoryItemAssessment) -> StatutoryItemAssessmentDto:
        """判定結果からDTOを生成する。"""
        return cls(
            item=value.item.value,
            item_label=value.item.label,
            article_clause=value.item.article_clause,
            state=value.state.value,
            state_label=value.state.label,
        )


@dataclass(frozen=True, kw_only=True)
class StatutoryRecordBlockerDto:
    """調剤録の代替を妨げる要因の出力DTO。"""

    blocker: str
    blocker_label: str

    @classmethod
    def from_value(cls, value: StatutoryRecordBlocker) -> StatutoryRecordBlockerDto:
        """妨げる要因からDTOを生成する。"""
        return cls(blocker=value.value, blocker_label=value.label)


@dataclass(frozen=True, kw_only=True)
class StatutoryRecordSufficiencyDto:
    """調剤録の代替可否の出力DTO。"""

    record_id: str
    dispensing_id: str
    prescription_id: str
    substitutes_dispensing_record: bool
    assessments: tuple[StatutoryItemAssessmentDto, ...]
    blockers: tuple[StatutoryRecordBlockerDto, ...]
    missing_items: tuple[str, ...]

    @classmethod
    def from_value(
        cls,
        sufficiency: StatutoryRecordSufficiency,
        *,
        record_id: str,
        dispensing_id: str,
        prescription_id: str,
    ) -> StatutoryRecordSufficiencyDto:
        """判定結果からDTOを生成する。"""
        return cls(
            record_id=record_id,
            dispensing_id=dispensing_id,
            prescription_id=prescription_id,
            substitutes_dispensing_record=(sufficiency.substitutes_dispensing_record),
            assessments=tuple(
                StatutoryItemAssessmentDto.from_value(assessment)
                for assessment in sufficiency.assessments
            ),
            blockers=tuple(
                StatutoryRecordBlockerDto.from_value(blocker)
                for blocker in sufficiency.blockers
            ),
            missing_items=tuple(item.value for item in sufficiency.missing_items),
        )


@dataclass(frozen=True, kw_only=True)
class VerifyStatutoryRecordQuery:
    """調剤録代替の確認の入力データ。"""

    corporate_id: str
    record_id: str


class VerifyStatutoryRecordUseCase:
    """薬歴が調剤録の記載事項を満たすかを確認する。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        dispensing_source: DispensingReferenceBoundary,
        statutory_source: StatutoryRecordSourceBoundary,
        service: StatutoryDispensingRecordService,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._dispensing_source = dispensing_source
        self._statutory_source = statutory_source
        self._service = service

    async def execute(
        self, query: VerifyStatutoryRecordQuery
    ) -> StatutoryRecordSufficiencyDto:
        """指定法人の薬歴について、調剤録の代替可否をDTOで返す。

        確定済に限らない。足りないものを確定の前に知るための問い合わせでもある。

        氏名を問い合わせるのは調剤した薬剤師と指導した薬剤師の2人だけ。最終鑑査者は
        施行規則第16条第1項第五号の対象ではないので、ここでは尋ねない。
        """
        corporate_id = CorporateId.parse(query.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.VIEW_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(query.record_id),
        )
        dispensing = await self._dispensing_source.get_or_raise(
            corporate_id=corporate_id,
            dispensing_id=record.dispensing_id,
        )
        source = await self._statutory_source.build(
            corporate_id=corporate_id,
            patient_id=record.patient_id,
            prescription_id=record.prescription_id,
            staff_ids=frozenset({dispensing.dispenser_id, record.counselor_id}),
        )
        return StatutoryRecordSufficiencyDto.from_value(
            self._service.verify(record, dispensing, source),
            record_id=str(record.id.value),
            dispensing_id=str(record.dispensing_id.value),
            prescription_id=str(record.prescription_id.value),
        )


__all__ = [
    "StatutoryItemAssessmentDto",
    "StatutoryRecordBlockerDto",
    "StatutoryRecordSufficiencyDto",
    "VerifyStatutoryRecordQuery",
    "VerifyStatutoryRecordUseCase",
]
