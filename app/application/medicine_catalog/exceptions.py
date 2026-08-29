"""MedicineCatalogコンテキストのApplication例外。"""

from app.base.application.exceptions import ApplicationError


class MedicineCatalogApplicationError(ApplicationError):
    """医薬品マスタユースケースの基底例外。"""

    default_message = "医薬品マスタの処理中にエラーが発生しました。"
    default_code = "MEDICINE_CATALOG_APPLICATION_ERROR"


class MedicineNotFoundError(MedicineCatalogApplicationError):
    """指定日に有効なマスタ行が存在しない場合の例外。

    「マスタに無い」と「その日には有効でない（未収載・経過措置切れ）」を
    区別しない。どちらも「その日その薬品では調剤できない」であり、
    呼び出し側が「該当しない」へ倒してはならない点も同じ。
    """

    default_message = "指定日に有効な医薬品マスタの行が見つかりません。"
    default_code = "MEDICINE_CATALOG_NOT_FOUND"
