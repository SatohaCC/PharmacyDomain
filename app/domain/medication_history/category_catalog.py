"""法人別薬歴記載区分カタログ集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.medication_history.exceptions import (
    DuplicateMajorCategoryError,
    DuplicateMediumCategoryError,
    MajorCategoryNotFoundError,
    RequiredCategoryMissingError,
)
from app.domain.medication_history.primitives import (
    CategoryCatalogId,
    MajorCategoryCode,
    MajorCategoryName,
    MedicationHistoryRecordKind,
    MediumCategoryCode,
    MediumCategoryName,
)
from app.domain.medication_history.value_objects import (
    MajorCategoryDefinition,
    MediumCategoryDefinition,
)

if TYPE_CHECKING:
    from app.domain.medication_history.medication_history_record import (
        MedicationHistoryRecord,
    )


_SOAP_SECTION_MAPPING: dict[str, str] = {
    "s": "subjective",
    "o": "objective",
    "a": "assessment",
    "p": "plan",
}


@dataclass(frozen=True, eq=False, kw_only=True)
class MedicationHistoryCategoryCatalog(AggregateRoot[CategoryCatalogId]):
    """法人ごとの薬歴記載区分（大区分・中区分）を管理する集約ルート。"""

    id: CategoryCatalogId
    corporate_id: CorporateId
    major_categories: tuple[MajorCategoryDefinition, ...]
    medium_categories: tuple[MediumCategoryDefinition, ...]

    def validate(self) -> None:
        """集約の不変条件（大区分の存在、コード重複防止等）を検証する。"""
        # 大区分コードの重複検証
        major_codes = [m.code.value for m in self.major_categories]
        if len(major_codes) != len(set(major_codes)):
            raise DuplicateMajorCategoryError()

        # 中区分コードの重複検証
        medium_codes = [m.code.value for m in self.medium_categories]
        if len(medium_codes) != len(set(medium_codes)):
            raise DuplicateMediumCategoryError()

        # 中区分の親大区分コードの存在確認
        major_code_set = set(major_codes)
        for med in self.medium_categories:
            if med.major_category_code.value not in major_code_set:
                raise MajorCategoryNotFoundError()

    @classmethod
    def create_default(cls, *, corporate_id: CorporateId) -> Self:
        """新規法人向けの標準区分カタログを構築する。"""
        soap_code = MajorCategoryCode("soap")
        statutory_code = MajorCategoryCode("statutory")

        major_categories = (
            MajorCategoryDefinition(
                code=soap_code,
                name=MajorCategoryName("SOAP"),
                display_order=1,
            ),
            MajorCategoryDefinition(
                code=statutory_code,
                name=MajorCategoryName("法令"),
                display_order=2,
            ),
        )

        medium_categories = (
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S（主観的情報）"),
                display_order=1,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("o"),
                major_category_code=soap_code,
                name=MediumCategoryName("O（客観的情報）"),
                display_order=2,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("a"),
                major_category_code=soap_code,
                name=MediumCategoryName("A（評価・判断）"),
                display_order=3,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P（計画・指導）"),
                display_order=4,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("handbook"),
                major_category_code=statutory_code,
                name=MediumCategoryName("お薬手帳"),
                display_order=5,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("residual_drug"),
                major_category_code=statutory_code,
                name=MediumCategoryName("残薬確認"),
                display_order=6,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("concurrent_medication"),
                major_category_code=statutory_code,
                name=MediumCategoryName("併用薬確認"),
                display_order=7,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("other"),
                major_category_code=statutory_code,
                name=MediumCategoryName("その他"),
                display_order=8,
            ),
        )

        return cls(
            id=CategoryCatalogId.generate(),
            corporate_id=corporate_id,
            major_categories=major_categories,
            medium_categories=medium_categories,
        )

    def add_major_category(self, definition: MajorCategoryDefinition) -> Self:
        """大区分を追加する。"""
        if any(m.code == definition.code for m in self.major_categories):
            raise DuplicateMajorCategoryError()
        return replace(self, major_categories=(*self.major_categories, definition))

    def update_major_category(self, definition: MajorCategoryDefinition) -> Self:
        """既存の大区分を更新する。"""
        new_majors = tuple(
            definition if m.code == definition.code else m
            for m in self.major_categories
        )
        return replace(self, major_categories=new_majors)

    def add_medium_category(self, definition: MediumCategoryDefinition) -> Self:
        """中区分を追加する。"""
        if any(m.code == definition.code for m in self.medium_categories):
            raise DuplicateMediumCategoryError()
        return replace(self, medium_categories=(*self.medium_categories, definition))

    def update_medium_category(self, definition: MediumCategoryDefinition) -> Self:
        """既存の中区分を更新する。"""
        new_mediums = tuple(
            definition if m.code == definition.code else m
            for m in self.medium_categories
        )
        return replace(self, medium_categories=new_mediums)

    def medium_categories_for(
        self, major_code: MajorCategoryCode
    ) -> tuple[MediumCategoryDefinition, ...]:
        """指定した大区分に属する中区分を表示順に返す。"""
        matched = [
            m for m in self.medium_categories if m.major_category_code == major_code
        ]
        return tuple(sorted(matched, key=lambda m: m.display_order))

    def required_medium_categories(self) -> tuple[MediumCategoryDefinition, ...]:
        """法人ルールとして確定時に必須とされている有効な中区分を返す。"""
        required = [m for m in self.medium_categories if m.is_required and m.is_enabled]
        return tuple(sorted(required, key=lambda m: m.display_order))

    def validate_record_compliance(self, record: MedicationHistoryRecord) -> None:
        """薬歴記録が本カタログの法人必須ルールを満たしているか検証する。"""
        if record.record_kind is MedicationHistoryRecordKind.FOLLOW_UP:
            return
        required_mediums = self.required_medium_categories()
        for req in required_mediums:
            code_val = req.code.value.lower()
            if code_val in _SOAP_SECTION_MAPPING:
                field_name = _SOAP_SECTION_MAPPING[code_val]
                notes = getattr(record.effective_soap, field_name)
                if not any(note.has_content for note in notes):
                    raise RequiredCategoryMissingError(
                        medium_category_name=req.name.value
                    )
            else:
                has_in_additional = any(
                    note.medium_category_code == req.code and note.has_content
                    for note in record.additional_notes
                )
                if not has_in_additional:
                    raise RequiredCategoryMissingError(
                        medium_category_name=req.name.value
                    )
