"""MedicineCatalogドメインの業務例外。"""

from __future__ import annotations

from app.base.domain.exceptions import DomainError


class MedicineCatalogDomainError(DomainError):
    """MedicineCatalogドメインの基底例外。"""

    default_message = "医薬品マスタでエラーが発生しました。"
    default_code = "MEDICINE_CATALOG_DOMAIN_ERROR"


class MedicineEffectivePeriodInvertedError(MedicineCatalogDomainError):
    """経過措置期限が収載日より前になっている場合の例外。"""

    default_message = "経過措置期限は収載日以降の日付で指定してください。"
    default_code = "MEDICINE_CATALOG_PERIOD_INVERTED"


class MedicineEffectivePeriodConflictError(MedicineCatalogDomainError):
    """同一薬品コードの収載期間が重複している場合の例外。

    期間が重なると、ある日付で引いたときに2行が返り「その日のマスタ」が
    一意に定まらなくなる。麻薬区分が行ごとに違えば、判定結果が並び順で変わる。
    """

    default_message = "同じ薬品コードで収載期間が重複しています。"
    default_code = "MEDICINE_CATALOG_PERIOD_CONFLICT"

    def __init__(self, *, medicine_code: str | None = None) -> None:
        """対象の薬品コードを添えて例外を生成する。"""
        message = self.default_message
        if medicine_code is not None:
            message = f"{message}薬品コード: {medicine_code}。"
        super().__init__(message)


class MedicineCodeRequiredError(MedicineCatalogDomainError):
    """薬品コードを持たない行をマスタへ登録しようとした場合の例外。

    マスタは薬品コードで引くためにある。``MedicineCodeType.NONE``（コードなし）の
    行を登録すると、二度と引けない行が積み上がる。紙処方箋の「コードなし」は
    処方箋側の表現であって、マスタの行にはなりえない。
    """

    default_message = "医薬品マスタには薬品コードが必要です。"
    default_code = "MEDICINE_CATALOG_CODE_REQUIRED"
