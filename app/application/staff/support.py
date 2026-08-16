"""スタッフユースケース間で共有するアプリケーション層の処理。"""

from app.application.staff.exceptions import StaffNotFoundError
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import Staff, StaffId, StaffRepository

__all__ = ["load_staff_or_raise", "load_store_or_raise", "to_optional_text"]


def to_optional_text(raw: str | None) -> str | None:
    """任意入力の文字列を正規化し、未入力を ``None`` に揃える。"""
    if raw is None:
        return None
    return raw.strip() or None


async def load_staff_or_raise(
    repository: StaffRepository,
    *,
    corporate_id: CorporateId,
    staff_id: StaffId,
) -> Staff:
    """指定された法人に所属するスタッフを取得し、存在しないまたは別法人の場合は例外を送出する。"""
    staff = await repository.get(corporate_id=corporate_id, staff_id=staff_id)

    if staff is None:
        raise StaffNotFoundError(
            f"指定されたスタッフ（ID: {staff_id.value}）が見つかりません。"
        )

    return staff
