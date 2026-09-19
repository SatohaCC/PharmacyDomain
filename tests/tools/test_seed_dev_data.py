"""開発・検証用シードが、DBへ触れる前に成り立たせる約束を固定する。

シードの正しさの大半は、実DBが無くても確かめられる。固定IDであること、本人と
スタッフの参照が組として揃っていること、保存順序が外部キーの向きに従うこと、
そして出力した環境変数がそのまま開発用の起動点で使えることである。

ここが緑でも実DBの検証にはならない。逆に、ここが落ちる形のシードは実DBでも
必ず落ちるので、往復の長い確認を待たずに検出する。
"""

from __future__ import annotations

from dataclasses import fields
from datetime import timedelta

import pytest

from app.application.access_control.models import ResolvedActorContext
from app.domain.corporate.primitives import CorporateStatus
from app.domain.identity.primitives import AccountStatus
from app.domain.store.lifecycle import StoreStatus
from app.domain.store.manager_assignment import ManagerAssignmentStatus
from app.infrastructure.postgres.connection import PostgresConfigurationError
from app.presentational.dev_main import build_actor_provider
from tools.seed_dev_data import (
    SeedData,
    build_seed_data,
    environment_lines,
    load_settings,
    save_order,
)

#: 保存順序の期待値。テーブル名で書くのは、この順序が守っているのが
#: 外部キーの向きそのものだからである。
EXPECTED_SAVE_ORDER: tuple[str, ...] = (
    "account_people",
    "account_people",
    "user_accounts",
    "user_accounts",
    "corporates",
    "stores",
    "staff_members",
    "staff_person_links",
    "corporate_memberships",
    "store_manager_assignments",
)


def _environment(data: SeedData) -> dict[str, str]:
    """出力行を環境変数の辞書へ読み直す（注釈行と空行は捨てる）。"""
    values: dict[str, str] = {}
    for line in environment_lines(data):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        values[key] = value
    return values


def test_シードの組み立ては_何度呼んでも同じIDを返す() -> None:
    """TC-01: 冪等の前提。採番すると2回目の実行が別の行を作る。"""
    # Act
    first = build_seed_data()
    second = build_seed_data()

    # Assert
    for field in fields(SeedData):
        assert getattr(first, field.name).id == getattr(second, field.name).id, (
            f"{field.name} のIDが実行ごとに変わる"
        )


def test_固定IDはすべてUUIDv7である() -> None:
    """TC-02: EntityUUID は v7 を要求する。v4 を書くと構築時に落ちる。"""
    # Arrange
    data = build_seed_data()

    # Act
    versions = {
        field.name: getattr(data, field.name).id.value.version
        for field in fields(SeedData)
    }

    # Assert
    assert set(versions.values()) == {7}, f"UUIDv7 でないIDがある: {versions}"


def test_法人管理者の本人が_アカウントと対応と任命で一致する() -> None:
    """TC-03: 複合外部キー (staff_id, person_id) が通る前提。"""
    # Arrange
    data = build_seed_data()

    # Assert
    assert data.admin_account.person_id == data.admin_person.id
    assert data.staff_person_link.person_id == data.admin_person.id
    assert data.manager_assignment.person_id == data.admin_person.id


def test_スタッフIDが_対応とアクセス権と任命で一致する() -> None:
    """TC-04: アクセス権は staff_members ではなく staff_person_links を指す。"""
    # Arrange
    data = build_seed_data()

    # Assert
    assert data.staff_person_link.id == data.staff.id
    assert data.membership.staff_id == data.staff.id
    assert data.manager_assignment.staff_id == data.staff.id


def test_法人IDが_全ての従属集約で一致する() -> None:
    """TC-05: 別法人が混ざると、テナント境界の検証が最初の1件で落ちる。"""
    # Arrange
    data = build_seed_data()
    corporate_id = data.corporate.id

    # Assert
    assert data.store.corporate_id == corporate_id
    assert data.staff.corporate_id == corporate_id
    assert data.staff_person_link.corporate_id == corporate_id
    assert data.membership.corporate_id == corporate_id
    assert data.manager_assignment.corporate_id == corporate_id


