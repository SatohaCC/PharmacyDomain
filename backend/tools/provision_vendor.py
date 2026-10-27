"""運用者が最初のベンダーアカウントを対話入力で発行する。"""

import argparse
import asyncio
from getpass import getpass

from app.domain.identity.entities import AccountPerson, UserAccount
from app.domain.identity.primitives import ExternalSubjectKey
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.infrastructure.di.repositories import PostgresRepositorySet
from app.infrastructure.identity.postgres.local_authentication import (
    PostgresCredentialWriter,
)
from app.infrastructure.postgres.connection import (
    PostgresSettings,
    PostgresUnitOfWork,
    create_async_engine_from_settings,
    create_session_factory,
)


async def provision(login_id: str, password: str, names: PersonNames) -> None:
    """初期化権限を持つ運用者だけが起動する。HTTPからは公開しない。"""
    engine = create_async_engine_from_settings(PostgresSettings.from_environment())
    try:
        async with PostgresUnitOfWork(create_session_factory(engine)) as work:
            repositories = PostgresRepositorySet.create(work)
            person_id, account_id = AccountPersonId.generate(), UserAccountId.generate()
            subject = f"local:{account_id.value}"
            await repositories.account_person.save(
                AccountPerson(id=person_id, names=names)
            )
            await repositories.user_account.save(
                UserAccount(
                    id=account_id,
                    person_id=person_id,
                    external_subject=ExternalSubjectKey(subject),
                    is_vendor_admin=True,
                )
            )
            await PostgresCredentialWriter(work).issue(login_id, password, subject)
            await work.commit()
    finally:
        await engine.dispose()


def main() -> None:
    """秘密をコマンド引数・ログ・設定ファイルに残さず発行する。"""
    parser = argparse.ArgumentParser(
        description="ベンダーのログインアカウントを発行します。"
    )
    parser.add_argument("--login-id", required=True, help="ログインID")
    parser.add_argument("--last-name", required=True, help="姓")
    parser.add_argument("--first-name", required=True, help="名")
    parser.add_argument("--last-name-kana", required=True, help="姓カナ")
    parser.add_argument("--first-name-kana", required=True, help="名カナ")
    args = parser.parse_args()
    password = getpass("初期パスワード（15～128文字）: ")
    if password != getpass("初期パスワード（確認）: "):
        parser.error("確認用パスワードが一致しません。")
    names = PersonNames(
        kanji=PersonName(
            last_name=PersonNamePart(args.last_name),
            first_name=PersonNamePart(args.first_name),
        ),
        kana=PersonNameKana(
            last_name=PersonNameKanaPart(args.last_name_kana),
            first_name=PersonNameKanaPart(args.first_name_kana),
        ),
    )
    asyncio.run(provision(args.login_id, password, names))
    print("登録が完了しました。初回ログイン時にパスワードを変更してください。")


if __name__ == "__main__":
    main()
