"""スタッフ集約の PostgreSQL Repository。

スタッフコードは無効化後も再利用させない。過去の調剤録・監査の追跡を壊さない
ためで、存在確認も一意性制約も ``is_active`` で絞らない（有効行だけを一意に
する外部患者IDとは逆向きになる）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.exceptions import StaffCodeAlreadyExistsError
from app.domain.staff.primitives import StaffCode, StaffId
from app.domain.staff.repository import StaffCatalogRepository, StaffRepository
from app.domain.staff.staff import Staff
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
    constraint_name,
)
from app.infrastructure.postgres.schema import staff_members


def _staff_columns(staff: Staff) -> dict[str, object]:
    """検索・一意性制約に使う列をスタッフから導く。"""
    return {
        "id": staff.id.value,
        "corporate_id": staff.corporate_id.value,
        "code": None if staff.code is None else staff.code.value,
        "is_active": staff.is_active,
    }


STAFF_MAPPING = AggregateMapping(
    table=staff_members,
    aggregate_type=Staff,
    label="スタッフ",
    search_columns=_staff_columns,
)


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
        return await self.find_one(
            STAFF_MAPPING,
            select(staff_members).where(
                staff_members.c.corporate_id == corporate_id.value,
                staff_members.c.id == staff_id.value,
            ),
        )

    async def save(self, staff: Staff) -> None:
        """スタッフを保存し、法人内のスタッフコード重複を拒否する。"""
        try:
            await self.save_aggregate(STAFF_MAPPING, staff)
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
        return await self.find_all(
            STAFF_MAPPING,
            select(staff_members)
            .where(staff_members.c.corporate_id == corporate_id.value)
            .order_by(staff_members.c.id),
        )

    async def list_all(self) -> list[Staff]:
        """ベンダー用に全スタッフを法人・ID順で返す。"""
        return await self.find_all(
            STAFF_MAPPING,
            select(staff_members).order_by(
                staff_members.c.corporate_id, staff_members.c.id
            ),
        )
