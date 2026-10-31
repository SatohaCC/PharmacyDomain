"""PostgreSQLへ保存するローカル資格情報と期限付きセッション。"""

import asyncio
import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.access_control.errors import TenantBoundaryNotFoundError
from app.application.common.clock import Clock
from app.application.identity.boundary_interfaces.local_authentication import (
    CredentialWriter,
    LocalAuthentication,
)
from app.application.identity.boundary_models import LoginSession, VerifiedSubject
from app.application.identity.errors import LoginFailedError, UnavailableIdentityError
from app.application.identity.queries.resolve_actor import ResolveActorUseCase
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import VendorOperatorId
from app.domain.identity.primitives import CorporateUserEmail
from app.domain.store.identifiers import StoreId
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
from app.infrastructure.identity.postgres.vendor_operator import (
    PostgresVendorOperatorRepository,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import (
    local_credentials,
    local_sessions,
    vendor_operators,
)
from app.infrastructure.readers.identity_resolve_actor import ResolveActorProjection
from app.infrastructure.staff.postgres.staff import PostgresStaffRepository
from app.infrastructure.store.postgres.store import PostgresStoreRepository
from app.infrastructure.store.postgres.store_manager_assignment import (
    PostgresStoreManagerAssignmentRepository,
)


class PostgresCredentialWriter(CredentialWriter):
    """利用者の登録と同じUoWで資格情報を作る。"""

    def __init__(self, work: PostgresUnitOfWork) -> None:
        self._work = work

    async def issue(
        self, corporate_id: CorporateId, email: str, password: str, subject: str
    ) -> None:
        """初期パスワードの再取得経路を作らず、ハッシュだけを保存する。"""
        identifier = CorporateUserEmail(email).value
        encoded = await asyncio.to_thread(hash_password, password)
        try:
            await self._work.session.execute(
                insert(local_credentials).values(
                    corporate_id=corporate_id.value,
                    email=identifier,
                    subject=subject,
                    password_hash=encoded,
                    must_change=True,
                    failed_attempts=0,
                )
            )
        except IntegrityError as error:
            raise IdentityConflictError(
                "このメールアドレスまたは認証アカウントが既に登録されています。"
            ) from error

    async def issue_vendor_operator(
        self, email: str, password: str, subject: str
    ) -> VendorOperatorId:
        """運営者の資格情報を保存する。"""
        identifier = CorporateUserEmail(email).value
        encoded = await asyncio.to_thread(hash_password, password)
        operator_id = VendorOperatorId.generate()
        try:
            await self._work.session.execute(
                insert(vendor_operators).values(
                    id=operator_id.value,
                    email=identifier,
                    password_hash=encoded,
                    external_subject=subject,
                    is_active=True,
                    failed_attempts=0,
                )
            )
        except IntegrityError as error:
            message = str(error)
            if "uq_vendor_operators_email" in message:
                raise IdentityConflictError(
                    "このメールアドレスの運営者は既に登録されています。"
                ) from error
            raise IdentityConflictError("運営者情報の競合が発生しました。") from error
        return operator_id


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
                    people=PostgresAccountPersonRepository(work),
                    accounts=PostgresUserAccountRepository(work),
                    memberships=PostgresCorporateMembershipRepository(work),
                    managers=PostgresStoreManagerAssignmentRepository(work),
                    vendor_operators=PostgresVendorOperatorRepository(work),
                    staffs=PostgresStaffRepository(work),
                    stores=PostgresStoreRepository(work),
                ),
                clock=self._clock,
            )
            try:
                await resolver.execute(VerifiedSubject(principal_id=subject))
            except UnavailableIdentityError:
                return False
            return True

    async def _selectable_store_ids(self, subject: str) -> frozenset[str]:
        """現在の選択可能店舗ID集合を取得する。"""
        async with PostgresUnitOfWork(self._sessions) as work:
            resolver = ResolveActorUseCase(
                reader=ResolveActorProjection(
                    people=PostgresAccountPersonRepository(work),
                    accounts=PostgresUserAccountRepository(work),
                    memberships=PostgresCorporateMembershipRepository(work),
                    managers=PostgresStoreManagerAssignmentRepository(work),
                    vendor_operators=PostgresVendorOperatorRepository(work),
                    staffs=PostgresStaffRepository(work),
                    stores=PostgresStoreRepository(work),
                ),
                clock=self._clock,
            )
            try:
                stores = await resolver.list_selectable_stores(
                    VerifiedSubject(principal_id=subject)
                )
            except UnavailableIdentityError:
                raise LoginFailedError() from None
            return frozenset(item.id for item in stores)

    async def login(
        self, corporate_id: str | CorporateId, email: str, password: str
    ) -> LoginSession:
        """失敗回数をDBで共有し、5回失敗したIDを15分間ロックする。"""
        try:
            cid = (
                corporate_id
                if isinstance(corporate_id, CorporateId)
                else CorporateId.parse(corporate_id)
            )
            identifier = CorporateUserEmail(email).value
        except DomainValidationError, ValueError:
            raise LoginFailedError() from None
        async with self._hash_limit, self._sessions.begin() as session:
            now = self._clock.now()
            row = (
                (
                    await session.execute(
                        select(local_credentials)
                        .where(
                            local_credentials.c.corporate_id == cid.value,
                            local_credentials.c.email == identifier,
                        )
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
                or (row["locked_until"] is not None and row["locked_until"] > now)
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
                    .where(
                        local_credentials.c.corporate_id == cid.value,
                        local_credentials.c.email == identifier,
                    )
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
                    .where(
                        local_credentials.c.corporate_id == cid.value,
                        local_credentials.c.email == identifier,
                    )
                    .values(failed_attempts=0, locked_until=None)
                )
                result = await self._issue_session(
                    session, str(row["subject"]), bool(row["must_change"])
                )
        if result is None:
            raise LoginFailedError()
        return result

    async def vendor_login(self, email: str, password: str) -> LoginSession:
        """運営者専用の認証。法人アカウントとは完全に分離して照合する。"""
        try:
            identifier = CorporateUserEmail(email).value
        except DomainValidationError:
            raise LoginFailedError() from None
        async with self._hash_limit, self._sessions.begin() as session:
            now = self._clock.now()
            row = (
                (
                    await session.execute(
                        select(vendor_operators)
                        .where(vendor_operators.c.email == identifier)
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
                or not bool(row["is_active"])
                or (row["locked_until"] is not None and row["locked_until"] > now)
            ):
                result = None
            elif not valid:
                attempts = (
                    int(row["failed_attempts"]) + 1
                    if row["locked_until"] is None
                    else 1
                )
                await session.execute(
                    update(vendor_operators)
                    .where(vendor_operators.c.email == identifier)
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
                    update(vendor_operators)
                    .where(vendor_operators.c.email == identifier)
                    .values(failed_attempts=0, locked_until=None)
                )
                result = await self._issue_session(
                    session, str(row["external_subject"]), False
                )
        if result is None:
            raise LoginFailedError()
        return result

    async def _issue_session(
        self,
        session: AsyncSession,
        subject: str,
        restricted: bool,
        *,
        selected_store_id: UUID | None = None,
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
                selected_store_id=selected_store_id,
            )
        )
        return LoginSession(
            access_token=token,
            password_change_required=restricted,
            selected_store_id=str(selected_store_id)
            if selected_store_id is not None
            else None,
        )

    async def authenticate_subject(self, credential: str | None) -> VerifiedSubject:
        """初期パスワードで作ったセッションを業務へ通さず、主体と選択店舗を返す。"""
        if not credential or len(credential) > 256:
            raise LoginFailedError()
        async with self._sessions() as session:
            sess_row = (
                await session.execute(
                    select(
                        local_sessions.c.subject,
                        local_sessions.c.restricted,
                        local_sessions.c.selected_store_id,
                    ).where(
                        local_sessions.c.digest
                        == sha256(credential.encode()).hexdigest(),
                        local_sessions.c.expires_at > self._clock.now(),
                    )
                )
            ).one_or_none()
            if sess_row is None:
                raise LoginFailedError()
            subject, restricted, selected_store_uuid = (
                str(sess_row[0]),
                bool(sess_row[1]),
                sess_row[2],
            )
            if restricted:
                raise LoginFailedError()
            if subject.startswith("vendor:"):
                # 運営者アカウントの有効性確認
                active_op = (
                    await session.execute(
                        select(vendor_operators.c.id).where(
                            vendor_operators.c.external_subject == subject,
                            vendor_operators.c.is_active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if active_op is None:
                    raise LoginFailedError()
                return VerifiedSubject(principal_id=subject)

            row = (
                await session.execute(
                    select(local_credentials.c.subject).where(
                        local_credentials.c.subject == subject,
                        local_credentials.c.must_change.is_(False),
                    )
                )
            ).one_or_none()
            if row is None or not await self._is_available(subject):
                raise LoginFailedError()
            return VerifiedSubject(
                principal_id=str(row[0]),
                selected_store_id=str(selected_store_uuid)
                if selected_store_uuid is not None
                else None,
            )

    async def authenticate(self, credential: str | None) -> str:
        """初期パスワードで作ったセッションを業務へ通さない。"""
        subject = await self.authenticate_subject(credential)
        return subject.principal_id

    async def select_store(self, token: str, store_id: str) -> LoginSession:
        """現在の有効セッションから選択可能店舗を検証し、店舗付きの別セッションを発行する。"""
        subject = await self.authenticate_subject(token)
        if subject.principal_id.startswith("vendor:"):
            raise TenantBoundaryNotFoundError()
        try:
            target_store_id = StoreId.parse(store_id)
        except DomainValidationError, ValueError:
            raise TenantBoundaryNotFoundError() from None
        selectable_ids = await self._selectable_store_ids(subject.principal_id)
        if str(target_store_id.value) not in selectable_ids:
            raise TenantBoundaryNotFoundError()
        async with self._sessions.begin() as session:
            return await self._issue_session(
                session,
                subject.principal_id,
                False,
                selected_store_id=target_store_id.value,
            )

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
