"""ASGIアプリケーションの起動点。

ローカル認証でログインIDとパスワードを照合し、現在の本人・法人権限を解決する。
"""

from fastapi import FastAPI

from app.bootstrap import create_app

app: FastAPI = create_app(local_authentication_enabled=True)
