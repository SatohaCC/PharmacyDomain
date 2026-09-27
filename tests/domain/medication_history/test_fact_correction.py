"""確定済み薬歴の事実訂正を原本と独立した履歴として検証する。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol, cast

import pytest

from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    BillingAdditionCode,
    BillingAdditionName,
    CounselingMethod,
    CounselingNote,
    CounselingTimestamp,
    FinalizationDelayReason,
    GenericPreferenceType,
    MajorCategoryCode,
    MedicationHistoryImportTimestamp,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
    MediumCategoryCode,
    ResidualDrugQuantity,
    ResidualDrugReason,
)
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    FamilyPharmacistIntent,
    GenericPreferenceIntent,
    ProfileUpdateIntents,
    ResidualDrugRecord,
    SoapRecord,
)
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    create_adverse_reaction_intent,
    create_allergy_intent,
    create_concurrent_intent,
    create_condition_intent,
    create_generic_preference_intents,
    create_handbook_status,
    create_lifestyle_intents,
    create_record,
    create_retract_adverse_reaction_intent,
    create_retract_allergy_intent,
    create_retract_condition_intent,
    create_stop_intent,
    create_update_condition_status_intent,
    finalize_record_with_review,
)

_CORRECTED_AT = datetime(2026, 8, 25, 3, tzinfo=UTC)
_CORRECTOR = StaffId.generate()
_ABSENT = object()


class _CorrectableRecord(Protocol):
    """承認済み計画が要求する薬歴の公開訂正契約。"""

    @property
    def effective_facts(self) -> Any: ...

    @property
    def fact_corrections(self) -> tuple[Any, ...]: ...

    def fact_elements(self, field_name: str) -> tuple[Any, ...]: ...

    def correct_fact(
        self,
        *,
        target: str,
        operation: str,
        reason: str,
        corrected_by: StaffId,
        recorded_at: datetime,
        value: object = _ABSENT,
    ) -> MedicationHistoryRecord: ...


def _api(record: MedicationHistoryRecord) -> _CorrectableRecord:
    """API が未実装の場合も、収集エラーではなく契約の失敗にする。"""
    assert callable(getattr(record, "correct_fact", None)), "薬歴の事実訂正 API が必要"
    return cast(_CorrectableRecord, record)


def _correct(
    record: MedicationHistoryRecord,
    *,
    target: str,
    operation: str = "replace",
    value: object = _ABSENT,
    reason: str = "原記録の誤記を訂正した。",
    corrected_by: StaffId = _CORRECTOR,
    recorded_at: datetime = _CORRECTED_AT,
) -> MedicationHistoryRecord:
    """新しい訂正を1件追記する。値の欠落と明示 null を区別する。"""
    arguments: dict[str, object] = {
        "target": target,
        "operation": operation,
        "reason": reason,
        "corrected_by": corrected_by,
        "recorded_at": recorded_at,
    }
    if value is not _ABSENT:
        arguments["value"] = value
    return _api(record).correct_fact(**cast(Any, arguments))


def _facts(record: MedicationHistoryRecord) -> Any:
    return _api(record).effective_facts


def _events(record: MedicationHistoryRecord) -> tuple[Any, ...]:
    return _api(record).fact_corrections


def _elements(record: MedicationHistoryRecord, field_name: str) -> tuple[Any, ...]:
    return _api(record).fact_elements(field_name)


def _element_id(record: MedicationHistoryRecord, field_name: str, index: int) -> str:
    return str(_plain(_elements(record, field_name)[index].id))


def _plain(value: object) -> object:
    return getattr(value, "value", value)


def _finalized(**overrides: Any) -> MedicationHistoryRecord:
    record = create_record(**overrides)
    return finalize_record_with_review(record)


def _note(text: str) -> CategorizedNote:
    return CategorizedNote(
        major_category_code=MajorCategoryCode("01"),
        medium_category_code=MediumCategoryCode("01-01"),
        text=CounselingNote(text),
    )


def _addition(name: str) -> BillingAddition:
    return BillingAddition(
        code=BillingAdditionCode("A001"),
        name=BillingAdditionName(name),
        points=10,
        quantity=1,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("method", CounselingMethod.TELEPHONE),
        ("handbook_status", create_handbook_status(presented=False)),
        (
            "residual_drug",
            ResidualDrugRecord(
                has_residual_drugs=True,
                quantity=ResidualDrugQuantity(2),
                reason=ResidualDrugReason("飲み忘れがあった。"),
            ),
        ),
        ("information_sheet_provided", True),
        ("source_system", MedicationHistorySourceSystem("NSIPS")),
        ("delay_reason", FinalizationDelayReason("記録を確認した。")),
        (
            "review_result",
            MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS,
        ),
    ),
)
def test_tc01_許可された単純フィールドを型を保って訂正する(
    field_name: str, value: object
) -> None:
    original = _finalized()

    corrected = _correct(original, target=field_name, value=value)

    assert getattr(_facts(corrected), field_name) == value
    assert getattr(original, field_name) == getattr(corrected, field_name)
    assert _events(corrected)[-1].before == getattr(original, field_name)
    assert _events(corrected)[-1].after == value


@pytest.mark.parametrize(
    "field_name",
    (
        "information_sheet_provided",
        "source_system",
        "handbook_status",
        "residual_drug",
    ),
)
def test_tc03_任意項目の明示的な解除は値欠落と区別する(field_name: str) -> None:
    original = replace(
        _finalized(),
        source_system=MedicationHistorySourceSystem("NSIPS"),
        imported_at=MedicationHistoryImportTimestamp(_CORRECTED_AT),
    )

    corrected = _correct(original, target=field_name, value=None)

    assert getattr(_facts(corrected), field_name) is None
    assert _events(corrected)[-1].before == getattr(original, field_name)
    assert _events(corrected)[-1].after is None


@pytest.mark.parametrize(
    "field_name", ("method", "counselor_id", "counseled_at", "review_result")
)
def test_tc04_確定記録の必須値を解除できない(field_name: str) -> None:
    original = _finalized()

    with pytest.raises(MedicationHistoryDomainError):
        _correct(original, target=field_name, value=None)

    assert getattr(original, field_name) is not None
    assert _events(original) == ()


def test_tc05_指導日時を確定監査日時より後にできない() -> None:
    original = _finalized()
    assert original.finalized_at is not None

    with pytest.raises(MedicationHistoryDomainError):
        _correct(
            original,
            target="counseled_at",
            value=CounselingTimestamp(
                original.finalized_at.value + timedelta(minutes=1)
            ),
        )

    assert _events(original) == ()


def test_tc06_指導日が確定日と異なる訂正には遅延理由が要る() -> None:
    original = _finalized()
    assert original.counseled_at is not None
    previous_day = CounselingTimestamp(original.counseled_at.value - timedelta(days=1))

    with pytest.raises(MedicationHistoryDomainError):
        _correct(original, target="counseled_at", value=previous_day)
    with_reason = _correct(
        original,
        target="delay_reason",
        value=FinalizationDelayReason("翌日に記録を確定した。"),
    )
    corrected = _correct(with_reason, target="counseled_at", value=previous_day)

    assert _facts(corrected).counseled_at == previous_day
    assert corrected.finalized_at == original.finalized_at
    assert len(_events(corrected)) == 2


def test_tc07_レビュー結果は薬剤師の評価記載と整合する() -> None:
    draft = create_record(
        soap=SoapRecord(subjective=(create_record().soap.subjective[0],))
    )
    original = finalize_record_with_review(
        draft,
        review_result=MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS,
    )

    with pytest.raises(MedicationHistoryDomainError):
        _correct(
            original,
            target="review_result",
            value=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
        )

    assert _events(original) == ()


def test_tc08_下書きは事実訂正経路を使えない() -> None:
    draft = create_record()

    with pytest.raises(MedicationHistoryDomainError):
        _correct(draft, target="method", value=CounselingMethod.TELEPHONE)

    assert _events(draft) == ()


def test_tc09_移行記録は確定監査値を創作せず訂正できる() -> None:
    original = replace(create_record(), status=MedicationHistoryStatus.LEGACY_RECORDED)

    corrected = _correct(original, target="method", value=CounselingMethod.TELEPHONE)

    assert _facts(corrected).method == CounselingMethod.TELEPHONE
    assert corrected.finalized_at is None
    assert corrected.finalized_by is None
    assert corrected.review_result is None
    assert len(_events(corrected)) == 1


@pytest.mark.parametrize(
    "target",
    (
        "event_id",
        "corporate_id",
        "store_id",
        "patient_id",
        "prescription_id",
        "dispensing_id",
        "soap",
        "imported_at",
        "recorded_at",
        "recorded_by",
        "finalized_at",
        "finalized_by",
        "status",
        "retention_expiry_date",
        "external_corrections",
        "tracing_reports",
    ),
)
def test_tc10_監査値や集約参照は訂正対象にできない(target: str) -> None:
    original = _finalized()

    with pytest.raises(MedicationHistoryDomainError):
        _correct(original, target=target, value="別の値")

    assert _events(original) == ()


def test_tc11_連続訂正は直前の有効値を前値として追記する() -> None:
    original = replace(
        _finalized(), source_system=MedicationHistorySourceSystem("NSIPS")
    )
    first = _correct(
        original,
        target="source_system",
        value=MedicationHistorySourceSystem("MANUAL"),
        recorded_at=_CORRECTED_AT + timedelta(hours=1),
    )
    second = _correct(
        first,
        target="source_system",
        value=MedicationHistorySourceSystem("OTHER"),
        recorded_at=_CORRECTED_AT,
    )

    assert _plain(original.source_system) == "NSIPS"
    assert [_plain(event.before) for event in _events(second)] == ["NSIPS", "MANUAL"]
    assert [_plain(event.after) for event in _events(second)] == ["MANUAL", "OTHER"]
    assert _plain(_facts(second).source_system) == "OTHER"


def test_tc12_同じ訂正IDを二重に復元できない() -> None:
    corrected = _correct(
        _finalized(), target="method", value=CounselingMethod.TELEPHONE
    )
    event = _events(corrected)[0]

    with pytest.raises(MedicationHistoryDomainError):
        replace(corrected, **cast(Any, {"fact_corrections": (event, event)}))


def test_tc13_原本要素IDは同名でも別で再読込後も安定する() -> None:
    updates = ProfileUpdateIntents(
        new_allergies=(create_allergy_intent(), create_allergy_intent())
    )
    original = _finalized(profile_updates=updates)
    another = _finalized(profile_updates=updates)
    field_name = "profile_updates.new_allergies"
    ids = tuple(item.id for item in _elements(original, field_name))

    corrected = _correct(
        original,
        target=str(ids[0]),
        value=create_allergy_intent(reaction="蕁麻疹"),
    )

    assert len(set(ids)) == 2
    assert ids[0] not in {item.id for item in _elements(another, field_name)}
    assert tuple(item.id for item in _elements(corrected, field_name)) == ids


def test_tc14_同名の原本Intentを1件だけ置換する() -> None:
    originals = (create_allergy_intent(), create_allergy_intent())
    record = _finalized(profile_updates=ProfileUpdateIntents(new_allergies=originals))
    element_id = _element_id(record, "profile_updates.new_allergies", 0)
    replacement = create_allergy_intent(reaction="蕁麻疹")

    corrected = _correct(record, target=element_id, value=replacement)

    assert _facts(corrected).profile_updates.new_allergies == (
        replacement,
        originals[1],
    )
    assert corrected.profile_updates.new_allergies == originals
    assert _events(corrected)[0].target == element_id


def test_tc16_欠落Intentを追加して原本配列は空のままにする() -> None:
    record = _finalized()
    new_intent = create_allergy_intent()

    corrected = _correct(
        record,
        target="profile_updates.new_allergies",
        operation="append",
        value=new_intent,
    )

    assert record.profile_updates.new_allergies == ()
    assert _facts(corrected).profile_updates.new_allergies == (new_intent,)
    assert _events(corrected)[0].before is None
    assert _events(corrected)[0].after == new_intent
    assert _element_id(corrected, "profile_updates.new_allergies", 0)


@pytest.mark.parametrize("operation", ("replace", "retract"))
def test_tc17_追加した要素を同じIDで後から訂正できる(operation: str) -> None:
    added = _correct(
        _finalized(),
        target="profile_updates.new_allergies",
        operation="append",
        value=create_allergy_intent(),
    )
    element_id = _element_id(added, "profile_updates.new_allergies", 0)
    replacement = create_allergy_intent(reaction="蕁麻疹")

    corrected = _correct(
        added,
        target=element_id,
        operation=operation,
        value=replacement if operation == "replace" else _ABSENT,
    )

    assert len(_events(corrected)) == 2
    assert _events(corrected)[0].after == create_allergy_intent()
    assert _events(corrected)[1].before == create_allergy_intent()
    assert _events(corrected)[1].target == element_id
    expected = (replacement,) if operation == "replace" else ()
    assert _facts(corrected).profile_updates.new_allergies == expected


@pytest.mark.parametrize(
    ("field_name", "original", "replacement"),
    (
        (
            "lifestyle_update",
            create_lifestyle_intents().lifestyle_update,
            create_lifestyle_intents("夜間の間食あり。").lifestyle_update,
        ),
        (
            "generic_preference_update",
            create_generic_preference_intents().generic_preference_update,
            GenericPreferenceIntent(preference=GenericPreferenceType.REFUSES),
        ),
        (
            "family_pharmacist_update",
            FamilyPharmacistIntent(
                pharmacist_id=StaffId.generate(), agreed_on=date(2026, 8, 1)
            ),
            FamilyPharmacistIntent(
                pharmacist_id=StaffId.generate(), agreed_on=date(2026, 8, 2)
            ),
        ),
    ),
)
def test_tc18_単数Intentはフィールド指定で置換と取消しができる(
    field_name: str, original: object, replacement: object
) -> None:
    record = _finalized(
        profile_updates=ProfileUpdateIntents(**cast(Any, {field_name: original}))
    )
    target = f"profile_updates.{field_name}"

    corrected = _correct(record, target=target, value=replacement)
    retracted = _correct(corrected, target=target, operation="retract")

    assert getattr(record.profile_updates, field_name) == original
    assert getattr(_facts(corrected).profile_updates, field_name) == replacement
    assert getattr(_facts(retracted).profile_updates, field_name) is None
    assert [_plain(event.operation) for event in _events(retracted)] == [
        "replace",
        "retract",
    ]


@pytest.mark.parametrize(
    ("field_name", "original", "replacement"),
    (
        (
            "new_allergies",
            create_allergy_intent(),
            create_allergy_intent(reaction="蕁麻疹"),
        ),
        (
            "retracted_allergies",
            create_retract_allergy_intent(),
            create_retract_allergy_intent(reason="誤記と判明。"),
        ),
        (
            "new_adverse_reactions",
            create_adverse_reaction_intent(),
            create_adverse_reaction_intent(symptom="浮腫"),
        ),
        (
            "retracted_adverse_reactions",
            create_retract_adverse_reaction_intent(),
            create_retract_adverse_reaction_intent(reason="本人に確認した。"),
        ),
        ("new_conditions", create_condition_intent(), create_condition_intent("喘息")),
        (
            "updated_conditions",
            create_update_condition_status_intent(),
            create_update_condition_status_intent("喘息"),
        ),
        (
            "retracted_conditions",
            create_retract_condition_intent(),
            create_retract_condition_intent(reason="医師に確認した。"),
        ),
        (
            "new_concurrent_medications",
            create_concurrent_intent(),
            create_concurrent_intent("別の市販薬"),
        ),
        (
            "stopped_concurrent_medications",
            create_stop_intent(),
            create_stop_intent(ended_on=date(2026, 8, 21)),
        ),
    ),
)
def test_tc19_配列Intentは各型の個別要素だけを置換する(
    field_name: str, original: object, replacement: object
) -> None:
    record = _finalized(
        profile_updates=ProfileUpdateIntents(**cast(Any, {field_name: (original,)}))
    )
    target = _element_id(record, f"profile_updates.{field_name}", 0)

    corrected = _correct(record, target=target, value=replacement)

    assert getattr(_facts(corrected).profile_updates, field_name) == (replacement,)
    assert getattr(record.profile_updates, field_name) == (original,)
    assert _events(corrected)[0].before == original


@pytest.mark.parametrize("field_name", ("additional_notes", "billing_additions"))
def test_tc20_同名メモと加算も対象要素だけを訂正する(field_name: str) -> None:
    original = (
        _note("指導内容") if field_name == "additional_notes" else _addition("加算")
    )
    replacement = (
        _note("訂正内容") if field_name == "additional_notes" else _addition("訂正加算")
    )
    record = _finalized(**{field_name: (original, original)})
    target = _element_id(record, field_name, 0)

    replaced = _correct(record, target=target, value=replacement)
    retracted = _correct(replaced, target=target, operation="retract")
    appended = _correct(
        retracted, target=field_name, operation="append", value=replacement
    )

    assert getattr(_facts(replaced), field_name) == (replacement, original)
    assert getattr(_facts(retracted), field_name) == (original,)
    assert getattr(_facts(appended), field_name) == (original, replacement)
    assert getattr(appended, field_name) == (original, original)
    assert len({item.id for item in _elements(appended, field_name)}) == 2


def test_tc21_他薬歴の要素IDは対象にできない() -> None:
    updates = ProfileUpdateIntents(new_allergies=(create_allergy_intent(),))
    source = _finalized(profile_updates=updates)
    target_record = _finalized(profile_updates=updates)
    foreign_id = _element_id(source, "profile_updates.new_allergies", 0)

    with pytest.raises(MedicationHistoryDomainError):
        _correct(target_record, target=foreign_id, value=create_allergy_intent())

    assert _events(source) == ()
    assert _events(target_record) == ()


@pytest.mark.parametrize(
    ("target_field", "value"),
    (
        ("profile_updates.new_allergies", create_concurrent_intent()),
        ("method", (CounselingMethod.TELEPHONE,)),
    ),
)
def test_tc22_訂正先と異なる型の値を拒否する(target_field: str, value: object) -> None:
    record = _finalized(
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),))
    )
    target = (
        _element_id(record, target_field, 0)
        if target_field.startswith("profile_updates.")
        else target_field
    )

    with pytest.raises(MedicationHistoryDomainError):
        _correct(record, target=target, value=value)

    assert _events(record) == ()


@pytest.mark.parametrize("operation", ("retract", "replace"))
def test_tc23_取消済みの要素は再訂正できない(operation: str) -> None:
    record = _finalized(
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),))
    )
    target = _element_id(record, "profile_updates.new_allergies", 0)
    retracted = _correct(record, target=target, operation="retract")

    with pytest.raises(MedicationHistoryDomainError):
        _correct(
            retracted,
            target=target,
            operation=operation,
            value=create_allergy_intent() if operation == "replace" else _ABSENT,
        )

    assert len(_events(retracted)) == 1


@pytest.mark.parametrize(
    ("reason", "recorded_at"),
    (
        ("   ", _CORRECTED_AT),
        ("誤記を訂正した。", datetime(2026, 8, 25, 3)),  # noqa: DTZ001
    ),
)
def test_tc24_理由と訂正時刻は監査値として妥当でなければならない(
    reason: str, recorded_at: datetime
) -> None:
    record = _finalized()

    with pytest.raises(MedicationHistoryDomainError):
        _correct(
            record,
            target="method",
            value=CounselingMethod.TELEPHONE,
            reason=reason,
            recorded_at=recorded_at,
        )

    assert _events(record) == ()
