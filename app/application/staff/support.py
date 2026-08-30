"""スタッフユースケース間で共有するアプリケーション層の処理。"""

from app.application.common.input_normalization import to_optional_text
from app.application.staff.exceptions import StaffNotFoundError
from app.application.store.support import load_store_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.staff import Staff, StaffId, StaffRepository

__all__ = ["load_staff_or_raise", "load_store_or_raise", "to_optional_text"]


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
