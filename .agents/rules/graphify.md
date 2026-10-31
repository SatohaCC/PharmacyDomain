---
trigger: model_decision
description: コード間の関係・呼出し経路・変更の影響範囲を調べるとき。
---

## graphify

- `graphify-out/graph.json` がある場合、コードや設計の質問では最初に `graphify query "<質問>"` を実行する。関係の追跡には `graphify path`、特定概念には `graphify explain` を使う。
- wikiがある場合は `graphify-out/wiki/index.md` を入口にする。全体把握が必要な場合だけGRAPH_REPORT.mdを読む。
- グラフが古い場合は現在のソースを確認する。コード変更後は `graphify update .` で更新する。
