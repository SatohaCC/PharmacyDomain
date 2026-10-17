"""参照用の固定値は元集約の同一性を自分の同一性にしない。"""

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.dispensing_source import RpSource
from app.domain.staff.store_source import StoreSource
from app.domain.store.identifiers import StoreId


def test_店舗参照_同じ参照先でも事実が変われば_異なる値になる() -> None:
    store_id = StoreId.generate()
    corporate_id = CorporateId.generate()

    open_store = StoreSource(
        store_id=store_id, corporate_id=corporate_id, is_closed=False
    )
    closed_store = StoreSource(
        store_id=store_id, corporate_id=corporate_id, is_closed=True
    )

    assert open_store != closed_store
    assert open_store == StoreSource(
        store_id=store_id, corporate_id=corporate_id, is_closed=False
    )


@pytest.mark.parametrize("quantity", [0, -1])
def test_調剤参照_数量が正でなければ_構築を拒否する(quantity: int) -> None:
    with pytest.raises(DomainValidationError, match="調剤数量は1以上"):
        RpSource(quantity=quantity, medicines=(), is_quantity_adjusted=False)
