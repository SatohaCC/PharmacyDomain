"""開発・検証用の初期データを投入する。

``uv run python -m tools.seed_dev_data`` で実行し、接続先は ``DATABASE_URL`` で
指定する。既定のDBへ黙って繋がないので、未設定なら何も書かずに失敗する。

**なぜ要るのか。** 更新は監査の追記を伴い、監査行は ``user_accounts`` への複合
外部キーを持つ。管理薬剤師の任命も ``staff_person_links`` を組で参照する。
つまり「実在する本人とアカウント」が先に無いと、開発用の起動点は起動できても
最初の更新で落ちる。手で揃えると、外部キーの向きを毎回思い出すことになる。

**冪等である。** IDは固定で、投入の前に必ず読む。既に在る行は**上書きしない**。
読まずに保存すると ``ON CONFLICT DO NOTHING`` が0行に当たり、
``ConcurrentModificationError`` として落ちる（``PostgresRepositoryBase._upsert``）。
上書きしないのは、手で変えた開発用データをシードが黙って戻すほうが驚きが
大きいからである。作り直したいときはテーブルを空にしてから流す。

**監査行は作らない。** シードは業務操作ではなく初期状態そのものであり、
``append_pending_audits`` はリクエスト経路の確定手続きである。ツールから呼ぶと
確定の経路が2つになる。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import (
    CorporateId,
    CorporateName,
    CorporateRepresentativeName,
)
from app.domain.identity.account_person import AccountPerson
from app.domain.identity.membership import CorporateMembership
from app.domain.identity.primitives import (
    AccountPersonId,
    CorporateMembershipId,
    ExternalSubjectKey,
    MembershipRole,
    UserAccountId,
)
from app.domain.identity.staff_person_link import StaffPersonLink
from app.domain.identity.user_account import UserAccount
from app.domain.shared.person_name import PersonNamePart, PersonNames
from app.domain.staff.primitives import (
    AffiliationPeriod,
    PharmacistLicenseNumber,
    PharmacistProfile,
    StaffCode,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.staff.staff import Staff
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.domain.store.primitives import (
    ContactInfo,
    StoreAddress,
    StoreAddressLine,
    StoreCode,
    StoreId,
    StoreName,
    StoreNameKana,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.store import Store
from app.infrastructure.postgres.connection import (
    PostgresSettings,
    PostgresUnitOfWork,
    create_async_engine_from_settings,
    create_session_factory,
)
from app.infrastructure.postgres.repositories import PostgresRepositorySet

# --------------------------------------------------------------------------
# 固定値
# --------------------------------------------------------------------------

# 固定IDは UUIDv7 の形（バージョンニブル 7・バリアント 8〜b）でなければ
# ``EntityUUID`` の構築時に落ちる。採番してしまうと2回目の実行が別の行を作り、
# 冪等でなくなる。
_VENDOR_PERSON_ID = "01930000-0000-7000-8000-000000000001"
_VENDOR_ACCOUNT_ID = "01930000-0000-7000-8000-000000000002"
_ADMIN_PERSON_ID = "01930000-0000-7000-8000-000000000003"
_ADMIN_ACCOUNT_ID = "01930000-0000-7000-8000-000000000004"
_CORPORATE_ID = "01930000-0000-7000-8000-000000000005"
_STORE_ID = "01930000-0000-7000-8000-000000000006"
# ``StaffPersonLink`` の識別子はスタッフIDそのものなので、別に採らない。
_STAFF_ID = "01930000-0000-7000-8000-000000000007"
_MEMBERSHIP_ID = "01930000-0000-7000-8000-000000000008"
_ASSIGNMENT_ID = "01930000-0000-7000-8000-000000000009"

#: 所属と任命の開始日。`date.today()` を使うと、流した日によって過去日の業務が
#: 通ったり通らなかったりする（ruff の DTZ011 も落ちる）。
SEED_START_DATE = date(2026, 1, 1)

#: 本人確認基盤が返す主体識別子に見立てた値。``ResolveActorUseCase`` は
#: ``external_subject`` が未固定のアカウントを解決しないので、必ず固定する。
_VENDOR_SUBJECT = "seed/vendor-admin"
_ADMIN_SUBJECT = "seed/corporate-admin"


@dataclass(frozen=True, slots=True)
class SeedData:
    """シードが投入する集約一式。"""

    vendor_person: AccountPerson
    vendor_account: UserAccount
    admin_person: AccountPerson
    admin_account: UserAccount
    corporate: Corporate
    store: Store
    staff: Staff
    staff_person_link: StaffPersonLink
    membership: CorporateMembership
    manager_assignment: StoreManagerAssignment


@dataclass(frozen=True, slots=True)
class SeedResult:
    """1件分の投入結果。"""

    label: str
    created: bool


# --------------------------------------------------------------------------
# 組み立て（DBに触れない）
# --------------------------------------------------------------------------


def build_seed_data() -> SeedData:
    """固定IDで投入対象の集約一式を組み立てる。

    ベンダーシステム管理者と、法人管理者を兼ねる管理薬剤師の2人を作る。
    前者は法人アクセス権を持たない（``ResolveActorUseCase`` はベンダーに
    法人アクセス権を要求しない）。後者は店舗に所属する薬剤師で、その店舗の
    管理薬剤師に任命する。任命が無いと、受付も調剤も薬歴の作成も始められない。
    """
    corporate_id = CorporateId.parse(_CORPORATE_ID)
    store_id = StoreId.parse(_STORE_ID)
    staff_id = StaffId.parse(_STAFF_ID)
    admin_person_id = AccountPersonId.parse(_ADMIN_PERSON_ID)
    vendor_person_id = AccountPersonId.parse(_VENDOR_PERSON_ID)
    admin_account_id = UserAccountId.parse(_ADMIN_ACCOUNT_ID)

    return SeedData(
        vendor_person=AccountPerson(
            id=vendor_person_id,
            names=PersonNames.create(
                last_name="開発",
                first_name="ベンダー",
                last_name_kana="カイハツ",
                first_name_kana="ベンダー",
            ),
        ),
        vendor_account=UserAccount(
            id=UserAccountId.parse(_VENDOR_ACCOUNT_ID),
            person_id=vendor_person_id,
            external_subject=ExternalSubjectKey(_VENDOR_SUBJECT),
            is_vendor_admin=True,
        ),
        admin_person=AccountPerson(
            id=admin_person_id,
            names=PersonNames.create(
                last_name="調剤",
                first_name="花子",
                last_name_kana="チョウザイ",
                first_name_kana="ハナコ",
            ),
        ),
        admin_account=UserAccount(
            id=admin_account_id,
            person_id=admin_person_id,
            external_subject=ExternalSubjectKey(_ADMIN_SUBJECT),
        ),
        corporate=Corporate(
            id=corporate_id,
            name=CorporateName("シード薬局グループ"),
            representative_name=CorporateRepresentativeName(
                last_name=PersonNamePart("調剤"),
                first_name=PersonNamePart("花子"),
            ),
        ),
        store=Store(
            id=store_id,
            corporate_id=corporate_id,
            names=StoreNames(
                name=StoreName("シード薬局 本店"),
                kana=StoreNameKana("シードヤッキョクホンテン"),
            ),
            address=StoreAddress(
                postal_code=StorePostalCode("1000001"),
                address=StoreAddressLine("東京都千代田区千代田1-1"),
            ),
            contact_info=ContactInfo.create(
                phone_number=StorePhoneNumber("0312345678")
            ),
            code=StoreCode("SEED-001"),
        ),
        staff=Staff(
            id=staff_id,
            corporate_id=corporate_id,
            names=PersonNames.create(
                last_name="調剤",
                first_name="花子",
                last_name_kana="チョウザイ",
                first_name_kana="ハナコ",
            ),
            qualifications=StaffQualifications.from_profiles(
                PharmacistProfile(license_number=PharmacistLicenseNumber("123456"))
            ),
            code=StaffCode("SEED-STAFF-001"),
            affiliations=(
                StoreAffiliation(
                    store_id=store_id,
                    period=AffiliationPeriod(start_date=SEED_START_DATE),
                    is_primary=True,
                ),
            ),
        ),
        staff_person_link=StaffPersonLink(
            id=staff_id,
            corporate_id=corporate_id,
            person_id=admin_person_id,
        ),
        membership=CorporateMembership(
            id=CorporateMembershipId.parse(_MEMBERSHIP_ID),
            account_id=admin_account_id,
            corporate_id=corporate_id,
            role=MembershipRole.CORPORATE_ADMIN,
            store_ids=frozenset({store_id}),
            staff_id=staff_id,
        ),
        manager_assignment=StoreManagerAssignment(
            id=StoreManagerAssignmentId.parse(_ASSIGNMENT_ID),
            corporate_id=corporate_id,
            store_id=store_id,
            staff_id=staff_id,
            person_id=admin_person_id,
            # 期限を付けると、その日を越えた開発環境で新規業務が黙って止まる。
            period=ManagerAssignmentPeriod(starts_on=SEED_START_DATE),
        ),
    )


def save_order(data: SeedData) -> tuple[tuple[str, object], ...]:
    """外部キーの向きに従った保存順を返す。

    参照先を後に保存すると、最初の実行が外部キー違反で落ちる。向きは
    ``account_people`` → ``user_accounts``、``staff_members`` →
    ``staff_person_links`` → ``corporate_memberships``、そして
    ``store_manager_assignments`` が ``staff_person_links`` を組で参照する。
    """
    return (
        ("account_people", data.vendor_person),
        ("account_people", data.admin_person),
        ("user_accounts", data.vendor_account),
        ("user_accounts", data.admin_account),
        ("corporates", data.corporate),
        ("stores", data.store),
        ("staff_members", data.staff),
        ("staff_person_links", data.staff_person_link),
        ("corporate_memberships", data.membership),
        ("store_manager_assignments", data.manager_assignment),
    )


def environment_lines(data: SeedData) -> list[str]:
    """``.env`` へ貼れる ``KEY=VALUE`` 行を返す。

    既定はベンダーシステム管理者にする。法人管理者で試したいときのために、
    差し替える本人とアカウントを注釈で併記する。
    """
    return [
        "# tools.seed_dev_data が投入した開発用の操作主体。",
        "DEV_ACTOR_ROLE=vendor_system_admin",
        f"DEV_ACTOR_PERSON_ID={data.vendor_person.id.value}",
        f"DEV_ACTOR_ACCOUNT_ID={data.vendor_account.id.value}",
        f"DEV_ACTOR_CORPORATE_ID={data.corporate.id.value}",
        f"DEV_ACTOR_STORE_IDS={data.store.id.value}",
        "# 法人管理者として試すときは DEV_ACTOR_ROLE=corporate_admin にして、",
        "# 本人とアカウントを次の2つへ差し替える。",
        f"# DEV_ACTOR_PERSON_ID={data.admin_person.id.value}",
        f"# DEV_ACTOR_ACCOUNT_ID={data.admin_account.id.value}",
    ]


def load_settings(environment: Mapping[str, str] | None = None) -> PostgresSettings:
    """投入先の接続設定を読み込む。

    Raises:
        PostgresConfigurationError: ``DATABASE_URL`` が無い、または読めない場合。
            既定のDBへ黙って繋ぐと、意図しないDBを書き換える。
    """
    return PostgresSettings.from_environment(environment)


# --------------------------------------------------------------------------
# 投入
# --------------------------------------------------------------------------


async def apply_seed(work: PostgresUnitOfWork, data: SeedData) -> list[SeedResult]:
    """読んでから、無ければ保存する。確定は呼び出し側が行う。"""
    repositories = PostgresRepositorySet.create(work)
    return [
        await _save_if_absent(repositories, label, aggregate)
        for label, aggregate in save_order(data)
    ]


async def _save_if_absent(
    repositories: PostgresRepositorySet, label: str, aggregate: object
) -> SeedResult:
    """既存行があれば読むだけで済ませ、無いときだけ保存する。"""
    match aggregate:
        case AccountPerson():
            created = await repositories.account_person.get(aggregate.id) is None
            if created:
                await repositories.account_person.save(aggregate)
        case UserAccount():
            created = await repositories.user_account.get(aggregate.id) is None
            if created:
                await repositories.user_account.save(aggregate)
        case Corporate():
            created = await repositories.corporate.get(aggregate.id) is None
            if created:
                await repositories.corporate.save(aggregate)
        case Store():
            created = await repositories.store.get(aggregate.id) is None
            if created:
                await repositories.store.save(aggregate)
        case Staff():
            created = (
                await repositories.staff.get(
                    corporate_id=aggregate.corporate_id, staff_id=aggregate.id
                )
                is None
            )
            if created:
                await repositories.staff.save(aggregate)
        case StaffPersonLink():
            created = await repositories.staff_person_link.get(aggregate.id) is None
            if created:
                await repositories.staff_person_link.save(aggregate)
        case CorporateMembership():
            created = await repositories.membership.get(aggregate.id) is None
            if created:
                await repositories.membership.save(aggregate)
        case StoreManagerAssignment():
            created = await repositories.manager_assignment.get(aggregate.id) is None
            if created:
                await repositories.manager_assignment.save(aggregate)
        case _:
            raise TypeError(f"投入方法の分からない集約です: {type(aggregate).__name__}")
    return SeedResult(label=label, created=created)


async def main() -> None:
    """接続設定を読み、シードを適用して環境変数を出力する。"""
    settings = load_settings()
    engine = create_async_engine_from_settings(settings)
    try:
        data = build_seed_data()
        async with PostgresUnitOfWork(create_session_factory(engine)) as work:
            results = await apply_seed(work, data)
            await work.commit()
    finally:
        await engine.dispose()

    for result in results:
        print(f"{'作成' if result.created else '既存'}: {result.label}")
    print("")
    print("\n".join(environment_lines(data)))


if __name__ == "__main__":
    asyncio.run(main())


__all__ = [
    "SEED_START_DATE",
    "SeedData",
    "SeedResult",
    "apply_seed",
    "build_seed_data",
    "environment_lines",
    "load_settings",
    "main",
    "save_order",
]
