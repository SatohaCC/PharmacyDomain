"""法人検索のページ境界と操作権限。"""

import pytest

from app.application.access_control.models import ActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.list_corporates import (
    ListCorporatesQuery,
    ListCorporatesUseCase,
)
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import (
    CorporateId,
    CorporateName,
    CorporateRepresentativeName,
)
from app.domain.foundation.exceptions import DomainValidationError
from tests.fakes.in_memory_corporate_search_repository import (
    InMemoryCorporateSearchRepository,
)


def _corporate(index: int) -> Corporate:
    return Corporate.create(
        name=CorporateName(f"法人{index:03d}"),
        representative_name=CorporateRepresentativeName.create(
            last_name="山田", first_name="太郎"
        ),
    )


def _use_case(repository: InMemoryCorporateSearchRepository) -> ListCorporatesUseCase:
    return ListCorporatesUseCase(
        repository,
        AuthorizationService(ActorContext.vendor_system_admin(principal_id="担当者")),
    )


@pytest.mark.asyncio
async def test_法人一覧は_ID昇順で既定の五十件を返す() -> None:
    items = [_corporate(index) for index in range(51)]
    repository = InMemoryCorporateSearchRepository(list(reversed(items)))

    result = await _use_case(repository).execute(ListCorporatesQuery())

    assert [item.id for item in result.items] == [
        str(item.id.value) for item in items[:50]
    ]
    assert result.next_cursor is not None
    assert repository.queries[0].limit <= 51


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["active", "inactive"])
async def test_指定した状態の法人だけが返る(status: str) -> None:
    active, inactive = _corporate(1), _corporate(2).deactivate()
    repository = InMemoryCorporateSearchRepository([active, inactive])

    result = await _use_case(repository).execute(ListCorporatesQuery(status=status))

    expected = active if status == "active" else inactive
    assert [item.id for item in result.items] == [str(expected.id.value)]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 100])
async def test_次ページをたどると_欠落や重複なく全件を取得できる(limit: int) -> None:
    items = [_corporate(index) for index in range(101)]
    use_case = _use_case(InMemoryCorporateSearchRepository(items))
    cursor = None
    collected: list[str] = []

    for _ in range(102):
        result = await use_case.execute(ListCorporatesQuery(limit=limit, cursor=cursor))
        collected.extend(item.id for item in result.items)
        cursor = result.next_cursor
        if cursor is None:
            break

    assert cursor is None
    assert collected == [str(item.id.value) for item in items]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 101])
async def test_範囲外の取得件数を拒否する(limit: int) -> None:
    with pytest.raises(DomainValidationError):
        await _use_case(InMemoryCorporateSearchRepository([])).execute(
            ListCorporatesQuery(limit=limit)
        )


@pytest.mark.asyncio
async def test_壊れたカーソルを拒否する() -> None:
    with pytest.raises(DomainValidationError):
        await _use_case(InMemoryCorporateSearchRepository([])).execute(
            ListCorporatesQuery(cursor="不正なカーソル")
        )


@pytest.mark.asyncio
async def test_別の検索条件のカーソルを拒否する() -> None:
    use_case = _use_case(
        InMemoryCorporateSearchRepository([_corporate(1), _corporate(2)])
    )
    first = await use_case.execute(ListCorporatesQuery(name="法人", limit=1))
    assert first.next_cursor is not None

    with pytest.raises(DomainValidationError):
        await use_case.execute(
            ListCorporatesQuery(name="別法人", cursor=first.next_cursor)
        )


@pytest.mark.asyncio
async def test_一致する法人がなければ_空ページを返す() -> None:
    result = await _use_case(
        InMemoryCorporateSearchRepository([_corporate(1)])
    ).execute(ListCorporatesQuery(name="見つからない"))
    assert result.items == ()
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_法人管理者は_全法人の一覧を取得できない() -> None:
    repository = InMemoryCorporateSearchRepository([_corporate(1)])
    use_case = ListCorporatesUseCase(
        repository,
        AuthorizationService(
            ActorContext.corporate_admin(
                principal_id="管理者", corporate_id=CorporateId.generate()
            )
        ),
    )

    with pytest.raises(AuthorizationError):
        await use_case.execute(ListCorporatesQuery())
    assert repository.queries == []
