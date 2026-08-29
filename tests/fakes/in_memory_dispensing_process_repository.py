"""調剤セッションRepositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.dispensing.services import DispensingIterationUniquenessService
from app.domain.prescription.primitives import PrescriptionId


class InMemoryDispensingProcessRepository(DispensingProcessRepository):
    """法人境界を適用するテスト用調剤セッションRepository。"""

    def __init__(self) -> None:
        self.items: dict[DispensingId, DispensingProcess] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess | None:
        """指定法人の調剤セッションだけを取得する。"""
        item = self.items.get(dispensing_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def list_by_prescription(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> list[DispensingProcess]:
        """指定法人・処方箋の調剤セッションを ``iteration`` 昇順で返す。"""
        matched = [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id
            and item.prescription_id == prescription_id
        ]
        return sorted(matched, key=lambda item: item.iteration.value)

    async def save(self, process: DispensingProcess) -> None:
        """同じ調剤回数の重複を原子的に拒否して調剤セッションを保存する。

        Applicationの事前readは早期エラー用であり原子性の代替ではないため、
        Repository契約として保存の直前にも同じ判定を行う。判定は
        ``DispensingIterationUniquenessService`` を呼び、規則の実装が2箇所に
        分かれないようにする。
        """
        DispensingIterationUniquenessService().ensure_no_conflict(
            process,
            [item for item in self.items.values() if item.id != process.id],
        )
        self.items[process.id] = copy.deepcopy(process)
