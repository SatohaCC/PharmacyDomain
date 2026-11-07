"""受付の今回記載欄入力値ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.common.exceptions import NotFoundError
from app.application.reception.commands.dtos.current_record_values import (
    CurrentRecordFieldValueDto,
)
from app.application.reception.commands.save_current_record_values import (
    SaveCurrentRecordValuesCommand,
    SaveCurrentRecordValuesUseCase,
)
from app.application.reception.queries.get_current_record_values import (
    GetCurrentRecordValuesQuery,
    GetCurrentRecordValuesUseCase,
)
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.identifiers import CurrentRecordFieldId
from app.domain.patient.identifiers import PatientId
from app.domain.reception.entities import Reception
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import (
    ReceptionFingerprint,
)
from app.domain.store.identifiers import StoreId
from app.infrastructure.readers.reception_get_current_record_values import (
    GetCurrentRecordValuesProjection,
)
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.fakes.in_memory_reception_repository import InMemoryReceptionRepository


@pytest.fixture
def corporate_repo() -> AutoProvisioningCorporateRepository:
    return AutoProvisioningCorporateRepository()


@pytest.fixture
def reception_repo() -> InMemoryReceptionRepository:
    return InMemoryReceptionRepository()


def make_reception(
    corporate_id: CorporateId,
    store_id: StoreId,
    reception_id: ReceptionId | None = None,
) -> Reception:
    return Reception(
        id=reception_id or ReceptionId.generate(),
        corporate_id=corporate_id,
        store_id=store_id,
        patient_id=PatientId.generate(),
        latest_fingerprint=ReceptionFingerprint("0" * 64),
        field_fingerprints=(),
    )


async def test_受付今回記載欄入力値_保存と取得_正常に保存され取得できる(
    reception_repo: InMemoryReceptionRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """受付の今回記載欄入力値の保存と取得が正しく機能すること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    corp_id = CorporateId.generate()
    store_id = StoreId.generate()
    reception = make_reception(corp_id, store_id)
    await reception_repo.save(reception)

    field_1 = CurrentRecordFieldId.generate()
    field_2 = CurrentRecordFieldId.generate()

    save_use_case = SaveCurrentRecordValuesUseCase(
        reception_repository=reception_repo,
        corporate_access=corp_access,
    )
    saved_values = await save_use_case.execute(
        SaveCurrentRecordValuesCommand(
            corporate_id=str(corp_id.value),
            store_id=str(store_id.value),
            reception_id=str(reception.id.value),
            values=(
                CurrentRecordFieldValueDto(
                    field_id=str(field_1.value),
                    value_text="残薬3日分あり。手帳に記載。",
                ),
                CurrentRecordFieldValueDto(
                    field_id=str(field_2.value),
                    value_text="体調良好、副作用なし。",
                ),
            ),
        )
    )

    assert len(saved_values) == 2
    assert saved_values[0].field_id == str(field_1.value)
    assert saved_values[0].value_text == "残薬3日分あり。手帳に記載。"

    # 取得クエリでも同一内容が取得できること
    get_use_case = GetCurrentRecordValuesUseCase(
        reader=GetCurrentRecordValuesProjection(reception_repo),
        corporate_access=corp_access,
    )
    fetched_values = await get_use_case.execute(
        GetCurrentRecordValuesQuery(
            corporate_id=str(corp_id.value),
            store_id=str(store_id.value),
            reception_id=str(reception.id.value),
        )
    )

    assert len(fetched_values) == 2
    assert fetched_values[0].field_id == str(field_1.value)
    assert fetched_values[0].value_text == "残薬3日分あり。手帳に記載。"
    assert fetched_values[1].field_id == str(field_2.value)
    assert fetched_values[1].value_text == "体調良好、副作用なし。"


async def test_受付今回記載欄入力値_存在しない受付_NotFoundErrorを送出する(
    reception_repo: InMemoryReceptionRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """存在しない受付の取得でNotFoundErrorが発生すること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    corp_id = CorporateId.generate()
    store_id = StoreId.generate()
    reception_id = ReceptionId.generate()

    get_use_case = GetCurrentRecordValuesUseCase(
        reader=GetCurrentRecordValuesProjection(reception_repo),
        corporate_access=corp_access,
    )
    with pytest.raises(NotFoundError):
        await get_use_case.execute(
            GetCurrentRecordValuesQuery(
                corporate_id=str(corp_id.value),
                store_id=str(store_id.value),
                reception_id=str(reception_id.value),
            )
        )
