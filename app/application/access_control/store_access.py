"""店舗状態によって業務の開始・継続・参照を分ける境界。"""

from enum import StrEnum
from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId


class StoreOperation(StrEnum):
    """店舗状態に応じて判定する業務操作。"""

    RECORD_RECEPTION = "record_reception"
    REGISTER_PRESCRIPTION = "register_prescription"
    START_DISPENSING = "start_dispensing"
    RECORD_DISPENSING = "record_dispensing"
    VERIFY_DISPENSING = "verify_dispensing"
    COMPLETE_DISPENSING = "complete_dispensing"
    READ_HISTORY = "read_history"
    START_HISTORY = "start_history"
    FINALIZE_HISTORY = "finalize_history"
    AMEND_HISTORY = "amend_history"
    ASSIGN_STAFF = "assign_staff"
    ASSIGN_MANAGER = "assign_manager"


class StoreOperationBoundary(Protocol):
    """他コンテキストは店舗集約を保持せず操作可否だけを問い合わせる。"""

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """法人・店舗・操作を検証する。他法人・未存在は404相当で隠蔽する。"""
        ...
