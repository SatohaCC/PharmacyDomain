# 管理画面

Vite + React + TypeScript + TanStack RouterのSPA。起動・認証設定はリポジトリルートのREADME.mdを参照。

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

画面はroutes、機能はfeatures、API・認証・共通UIはsharedに置く。API型は `pnpm generate:api` で再生成し、schema.d.tsとrouteTree.gen.tsを手編集しない。
