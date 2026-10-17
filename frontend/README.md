# 管理画面

Vite + React + TypeScript + TanStack RouterのSPA。依存はpnpm workspaceで管理する。インストール・開発・検証はリポジトリルートで行う。

```bash
pnpm install --frozen-lockfile
pnpm dev:frontend
pnpm typecheck:frontend
pnpm lint:frontend
pnpm test:frontend
pnpm build
pnpm test:e2e
pnpm generate:api
```

画面はroutes、機能はfeatures、共通API・認証・UIはsharedに置く。生成するschema.d.tsとrouteTree.gen.tsは手編集しない。JSのlockfileとpackageManager指定はルートだけに置く。起動・認証設定はルートREADME.mdを参照。
