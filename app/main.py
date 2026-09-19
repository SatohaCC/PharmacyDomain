"""ASGIアプリケーションの起動点。

``OIDC_*`` が設定されていれば外部IdPを接続し、未設定なら業務操作をすべて401で
拒否する既定のまま起動する。設定が中途半端な場合はここで落とす。
"""

from fastapi import FastAPI

from app.presentational import create_app
from app.presentational.oidc import build_verified_subject_provider

app: FastAPI = create_app(identity_provider=build_verified_subject_provider())
