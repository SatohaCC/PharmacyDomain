"""スタッフの PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.exceptions import StaffCodeAlreadyExistsError
from app.domain.staff.primitives import StaffCode, StaffId
from app.domain.staff.repository import StaffCatalogRepository, StaffRepository
from app.domain.staff.staff import Staff
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import staff_members


def row_values(staff: Staff) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": staff.id.value,
        "corporate_id": staff.corporate_id.value,
        "code": None if staff.code is None else staff.code.value,
        "is_active": staff.is_active,
        "payload": encode_aggregate(staff),
    }


class PostgresStaffRepository(
    PostgresRepositoryBase, StaffRepository, StaffCatalogRepository
):
    """スタッフ集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> Staff | None:
        """法人境界を含めてIDでスタッフを検索する。"""
        result = await self.session.execute(
            select(staff_members).where(
                staff_members.c.corporate_id == corporate_id.value,
                staff_members.c.id == staff_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=staff_members.name,
            )
        )

    async def save(self, staff: Staff) -> None:
        """スタッフを保存し、法人内のスタッフコード重複を拒否する。"""
        try:
            await self.upsert(
                staff_members, aggregate_id=staff.id.value, values=row_values(staff)
            )
        except IntegrityError as error:
            if constraint_name(error) == "uq_staff_members_corporate_code":
                raise StaffCodeAlreadyExistsError(
                    f"同一法人内にスタッフコード '{staff.code}' は既に登録されています。"
                ) from error
            raise

    async def exists_by_code(
        self,
        *,
        corporate_id: CorporateId,
        code: StaffCode,
        excluding_id: StaffId | None = None,
    ) -> bool:
        """同一法人内でスタッフコードが使われているかを検索する。

        無効化済みのスタッフも対象に含める。過去の調剤録・監査の追跡を壊さない
        ため、スタッフコードは無効化後も再利用させない。
        """
        statement = select(staff_members.c.id).where(
            staff_members.c.corporate_id == corporate_id.value,
            staff_members.c.code == code.value,
        )
        if excluding_id is not None:
            statement = statement.where(staff_members.c.id != excluding_id.value)
        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_by_corporate_id(self, corporate_id: CorporateId) -> list[Staff]:
        """法人のスタッフをID順で返す。"""
        result = await self.session.execute(
            select(staff_members)
            .where(staff_members.c.corporate_id == corporate_id.value)
            .order_by(staff_members.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=staff_members.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def list_all(self) -> list[Staff]:
        """ベンダー用に全スタッフを法人・ID順で返す。"""
        result = await self.session.execute(
            select(staff_members).order_by(
                staff_members.c.corporate_id, staff_members.c.id
            )
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=staff_members.name,
                )
            )
            for row in result.mappings().all()
        ]


def _decode_row(row: Mapping[str, object]) -> Staff:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "スタッフの payload が JSON オブジェクトではありません。"
        )
    staff = decode_aggregate(payload, Staff)
    code = None if staff.code is None else staff.code.value
    if (
        staff.id.value != row.get("id")
        or staff.corporate_id.value != row.get("corporate_id")
        or code != row.get("code")
        or staff.is_active != row.get("is_active")
    ):
        raise PersistenceMappingError("スタッフの検索列と payload が一致しません。")
    return staff
