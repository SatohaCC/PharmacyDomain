"""調剤を完了し、必要なら処方箋を調剤済へ進めるユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common import UnitOfWork
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.application.dispensing.reference import PrescriptionCompletionBoundary
from app.application.dispensing.support import load_dispensing_or_raise, parse_enum
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensingCompletionType,
    DispensingId,
    DispensingProcessRepository,
    NextDispensingDate,
)


@dataclass(frozen=True, kw_only=True)
class CompleteDispensingCommand:
    """調剤完了の入力データ。"""

    corporate_id: str
    dispensing_id: str
    completion_type: str
    next_dispensing_date: date | None = None


class CompleteDispensingUseCase:
    """患者へ交付して調剤セッションを完了する。

    **処方箋を調剤済へ進める契機は調剤終了区分である**（調剤編
    リフィル処方箋情報レコード(521)）。「調剤回数が総使用回数に達したこと」
    ではない。規格は「達していないが次回以降の調剤が不要となった場合」も終了と
    定めるため、判断は調剤側から渡される。

    調剤セッションの保存と処方箋の状態更新は、片方だけが残ると調剤の記録と
    処方箋の状態が食い違う。**トランザクションの開始・確定を実行スコープが
    担い、ユースケースは必須の UnitOfWork で境界が開始済みであることを確認する。**
    永続化実装はトランザクションの外では読み書きできないため、境界を張り忘れた
    まま2件を書き込む経路は存在しない。
    """

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        prescription_completion: PrescriptionCompletionBoundary,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._prescription_completion = prescription_completion
        self._unit_of_work = unit_of_work

    async def execute(self, command: CompleteDispensingCommand) -> DispensingProcessDto:
        """調剤セッションを完了し、終了区分なら処方箋も調剤済にする。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_DISPENSING,
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        completion_type = parse_enum(
            DispensingCompletionType, command.completion_type, "調剤終了区分"
        )
        process = process.complete(
            completion_type=completion_type,
            next_dispensing_date=(
                NextDispensingDate(command.next_dispensing_date)
                if command.next_dispensing_date is not None
                else None
            ),
        )
        await self._repository.save(process)
        if completion_type is DispensingCompletionType.COMPLETED:
            await self._prescription_completion.complete_dispensing(
                corporate_id=corporate_id,
                prescription_id=process.prescription_id,
            )
        return DispensingProcessDto.from_entity(process)
