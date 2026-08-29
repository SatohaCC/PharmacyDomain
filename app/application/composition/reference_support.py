"""参照Boundaryの実アダプタが共有する読み込み補助。

ここに置くのは**テナント境界の判定だけ**である。例外への写像は各コンテキストの
語彙（``XxxStoreNotFoundError``）なので、アダプタ側に残す。

``StoreRepository.get()`` は法人IDを取らない。他のRepositoryと違って
法人境界の判定が呼び出し側に残るため、4つのコンテキストのアダプタが同じ比較を
それぞれ書くことになる。1箇所でも書き漏らすと他法人の店舗が「存在する」と
判定され、テナント境界が破れる。危険な比較の方を共有し、書き漏らしようのない
形にする。
"""

from __future__ import annotations

from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository
from app.domain.store.store import Store


async def load_store_in_corporate(
    repository: StoreRepository,
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
) -> Store | None:
    """指定法人の店舗だけを返し、別法人の店舗は ``None`` へ畳む。

    「存在しない」と「別法人」を戻り値で区別しない。区別できる形にすると、
    呼び出し側が別々の例外へ分けられてしまい、他テナントの店舗IDの存在が漏れる。

    店舗の有効・無効は見ない。参照Boundaryの契約が確認するのは存在と法人境界
    だけであり、廃止済み店舗を拒否するかは各コンテキストの業務判断である
    （現時点でそれを要求する契約はない）。
    """
    store = await repository.get(store_id)
    if store is None or store.corporate_id != corporate_id:
        return None
    return store
