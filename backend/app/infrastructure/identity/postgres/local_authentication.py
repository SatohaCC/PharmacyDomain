"""PostgreSQLへ保存するローカル資格情報と期限付きセッション。"""

import asyncio
import re
import secrets
from datetime import timedelta
from hashlib import sha256

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.common.clock import Clock
from app.application.identity.boundary_interfaces.local_authentication import (
    CredentialWriter,
    LocalAuthentication,
)
from app.application.identity.boundary_models import LoginSession, VerifiedSubject
from app.application.identity.errors import LoginFailedError, UnavailableIdentityError
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.exceptions import IdentityConflictError
from app.infrastructure.identity.passwords import (
    hash_password,
    validate_password,
    verify_password,
)
from app.infrastructure.identity.postgres.account_person import (
    PostgresAccountPersonRepository,
)
from app.infrastructure.identity.postgres.corporate_membership import (
    PostgresCorporateMembershipRepository,
)
from app.infrastructure.identity.postgres.user_account import (
    PostgresUserAccountRepository,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import local_credentials, local_sessions
from app.infrastructure.readers.identity_resolve_actor import ResolveActorProjection


def normalize_login_id(login_id: str) -> str:
    """大文字小文字を区別しないASCIIのログインIDに統一する。"""
    normalized = login_id.strip().lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", normalized) is None:
        raise DomainValidationError(
            "ログインIDは3～64文字の半角英数字・ピリオド・ハイフン・下線で指定してください。"
        )
    return normalized


class PostgresCredentialWriter(CredentialWriter):
    """利用者の登録と同じUoWで資格情報を作る。"""

    def __init__(self, work: PostgresUnitOfWork) -> None:
        self._work = work

    async def issue(self, login_id: str, password: str, subject: str) -> None:
        """初期パスワードの再取得経路を作らず、ハッシュだけを保存する。"""
        identifier = normalize_login_id(login_id)
        encoded = await asyncio.to_thread(hash_password, password)
        try:
            await self._work.session.execute(
                insert(local_credentials).values(
                    login_id=identifier,
                    subject=subject,
                    password_hash=encoded,
                    must_change=True,
                    failed_attempts=0,
                )
            )
        except IntegrityError as error:
            raise IdentityConflictError(
                "ログインIDまたは認証アカウントが既に登録されています。"
            ) from error


class PostgresLocalAuthentication(LocalAuthentication):
    """認証用の短いトランザクションを開き、業務権限は別の境界で解決する。"""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], clock: Clock
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._dummy_hash: str | None = None
        self._hash_limit = asyncio.Semaphore(2)

    async def _is_available(self, subject: str) -> bool:
        """業務要求と同じ本人解決で、現在のアカウントと法人権限を確認する。"""
        async with PostgresUnitOfWork(self._sessions) as work:
            resolver = ResolveActorUseCase(
                reader=ResolveActorProjection(
                    PostgresAccountPersonRepository(work),
                    PostgresUserAccountRepository(work),
                    PostgresCorporateMembershipRepository(work),
                )
            )
            try:
                await resolver.execute(VerifiedSubject(principal_id=subject))
            except UnavailableIdentityError:
                return False
            return True

    async def login(self, login_id: str, password: str) -> LoginSession:
        """失敗回数をDBで共有し、5回失敗したIDを15分間ロックする。"""
        try:
            identifier = normalize_login_id(login_id)
        except DomainValidationError:
            raise LoginFailedError() from None
        async with self._hash_limit, self._sessions.begin() as session:
            now = self._clock.now()
            row = (
                (
                    await session.execute(
                        select(local_credentials)
                        .where(local_credentials.c.login_id == identifier)
                        .with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if self._dummy_hash is None:
                self._dummy_hash = await asyncio.to_thread(
                    hash_password, secrets.token_urlsafe(32)
                )
            encoded = str(row["password_hash"]) if row else self._dummy_hash
            valid = await asyncio.to_thread(verify_password, password, encoded)
            if (
                row is None
                or not await self._is_available(str(row["subject"]))
                or row["locked_until"] is not None
                and row["locked_until"] > now
            ):
                result = None
            elif not valid:
                attempts = (
                    int(row["failed_attempts"]) + 1
                    if row["locked_until"] is None
                    else 1
                )
                await session.execute(
                    update(local_credentials)
                    .where(local_credentials.c.login_id == identifier)
                    .values(
                        failed_attempts=attempts,
                        locked_until=now + timedelta(minutes=15)
                        if attempts >= 5
                        else None,
                    )
                )
                result = None
            else:
                await session.execute(
                    update(local_credentials)
                    .where(local_credentials.c.login_id == identifier)
                    .values(failed_attempts=0, locked_until=None)
                )
                result = await self._issue_session(
                    session, str(row["subject"]), bool(row["must_change"])
                )
        if result is None:
            raise LoginFailedError()
        return result

    async def _issue_session(
        self, session: AsyncSession, subject: str, restricted: bool
    ) -> LoginSession:
        """秘密そのものではなくダイジェストと有効期限だけを保存する。"""
        token = secrets.token_urlsafe(32)
        await session.execute(
            delete(local_sessions).where(
                local_sessions.c.expires_at <= self._clock.now()
            )
        )
        await session.execute(
            insert(local_sessions).values(
                digest=sha256(token.encode()).hexdigest(),
                subject=subject,
                restricted=restricted,
                expires_at=self._clock.now()
                + (timedelta(minutes=10) if restricted else timedelta(hours=8)),
            )
        )
        return LoginSession(access_token=token, password_change_required=restricted)

    async def authenticate(self, credential: str | None) -> str:
        """初期パスワードで作ったセッションを業務へ通さない。"""
        if not credential or len(credential) > 256:
            raise LoginFailedError()
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(local_sessions.c.subject)
                    .join(
                        local_credentials,
                        local_credentials.c.subject == local_sessions.c.subject,
                    )
                    .where(
                        local_sessions.c.digest
                        == sha256(credential.encode()).hexdigest(),
                        local_sessions.c.expires_at > self._clock.now(),
                        local_sessions.c.restricted.is_(False),
                        local_credentials.c.must_change.is_(False),
                    )
                )
            ).one_or_none()
            if row is None:
                raise LoginFailedError()
            return str(row[0])

    async def change_password(self, token: str, password: str) -> LoginSession:
        """初回変更専用の資格情報だけで変更し、以前の全セッションを失効する。"""
        validate_password(password)
        if not token or len(token) > 256:
            raise LoginFailedError()
        async with self._hash_limit, self._sessions.begin() as session:
            row = (
                (
                    await session.execute(
                        select(local_credentials)
                        .join(
                            local_sessions,
                            local_credentials.c.subject == local_sessions.c.subject,
                        )
                        .where(
                            local_sessions.c.digest
                            == sha256(token.encode()).hexdigest(),
                            local_sessions.c.expires_at > self._clock.now(),
                            local_sessions.c.restricted.is_(True),
                            local_credentials.c.must_change.is_(True),
                        )
                        .with_for_update(of=local_credentials)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None or not await self._is_available(str(row["subject"])):
                raise LoginFailedError()
            # ロック待機中に別の変更で失効したセッションを再利用させない。
            active_session = await session.scalar(
                select(local_sessions.c.digest).where(
                    local_sessions.c.digest == sha256(token.encode()).hexdigest(),
                    local_sessions.c.expires_at > self._clock.now(),
                    local_sessions.c.restricted.is_(True),
                )
            )
            if active_session is None:
                raise LoginFailedError()
            if await asyncio.to_thread(
                verify_password, password, str(row["password_hash"])
            ):
                raise DomainValidationError(
                    "現在と異なるパスワードを指定してください。"
                )
            encoded = await asyncio.to_thread(hash_password, password)
            subject = str(row["subject"])
            await session.execute(
                update(local_credentials)
                .where(local_credentials.c.subject == subject)
                .values(
                    password_hash=encoded,
                    must_change=False,
                    failed_attempts=0,
                    locked_until=None,
                )
            )
            await session.execute(
                delete(local_sessions).where(local_sessions.c.subject == subject)
            )
            return await self._issue_session(session, subject, False)

    async def logout(self, token: str) -> None:
        """ログアウトしたセッションをサーバー側でも削除する。"""
        async with self._sessions.begin() as session:
            await session.execute(
                delete(local_sessions).where(
                    local_sessions.c.digest == sha256(token.encode()).hexdigest()
                )
            )
