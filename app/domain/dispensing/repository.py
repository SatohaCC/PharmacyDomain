"""調剤セッションのリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.prescription.primitives import PrescriptionId


class DispensingProcessRepository(Protocol):
    """調剤セッション集約を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess | None:
        """指定法人の調剤セッションを取得する。

        他法人のセッションは存在を隠すため ``None`` を返す（403ではなく404相当）。
        """
        ...

    async def list_by_prescription(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> list[DispensingProcess]:
        """同一処方箋に紐付く**自局の**調剤セッションを ``iteration`` 昇順で返す。

        リフィル・分割の各回は別の保険薬局で行われうるため、他薬局で実施された
        回はここに現れない。**返る件数はその処方箋の総調剤回数と一致しない**
        （``okf/ddd/dispensing.md`` §1.2）。呼び出し側が件数から回数を導出しては
        ならない。
        """
        ...

    async def save(self, process: DispensingProcess) -> None:
        """同じ調剤回数の重複を原子的に拒否して調剤セッションを保存する。

        同一法人・同一処方箋で ``iteration`` が重複する行を、同じ集約IDを
        除外した上で拒否し、``DispensingAlreadyExistsError`` を送出する。
        同じ回の調剤が二重に登録されると、調剤基本料の算定回数と薬歴の
        記録がいずれも二重になる。

        Applicationの事前readは早期エラー用であり原子性の代替ではない。
        """
        ...
