"""患者頭書きの値と改訂規則。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.exceptions import (
    PatientHeadingConflictError,
    PatientStateConflictError,
)
from app.domain.patient.heading import (
    PatientHeadingContent,
    PatientHeadingRevision,
    PatientHeadingText,
)
from app.domain.patient.lifecycle import PatientStatus
from app.domain.patient.primitives import PatientId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from tests.factories.persistence_factory import create_patient


def _content(summary: str | None, notes: str | None = None) -> PatientHeadingContent:
    """改訂の本文値を組み立てる。"""
    return PatientHeadingContent(
        summary=PatientHeadingText(summary) if summary is not None else None,
        notes=PatientHeadingText(notes) if notes is not None else None,
    )


def _revision(
    *,
    summary: str,
    recorded_at: datetime = datetime(2026, 9, 1, tzinfo=UTC),
) -> PatientHeadingRevision:
    """頭書き履歴用の改訂を組み立てる。"""
    return PatientHeadingRevision(
        content=_content(summary),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=recorded_at,
    )


def test_tc43_01_患者の初期頭書き履歴は空である() -> None:
    patient = create_patient()

    assert patient.heading_history == ()
    assert patient.profile_history == ()


def test_tc43_02_頭書きの初回記録は別の患者インスタンスに追記する() -> None:
    patient = create_patient()
    person_id = AccountPersonId.generate()
    account_id = UserAccountId.generate()
    recorded_at = datetime(2026, 9, 2, 3, tzinfo=UTC)

    updated = patient.change_heading(
        _content("大切な申し送り", "前回のトラブル経緯"),
        expected_revision=0,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert updated is not patient
    assert patient.heading_history == ()
    assert updated.heading_revision == 1
    revision = updated.heading_history[0]
    assert revision.content == _content("大切な申し送り", "前回のトラブル経緯")
    assert revision.person_id == person_id
    assert revision.account_id == account_id
    assert revision.recorded_at == recorded_at


@pytest.mark.parametrize(
    ("existing", "expected_revision", "new_summary", "new_notes"),
    [
        ((), 0, None, None),
        ((_revision(summary="概要"),), 1, "概要", None),
    ],
    ids=["未登録空", "登録済み同値"],
)
def test_tc43_04_同じ内容の更新は改訂と記録者を変えない(
    existing: tuple[PatientHeadingRevision, ...],
    expected_revision: int,
    new_summary: str | None,
    new_notes: str | None,
) -> None:
    patient = replace(create_patient(), heading_history=existing)

    updated = patient.change_heading(
        _content(new_summary, new_notes),
        expected_revision=expected_revision,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert updated is patient
    assert updated.heading_history == existing


def test_tc43_03_変更のたびに過去を保って追記する() -> None:
    first = _revision(summary="変更前")
    patient = replace(create_patient(), heading_history=(first,))

    updated = patient.change_heading(
        _content("変更後", "追加の特記事項"),
        expected_revision=1,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=datetime(2026, 9, 4, tzinfo=UTC),
    )

    assert updated.heading_history[0] == first
    assert len(updated.heading_history) == 2
    assert updated.heading_history[1].content == _content("変更後", "追加の特記事項")


def test_tc43_05_全欄を解除しても解除改訂を残す() -> None:
    first = _revision(summary="解除前", recorded_at=datetime(2026, 9, 1, tzinfo=UTC))
    patient = replace(create_patient(), heading_history=(first,))

    updated = patient.change_heading(
        _content(None),
        expected_revision=1,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert updated.heading_history[0] == first
    assert updated.heading_history[-1].content == _content(None)


@pytest.mark.parametrize("length", [1, 10_000])
def test_tc43_06_頭書きは上限までの文字数を受け入れる(length: int) -> None:
    assert len(PatientHeadingText("あ" * length).value) == length


def test_tc43_06_10_001文字の頭書きを拒否する() -> None:
    with pytest.raises(DomainValidationError):
        PatientHeadingText("あ" * 10_001)


@pytest.mark.parametrize("text", ["", " \t　"])
def test_tc43_07_空欄を本文プリミティブにできない(text: str) -> None:
    with pytest.raises(DomainValidationError):
        PatientHeadingText(text)


def test_tc43_07_本文の前後空白を除いて改行を保つ() -> None:
    assert PatientHeadingText("  一行目  \n二行目  ").value == "一行目\n二行目"


def test_tc43_08_日時を協定世界時へ正規化する() -> None:
    revision = _revision(
        summary="概要",
        recorded_at=datetime(2026, 9, 1, 9, tzinfo=timezone(timedelta(hours=9))),
    )

    assert revision.recorded_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert revision.recorded_at.tzinfo is UTC


def test_tc43_09_タイムゾーンのない日時を拒否する() -> None:
    with pytest.raises(DomainValidationError):
        _revision(summary="概要", recorded_at=datetime(2026, 9, 1))  # noqa: DTZ001


@pytest.mark.parametrize(
    "second_at",
    [datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 8, 31, tzinfo=UTC)],
    ids=["同じ時刻", "より古い時刻"],
)
def test_tc43_10_改訂履歴は日時の前後によらず追記順を保つ(
    second_at: datetime,
) -> None:
    first = _revision(summary="最初", recorded_at=datetime(2026, 9, 1, tzinfo=UTC))
    patient = replace(create_patient(), heading_history=(first,))

    updated = patient.change_heading(
        _content("次の記録"),
        expected_revision=1,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=second_at,
    )

    assert updated.heading_history[0] == first
    assert len(updated.heading_history) == 2
    assert updated.heading_history[-1].content == _content("次の記録")


@pytest.mark.parametrize("expected_revision", [0, 2])
def test_tc43_11_現在と異なる期待改訂を拒否する(
    expected_revision: int,
) -> None:
    first = _revision(summary="現在値")
    patient = replace(create_patient(), heading_history=(first,))

    with pytest.raises(PatientHeadingConflictError):
        patient.change_heading(
            _content("更新値"),
            expected_revision=expected_revision,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=datetime(2026, 9, 6, tzinfo=UTC),
        )

    assert patient.heading_history == (first,)


def test_tc43_12_統合済み患者の同値頭書き更新も拒否する() -> None:
    first = _revision(summary="元の記載")
    patient = replace(
        create_patient(),
        heading_history=(first,),
        status=PatientStatus.MERGED,
        merged_into_id=PatientId.generate(),
    )

    with pytest.raises(PatientStateConflictError):
        patient.change_heading(
            first.content,
            expected_revision=1,
            person_id=AccountPersonId.generate(),
            account_id=UserAccountId.generate(),
            recorded_at=datetime(2026, 9, 6, tzinfo=UTC),
        )

    assert patient.heading_history == (first,)
