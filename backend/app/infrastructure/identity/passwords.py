"""パスワードをソルト付きscryptで照合する。平文は保持しない。"""

import hashlib
import hmac
import secrets

from app.domain.foundation.exceptions import DomainValidationError


def validate_password(password: str) -> None:
    """長いパスフレーズを許可し、入力サイズを制限する。"""
    if not 15 <= len(password) <= 128:
        raise DomainValidationError("パスワードは15文字以上128文字以下にしてください。")


def hash_password(password: str) -> str:
    """独立したソルトと計算量を含むハッシュを返す。"""
    validate_password(password)
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=131072,
        r=8,
        p=1,
        maxmem=268435456,
    ).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    """入力サイズを制限し、定時間でハッシュを比較する。"""
    if not 1 <= len(password) <= 128:
        return False
    _, salt, expected = encoded.split("$")
    actual = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=131072,
        r=8,
        p=1,
        maxmem=268435456,
    ).hex()
    return hmac.compare_digest(actual, expected)
