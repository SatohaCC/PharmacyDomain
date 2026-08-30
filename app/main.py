"""ASGIアプリケーションの起動点。"""

from fastapi import FastAPI

from app.presentational import create_app

app: FastAPI = create_app()
