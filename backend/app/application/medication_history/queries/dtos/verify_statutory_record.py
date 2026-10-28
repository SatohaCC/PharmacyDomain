"""Applicationのverify_statutory_recordを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.medication_history.primitives import StatutoryRecordBlocker
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
            substitutes_dispensing_record=sufficiency.substitutes_dispensing_record,
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
