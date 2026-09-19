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
    StoreOperation.READ_HISTORY: StoreOperationKind.READ_ONLY,
}

#: 区分ごとに、管理薬剤師の在任を要するか。
#:
#: 薬機法第7条は薬局ごとに管理薬剤師を置くことを義務づける。店舗が有効である
#: ことと管理薬剤師が在任することは**別の事実**なので、店舗状態の区分へ畳まず
#: 軸を分ける。
#:
#: ただし宣言は業務ごとではなく**区分ごと**に置く。業務ごとに書くと、いまは
#: 上の表と同じ値が12行並ぶだけの複製になり、片方だけ直した事故をどちらの表も
#: 検出できない。区分を増やしたときには必ず1行書かせる。
#:
#: 在任を業務の「継続」まで要求しない。不在を理由に継続まで止めると、調剤済みの
#: 記録や書きかけの薬歴が不在の期間だけ凍結し、閉局で全てを止めないのと同じ
#: 理由で害のほうが大きい。新しい業務を始めさせないことが抑止になる。
MANAGER_REQUIRED_BY_KIND: Final[Mapping[StoreOperationKind, bool]] = {
    StoreOperationKind.NEW_WORK: True,
    StoreOperationKind.CONTINUING: False,
    StoreOperationKind.READ_ONLY: False,
}

# スタッフの配属と管理薬剤師の任命は、この境界の対象に**しない**。どちらも
# 本物の集約を受け取る Domain Service（``StaffStoreAssignmentService`` と
# ``StoreManagerAssignmentService``）が閉局店舗を拒否しており、ここに同じ規則を
# 置くと判定が2箇所になる。実際、かつて列挙にだけ存在した ``assign_staff`` /
# ``assign_manager`` は ``require_allowed`` を呼ぶ経路を持たず、表の上でだけ
# 守られているように見えていた。さらに、任命を在任の要る業務として扱うと
# 最初の1人を任命できなくなる。


class StoreOperationBoundary(Protocol):
    """他コンテキストは店舗集約を保持せず操作可否だけを問い合わせる。"""

    async def require_allowed(
        self, *, corporate_id: CorporateId, store_id: StoreId, operation: StoreOperation
    ) -> None:
        """法人・店舗・操作を検証する。他法人・未存在は404相当で隠蔽する。"""
        ...
