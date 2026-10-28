"""Applicationのstore_operationsを定義する。"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.store.identifiers import StoreId


class StoreOperation(StrEnum):
    """店舗状態に応じて判定する業務操作。"""

    RECORD_RECEPTION = "record_reception"
    REGISTER_PRESCRIPTION = "register_prescription"
    START_DISPENSING = "start_dispensing"
    RECORD_DISPENSING = "record_dispensing"
    VERIFY_DISPENSING = "verify_dispensing"
    COMPLETE_DISPENSING = "complete_dispensing"
    READ_HISTORY = "read_history"
    CREATE_EVENT = "create_event"
    START_HISTORY = "start_history"
    FINALIZE_HISTORY = "finalize_history"
    AMEND_HISTORY = "amend_history"


class StoreOperationKind(StrEnum):
    """店舗状態に対する業務の区分。"""

    NEW_WORK = "new_work"
    CONTINUING = "continuing"
    READ_ONLY = "read_only"


STORE_OPERATION_KINDS: Final[Mapping[StoreOperation, StoreOperationKind]] = {
    StoreOperation.RECORD_RECEPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.REGISTER_PRESCRIPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.START_DISPENSING: StoreOperationKind.NEW_WORK,
    StoreOperation.CREATE_EVENT: StoreOperationKind.NEW_WORK,
    StoreOperation.START_HISTORY: StoreOperationKind.NEW_WORK,
    StoreOperation.RECORD_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.VERIFY_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.COMPLETE_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.FINALIZE_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.AMEND_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.READ_HISTORY: StoreOperationKind.READ_ONLY,
}
MANAGER_REQUIRED_BY_KIND: Final[Mapping[StoreOperationKind, bool]] = {
    StoreOperationKind.NEW_WORK: True,
    StoreOperationKind.CONTINUING: False,
    StoreOperationKind.READ_ONLY: False,
}


class StoreOperationBoundary(Protocol):
    """他コンテキストは店舗集約を保持せず操作可否だけを問い合わせる。"""

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """法人・店舗・操作を検証する。他法人・未存在は404相当で隠蔽する。"""
        ...
