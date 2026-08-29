"""MedicationHistory Applicationが依存する参照境界。

集約を跨ぐ検証は、本物の集約・値オブジェクトを受け取る Domain Service が担う。
それらを**運ぶ**のがこの層の Protocol であり、実装は Composition Root の
実アダプタに閉じる。
"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId


class StoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人に店舗が存在することを確認する。

        Raises:
            MedicationHistoryStoreNotFoundError: 未存在または別法人の店舗である
                場合。他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class DispensingReferenceBoundary(Protocol):
    """薬歴が紐付く調剤セッション集約を取り出す境界。

    ``DispensingProcess`` そのものを返す。法人・患者の一致は
    IDだけでは判定できず、Domain Service が本物の集約を必要とする。
    ``MedicationHistoryRecord`` 集約が調剤を保持するわけではない
    （集約モジュールからの import は ``[tool.import_rules.forbidden]`` が禁じている）。
    """

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess:
        """指定法人の調剤セッションを取得する。

        Raises:
            MedicationHistoryDispensingNotFoundError: 未存在または別法人の
                調剤セッションである場合。
        """
        ...


class StaffQualificationBoundary(Protocol):
    """Staff集約を渡さず、保有資格だけを取り出す境界。

    薬剤師かどうかの**判定そのものは行わない**。判定は
    ``CounselorQualificationService`` が担い、この境界は判定材料を運ぶ。
    """

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """指定法人に在籍するスタッフの保有資格を返す。

        Raises:
            MedicationHistoryStaffNotFoundError: 未存在または別法人のスタッフで
                ある場合。資格を持たないだけのスタッフはここでは例外にせず、
                空の ``StaffQualifications`` を返す（存在はしているため）。
        """
        ...
