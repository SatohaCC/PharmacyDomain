# バックエンド

Pythonの依存管理はuvに任せ、通常操作はリポジトリルートのpnpmから実行する。

```bash
pnpm sync:backend
pnpm dev:backend
pnpm test:backend
pnpm typecheck:backend
pnpm lint:backend
pnpm format:check
pnpm imports
pnpm db:migrate
pnpm db:seed
```

本番入口はapp.main:app、開発入口はapp.dev_main:create_dev_app。既定のdev:backendとDB操作はDocker Composeを利用する。ホストのPython環境で起動する場合は `pnpm dev:backend:local` とし、ルート.envのDATABASE_URLをホスト用に設定する。backend/package.jsonがuvコマンドを定義し、pyproject.tomlとuv.lockはここに維持する。品質ゲートの正典はルートAGENTS.md。
