"""運営者集約のPostgreSQL保存境界。"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.domain.identity.entities import VendorOperator
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.identity.identifiers import VendorOperatorId
from app.domain.identity.primitives import (
    CorporateUserEmail,
    ExternalSubjectKey,
    LoginId,
)
from app.domain.identity.repositories import VendorOperatorRepository
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import vendor_operators


class PostgresVendorOperatorRepository(VendorOperatorRepository):
    """運営者集約の永続化実装。"""

    def __init__(self, work: PostgresUnitOfWork) -> None:
        self._unit_of_work = work

    def _to_entity(self, row: dict[str, object]) -> VendorOperator:
        return VendorOperator(
            id=VendorOperatorId.parse(str(row["id"])),
            login_id=LoginId(str(row["login_id"])),
            email=CorporateUserEmail(str(row["email"]))
            if row["email"] is not None
            else None,
            external_subject=ExternalSubjectKey(str(row["external_subject"])),
            is_active=bool(row["is_active"]),
        )

    async def get(self, operator_id: VendorOperatorId) -> VendorOperator | None:
        result = await self._unit_of_work.session.execute(
            select(vendor_operators).where(vendor_operators.c.id == operator_id.value)
        )
        row = result.mappings().one_or_none()
        return self._to_entity(dict(row)) if row is not None else None

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> VendorOperator | None:
        result = await self._unit_of_work.session.execute(
            select(vendor_operators).where(
                vendor_operators.c.external_subject == subject.value
            )
        )
        row = result.mappings().one_or_none()
        return self._to_entity(dict(row)) if row is not None else None

    async def get_by_login_id(self, login_id: LoginId) -> VendorOperator | None:
        result = await self._unit_of_work.session.execute(
            select(vendor_operators).where(
                vendor_operators.c.login_id == login_id.value
            )
        )
        row = result.mappings().one_or_none()
        return self._to_entity(dict(row)) if row is not None else None

    async def save(self, operator: VendorOperator) -> None:
        try:
            stmt = (
                insert(vendor_operators)
                .values(
                    id=operator.id.value,
                    login_id=operator.login_id.value,
                    email=operator.email.value if operator.email else None,
                    password_hash="",  # 管理者パスワードは認証側またはプロビジョニングで更新
                    external_subject=operator.external_subject.value,
                    is_active=operator.is_active,
                )
                .on_conflict_do_update(
                    index_elements=[vendor_operators.c.id],
                    set_={
                        "login_id": operator.login_id.value,
                        "email": operator.email.value if operator.email else None,
                        "external_subject": operator.external_subject.value,
                        "is_active": operator.is_active,
                    },
                )
            )
            await self._unit_of_work.session.execute(stmt)
        except IntegrityError as error:
            message = str(error)
            if "uq_vendor_operators_login_id" in message:
                raise IdentityConflictError(
                    "このログインIDの運営者は既に登録されています。"
                ) from error
            if "uq_vendor_operators_external_subject" in message:
                raise IdentityConflictError(
                    "この外部主体の運営者は既に登録されています。"
                ) from error
            raise IdentityConflictError("運営者情報の競合が発生しました。") from error
