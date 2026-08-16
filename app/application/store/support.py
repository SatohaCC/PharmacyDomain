"""店舗ユースケース間で共有するアプリケーション層の処理。"""

from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository
from app.domain.store.store import Store


def to_optional_text(raw: str | None) -> str | None:
    """任意入力の文字列を正規化し、未入力を ``None`` に揃える。

    空文字を「未設定」と読むか「不正な値」と読むかがユースケースごとにぶれると、
    同じ画面から送られた同じ値が登録では通り変更では検証エラーになる。境界で
    1度だけ正規化し、以降は「未設定は ``None`` だけ」という前提で扱えるようにする。

    Args:
        raw: 外部から渡された任意項目の文字列（未入力は ``None`` または空文字）

    Returns:
        str | None: 前後の余白を除いた文字列。空文字・空白のみの場合は ``None``
    """
    if raw is None:
        return None
    return raw.strip() or None


async def load_store_or_raise(
    repository: StoreRepository,
    *,
    corporate_id: CorporateId,
    store_id: StoreId,
) -> Store:
    """指定された法人に所属する店舗を取得し、存在しないまたは別法人の場合は例外を送出する。

    Args:
        repository: 店舗リポジトリ
        corporate_id: 要求元の法人ID
        store_id: 取得対象の店舗ID

    Returns:
        Store: 取得された店舗集約

    Raises:
        StoreNotFoundError: 店舗が存在しない、または別法人に所属している場合
    """
    store = await repository.get(store_id)

    # 店舗が存在しない、または所属法人が一致しない場合は 404 扱いとする
    if store is None or store.corporate_id != corporate_id:
        raise StoreNotFoundError(
            f"指定された店舗（ID: {store_id.value}）が見つかりません。"
        )

    return store
