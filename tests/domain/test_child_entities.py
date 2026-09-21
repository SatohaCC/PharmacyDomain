"""集約内子エンティティの同一性とライフサイクル整合性テスト。"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
from datetime import timedelta

import app.domain
from app.domain.foundation.entity import AggregateRoot, Entity
from app.domain.foundation.value_object import ValueObject
from app.domain.medication_history import (
    FollowUpId,
    MedicationHistoryRecord,
    TracingReportId,
)
from app.infrastructure.postgres.codec import decode_aggregate, encode_aggregate
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_follow_up,
    create_record,
    create_tracing_report,
    create_tracing_report_response,
)


def _iter_domain_classes() -> list[type[object]]:
    """app/domain 配下の全 dataclass を走査する。"""
    found: list[type[object]] = []
    for module_info in pkgutil.walk_packages(
        app.domain.__path__, prefix=f"{app.domain.__name__}."
    ):
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            if not isinstance(value, type):
                continue
            if value.__module__ != module_info.name:
                continue
            if dataclasses.is_dataclass(value):
                found.append(value)
    return found


def test_ライフサイクルを持つ子要素はEntityを継承する() -> None:
    """TC-01: 識別子と状態遷移/ライフサイクル変更メソッドを持つクラスは Entity を継承する。

    ValueObject は属性値による同値性を持つため、ライフサイクルによって状態が遷移する
    同一の実体を表現できない。状態遷移メソッド（record_response, resolve 等）を持つ
    ものは Entity または AggregateRoot でなければならない。
    """
    classes = _iter_domain_classes()
    violating_classes: list[str] = []

    # ライフサイクル・状態遷移を表す典型的なメソッド
    state_change_methods = {
        "record_response",
        "resolve",
        "change_status",
        "revoke_closure",
        "suspend",
        "reactivate",
        "deactivate",
        "activate",
        "accept",
        "cancel",
        "complete",
        "verify",
    }

    for cls in classes:
        field_names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        has_id = "id" in field_names
        methods = {
            name
            for name, member in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        has_lifecycle_method = bool(methods & state_change_methods)

        if has_id and has_lifecycle_method:
            is_entity = issubclass(cls, (Entity, AggregateRoot))
            is_value_object = issubclass(cls, ValueObject)
            if not is_entity or is_value_object:
                violating_classes.append(
                    f"{cls.__name__} (is_entity={is_entity}, is_value_object={is_value_object})"
                )

    assert not violating_classes, (
        "ライフサイクルを持つ以下のクラスが Entity ではなく ValueObject を継承しています:\n"
        + "\n".join(violating_classes)
    )


def test_トレーシングレポートの同一性はIDによって判定される() -> None:
    """TC-02: 同一IDを持つトレーシングレポートは、返答の前後で == が成立する。

    エンティティは状態が変化しても同一性を保持する。
    """
    report_id = TracingReportId.generate()
    report_before = create_tracing_report(
        report_id=report_id,
        provided_at=COUNSELED_AT + timedelta(days=1),
    )
    response = create_tracing_report_response(
        responded_at=COUNSELED_AT + timedelta(days=2),
    )
    report_after = report_before.record_response(response)

    # 属性は異なる（返答が追加された）
    assert report_before.response is None
    assert report_after.response is not None

    # しかし同一の TracingReportId を持つエンティティなので == である
    assert report_before == report_after


def test_異なるIDのトレーシングレポートは等しくない() -> None:
    """TC-03: 異なるIDを持つトレーシングレポートは、他の属性が同一でも != である。"""
    report1 = create_tracing_report(
        report_id=TracingReportId.generate(),
        provided_at=COUNSELED_AT + timedelta(days=1),
    )
    report2 = create_tracing_report(
        report_id=TracingReportId.generate(),
        provided_at=COUNSELED_AT + timedelta(days=1),
    )

    assert report1 != report2


def test_フォローアップ記録の同一性はIDによって判定される() -> None:
    """TC-04: フォローアップ記録は同一IDであれば等しく、異なれば等しくない。"""
    fu_id = FollowUpId.generate()
    fu1 = create_follow_up(
        follow_up_id=fu_id,
        followed_up_at=COUNSELED_AT + timedelta(days=1),
    )
    fu2 = create_follow_up(
        follow_up_id=fu_id,
        followed_up_at=COUNSELED_AT + timedelta(days=2),
    )
    fu3 = create_follow_up(
        follow_up_id=FollowUpId.generate(),
        followed_up_at=COUNSELED_AT + timedelta(days=1),
    )

    assert fu1 == fu2
    assert fu1 != fu3


def test_子エンティティのハッシュはIDに基づく() -> None:
    """TC-05: 同一IDのインスタンスはハッシュ値が等しく、setで同一視される。"""
    report_id = TracingReportId.generate()
    report1 = create_tracing_report(
        report_id=report_id,
        provided_at=COUNSELED_AT + timedelta(days=1),
    )
    response = create_tracing_report_response(
        responded_at=COUNSELED_AT + timedelta(days=2),
    )
    report2 = report1.record_response(response)

    assert hash(report1) == hash(report2)
    assert len({report1, report2}) == 1


def test_子エンティティを含む薬歴のCodec可逆性() -> None:
    """TC-07: TracingReport / FollowUpRecord を含む薬歴のエンコード・デコード可逆性。"""
    record = create_record().finalize()
    report = create_tracing_report(
        provided_at=COUNSELED_AT + timedelta(days=1),
    )
    follow_up = create_follow_up(
        followed_up_at=COUNSELED_AT + timedelta(days=1),
    )

    record = record.add_follow_up(follow_up).add_tracing_report(report)

    encoded = encode_aggregate(record)
    decoded = decode_aggregate(encoded, MedicationHistoryRecord)

    assert decoded == record
    assert len(decoded.tracing_reports) == 1
    assert decoded.tracing_reports[0] == report
    assert len(decoded.follow_ups) == 1
    assert decoded.follow_ups[0] == follow_up
