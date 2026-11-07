"""法人テストデータのコードを重複なく作る。"""

from itertools import count

from app.domain.corporate.primitives import CorporateLoginCode

_codes = count()


def create_login_code() -> CorporateLoginCode:
    """テスト用法人へ6桁コードを割り当てる。"""
    return CorporateLoginCode(f"{next(_codes):06d}")
