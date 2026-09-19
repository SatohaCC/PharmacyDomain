"""店舗状態によって業務の開始・継続・参照を分ける境界。"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Protocol

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


class StoreOperationKind(StrEnum):
    """店舗状態に対する業務の区分。"""

    #: 休止中・閉局済みの店舗では始められない。
    NEW_WORK = "new_work"
    #: 既に始まった業務の続き。閉局済みでだけ止める。
    CONTINUING = "continuing"
    #: 過去の記録の参照。店舗状態では止めない。
    READ_ONLY = "read_only"


#: 各業務がどの区分に属するか。
#:
#: 規則の本体をここだけに置く。判定する側と検査する側が同じ集合を書き写すと、
#: 片方だけを直した事故を検出できなくなる。実際、薬歴の操作がどちらの集合にも
#: 入っていなかった時期があり、閉局店舗で新規の薬歴を作れたにもかかわらず、
#: 期待値を実装からコピーしていたテストは全て緑だった。
STORE_OPERATION_KINDS: Final[Mapping[StoreOperation, StoreOperationKind]] = {
    StoreOperation.RECORD_RECEPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.REGISTER_PRESCRIPTION: StoreOperationKind.NEW_WORK,
    StoreOperation.START_DISPENSING: StoreOperationKind.NEW_WORK,
    # 薬歴の作成は、その店舗で新しく始める業務である。調剤の記録から投影される
    # 頭書きの元になるので、閉局した店舗で増えてはいけない。
    StoreOperation.START_HISTORY: StoreOperationKind.NEW_WORK,
    StoreOperation.RECORD_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.VERIFY_DISPENSING: StoreOperationKind.CONTINUING,
    StoreOperation.COMPLETE_DISPENSING: StoreOperationKind.CONTINUING,
    # 既にある薬歴の確定・訂正は、閉局前に始まった業務の後始末として残す。
    # 閉局で書けなくなると、記載漏れのある薬歴を直せないまま凍結してしまう。
    StoreOperation.FINALIZE_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.AMEND_HISTORY: StoreOperationKind.CONTINUING,
    StoreOperation.ASSIGN_STAFF: StoreOperationKind.CONTINUING,
    StoreOperation.ASSIGN_MANAGER: StoreOperationKind.CONTINUING,
    StoreOperation.READ_HISTORY: StoreOperationKind.READ_ONLY,
}


class StoreOperationBoundary(Protocol):
    """他コンテキストは店舗集約を保持せず操作可否だけを問い合わせる。"""

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """法人・店舗・操作を検証する。他法人・未存在は404相当で隠蔽する。"""
        ...
