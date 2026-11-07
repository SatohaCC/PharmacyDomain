"""薬歴記載ブロック（動的区分方式）のDomain単体テスト。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.medication_history.entities import MedicationHistoryBlock
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyFinalizedError,
)
from app.domain.medication_history.identifiers import MedicationHistoryBlockId
from app.domain.medication_history.primitives import (
    BlockSourceId,
    BlockSourceModule,
    CategoryDisplayOrder,
    CounselingNote,
    FinalizedTimestamp,
    MedicationHistoryReviewResult,
    MediumCategoryCode,
)
from app.domain.medication_history.value_objects import (
    SoapRecord,
)
from app.domain.staff.identifiers import StaffId
from tests.factories.medication_history_factory import create_record


def test_薬歴ブロック_正常な値_インスタンスが構築できる() -> None:
    # Arrange
    block_id = MedicationHistoryBlockId.generate()
    now = datetime.now(UTC)

    # Act
    block = MedicationHistoryBlock(
        id=block_id,
        category_code=MediumCategoryCode("s"),
        content=CounselingNote("頭痛の訴えあり。"),
        display_order=CategoryDisplayOrder(10),
        source_module=BlockSourceModule.SOAP,
        source_id=BlockSourceId("source-1"),
        updated_by=StaffId.generate(),
        updated_at=now,
    )

    # Assert
    assert block.id == block_id
    assert block.category_code.value == "s"
    assert block.content.value == "頭痛の訴えあり。"
    assert block.display_order.value == 10
    assert block.source_module == BlockSourceModule.SOAP
    assert block.has_content is True


def test_薬歴ブロック_空文字列_has_contentがFalse() -> None:
    # Arrange & Act
    block = MedicationHistoryBlock(
        id=MedicationHistoryBlockId.generate(),
        category_code=MediumCategoryCode("o"),
        content=CounselingNote("   "),
        display_order=CategoryDisplayOrder(20),
    )

    # Assert
    assert block.has_content is False


def test_薬歴集約_下書き状態のブロック更新_正常に更新される() -> None:
    # Arrange
    record = create_record(soap=SoapRecord())
    block1 = MedicationHistoryBlock(
        id=MedicationHistoryBlockId.generate(),
        category_code=MediumCategoryCode("s"),
        content=CounselingNote("患者訴え"),
        display_order=CategoryDisplayOrder(10),
    )
    block2 = MedicationHistoryBlock(
        id=MedicationHistoryBlockId.generate(),
        category_code=MediumCategoryCode("a"),
        content=CounselingNote("薬剤師評価"),
        display_order=CategoryDisplayOrder(20),
    )

    # Act
    updated = record.update_blocks((block1, block2))

    # Assert
    assert len(updated.blocks) == 2
    assert updated.blocks[0].content.value == "患者訴え"
    assert updated.blocks[1].content.value == "薬剤師評価"


def test_薬歴集約_確定済み状態でブロック更新_例外が発生する() -> None:
    # Arrange
    record = create_record()
    assert record.counseled_at is not None
    finalized_at = FinalizedTimestamp(record.counseled_at.value + timedelta(minutes=5))
    finalized = record.finalize(
        finalized_by=StaffId.generate(),
        finalized_at=finalized_at,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )

    block = MedicationHistoryBlock(
        id=MedicationHistoryBlockId.generate(),
        category_code=MediumCategoryCode("s"),
        content=CounselingNote("確定後の更新試行"),
        display_order=CategoryDisplayOrder(10),
    )

    # Act & Assert
    with pytest.raises(MedicationHistoryAlreadyFinalizedError):
        finalized.update_blocks((block,))


def test_薬歴集約_ブロックのみ記載された状態での確定_SOAP空でもブロックにより確定できる() -> (
    None
):
    # Arrange
    record = create_record(soap=SoapRecord())
    block_a = MedicationHistoryBlock(
        id=MedicationHistoryBlockId.generate(),
        category_code=MediumCategoryCode("a"),
        content=CounselingNote("Assessment記載あり"),
        display_order=CategoryDisplayOrder(10),
    )
    record_with_blocks = record.update_blocks((block_a,))
    assert record_with_blocks.counseled_at is not None
    finalized_at = FinalizedTimestamp(
        record_with_blocks.counseled_at.value + timedelta(minutes=5)
    )

    # Act
    finalized = record_with_blocks.finalize(
        finalized_by=StaffId.generate(),
        finalized_at=finalized_at,
        review_result=MedicationHistoryReviewResult.ASSESSMENT_AND_INSTRUCTION_RECORDED,
    )

    # Assert: validate should not raise SoapContentRequiredError
    finalized.validate()
    assert finalized.status.is_finalized is True
