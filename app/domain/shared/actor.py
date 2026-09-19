"""「誰が操作したか」を表す識別子（Shared Kernel）。

ここに置く理由は、この語彙を必要とするコンテキストが Identity だけではないから
である。店舗の状態変更履歴は操作者を残すし、監査も、将来の調剤録の署名も同じ
参照を要る。一方 Identity は法人アクセス権の範囲として ``StoreId`` や
``StaffId`` を持つ。両方を所有コンテキストから import すると、Store と Identity
が相互に依存し、どちらも単独では取り出せなくなる。

``MedicineName`` と同じく、この2つは「操作した人・使ったアカウント」を指す語彙
として複数コンテキストに現れる。Identity はこれらを自分の集約の同一性として
**使う**が、語彙そのものを所有しない。

このモジュールは各コンテキストへ依存せず、Domain基盤だけに依存する。
"""

from app.domain.foundation.primitives.primitives import EntityUUID


class AccountPersonId(EntityUUID):
    """操作する人の識別子。"""

    identifier_name = "本人ID"


class UserAccountId(EntityUUID):
    """個人アカウントの識別子。"""

    identifier_name = "アカウントID"


__all__ = ["AccountPersonId", "UserAccountId"]
