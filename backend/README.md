# バックエンド

このディレクトリでuvコマンドを実行する。起動・DB設定・管理画面との接続手順はリポジトリルートのREADME.md、品質ゲートはAGENTS.mdを参照する。

```bash
uv sync --locked
uv run pytest -q
uv run mypy app tests tools
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
```

本番入口は `app.main:app`、固定トークンでの開発入口は `app.dev_main:create_dev_app --factory`。マイグレーションは `uv run alembic upgrade head`。DATABASE_URLは明示設定し、ルート.envは必要なシェルで明示読込する。