def test_ベンダー管理者は_法人アクセス権を持たずに解決できる形になる() -> None:
    """TC-06: ResolveActorUseCase はベンダーに法人アクセス権を要求しない。"""
    # Arrange
    data = build_seed_data()

    # Assert
    assert data.vendor_account.is_vendor_admin is True
    assert data.vendor_account.external_subject is not None
    assert data.vendor_account.status == AccountStatus.ACTIVE
    assert data.membership.account_id != data.vendor_account.id


def test_ベンダーと法人管理者の外部主体は_重複しない() -> None:
    """TC-07: uq_user_accounts_external_subject は法人をまたいで全体一意。"""
    # Arrange
    data = build_seed_data()

    # Assert
    assert data.admin_account.external_subject is not None
    assert data.vendor_account.external_subject != data.admin_account.external_subject


def test_法人と店舗は_新規業務を受けられる状態で作られる() -> None:
    """TC-08: 休止・閉局の店舗では受付も調剤も始められない。"""
    # Arrange
    data = build_seed_data()

    # Assert
    assert data.corporate.status == CorporateStatus.ACTIVE
    assert data.store.status == StoreStatus.ACTIVE


def test_管理薬剤師に任命するスタッフは_薬剤師で当該店舗に所属する() -> None:
    """TC-09: 資格も所属も無いスタッフを任命すると、業務としては成立しない。"""
    # Arrange
    data = build_seed_data()
    starts_on = data.manager_assignment.period.starts_on

    # Assert
    assert data.staff.is_pharmacist is True
    assert data.staff.current_home_store_id(starts_on) == data.store.id


def test_管理薬剤師の任命は_無期限の在任として作られる() -> None:
    """TC-10: 期限付きにすると、その日を越えた開発環境で業務が止まる。"""
    # Arrange
    data = build_seed_data()
    assignment = data.manager_assignment
    starts_on = assignment.period.starts_on

    # Assert
    assert assignment.status == ManagerAssignmentStatus.CONFIRMED
    assert assignment.period.ends_on is None
    assert assignment.is_effective_on(starts_on) is True
    assert assignment.is_effective_on(starts_on + timedelta(days=3650)) is True


def test_出力する環境変数は_投入した集約のIDと一致する() -> None:
    """TC-11: 出力と投入がずれると、存在しない行を指したまま起動する。"""
    # Arrange
    data = build_seed_data()

    # Act
    values = _environment(data)

    # Assert
    assert values["DEV_ACTOR_PERSON_ID"] == str(data.vendor_person.id.value)
    assert values["DEV_ACTOR_ACCOUNT_ID"] == str(data.vendor_account.id.value)
    assert values["DEV_ACTOR_CORPORATE_ID"] == str(data.corporate.id.value)
    assert values["DEV_ACTOR_STORE_IDS"] == str(data.store.id.value)


async def test_シードの出力で_開発用の認証基盤が組み立つ() -> None:
    """TC-12: 出力をそのまま貼って起動できなければ、手順として成立しない。"""
    # Arrange
    data = build_seed_data()
    environment = {**_environment(data), "DEV_ACTOR_TOKEN": "seed-token"}

    # Act
    actor = await build_actor_provider(environment).authenticate("seed-token")

    # Assert
    assert isinstance(actor, ResolvedActorContext)
    assert actor.person_id == data.vendor_person.id
    assert actor.account_id == data.vendor_account.id


def test_保存順序が_外部キーの向きに従う() -> None:
    """TC-13: 参照先を後に保存すると、最初の実行が外部キー違反で落ちる。"""
    # Arrange
    data = build_seed_data()

    # Act
    labels = tuple(label for label, _ in save_order(data))

    # Assert
    assert labels == EXPECTED_SAVE_ORDER


def test_保存順序に_SeedDataの全項目が並ぶ() -> None:
    """TC-14: 項目を足して順序表へ書き忘れると、その集約だけ投入されない。"""
    # Arrange
    data = build_seed_data()

    # Act
    ordered = {aggregate for _, aggregate in save_order(data)}

    # Assert
    assert ordered == {getattr(data, field.name) for field in fields(SeedData)}


def test_接続先が未設定なら_シードは実行されない() -> None:
    """TC-15: 既定のDBへ黙って繋ぐと、意図しないDBを書き換える。"""
    # Act & Assert
    with pytest.raises(PostgresConfigurationError):
        load_settings({})
