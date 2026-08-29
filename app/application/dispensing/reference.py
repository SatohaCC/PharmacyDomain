"""Dispensing Applicationが依存する参照境界。

集約を跨ぐ検証（``okf/ddd/dispensing.md`` §5 の #3 / #5 / #6 / #8 / #10 / #13）は
本物の集約・値オブジェクトを受け取る Domain Service が担う。それらを**運ぶ**のが
この層の Protocol であり、実装は Composition Root の実アダプタに閉じる。

Prescription コンテキストの Application 実装（``app.application.prescription``）は
import しない。逆向きの依存も含めて ``[tool.import_rules.forbidden]`` が検出する。
"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import PrescriptionId
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
            DispensingStoreNotFoundError: 未存在または別法人の店舗である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class PrescriptionReferenceBoundary(Protocol):
    """調剤の対象となる処方箋集約を取り出す境界。

    **ここだけは他コンテキストの集約そのものを返す。** 調剤の整合性検証
    （回数・使用期間・変更制限・剤の対応）は処方箋の中身を見ないと判定できず、
    ID や部分的なSnapshotでは足りない。AGENTS.md の「複数集約に跨る検証は
    本物の集約を受け取る Domain Service が担当する」に対応する運び役であり、
    ``DispensingProcess`` 集約が処方箋を保持するわけではない
    （集約モジュールからの import は ``[tool.import_rules.forbidden]`` が禁じている）。
    """

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription:
        """指定法人の処方箋集約を取得する。

        Raises:
            DispensingPrescriptionNotFoundError: 未存在または別法人の処方箋で
                ある場合。他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class PrescriptionCompletionBoundary(Protocol):
    """調剤の終了を処方箋側へ反映する境界。

    処方箋を調剤済へ進める契機は調剤終了区分であり（調剤編
    ``リフィル処方箋情報レコード(521)``）、その判断は調剤側にしか無い。
    **書き込みを伴う唯一の境界**である。
    """

    async def complete_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> None:
        """処方箋を調剤済へ遷移させる。

        すでに調剤済の処方箋に対しては何もしない（冪等）。同じ処方箋を
        分割調剤の各回で完了しても、2回目以降が状態遷移エラーにならないため。

        Raises:
            DispensingPrescriptionNotFoundError: 未存在または別法人の処方箋で
                ある場合。
        """
        ...


class StaffQualificationBoundary(Protocol):
    """Staff集約を渡さず、保有資格だけを取り出す境界。

    薬剤師かどうかの**判定そのものは行わない**。判定は
    ``DispensingPharmacistService`` が担い、この境界は判定材料を運ぶ。
    境界側で判定させると、同じ規則が実装ごとに分岐する。
    """

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """指定法人に在籍するスタッフの保有資格を返す。

        Raises:
            DispensingStaffNotFoundError: 未存在または別法人のスタッフである場合。
                資格を持たないだけのスタッフはここでは例外にせず、空の
                ``StaffQualifications`` を返す（存在はしているため）。
        """
        ...
