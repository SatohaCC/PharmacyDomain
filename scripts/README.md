# 開発ツールと品質検査（ハーネス）

テスト本体とlint・型検査設定は`backend/`・`frontend/`が所有する。全エージェントが利用する共有CLIは`pnpm agent:check`で、実行計画は`scripts/checks/quality.mjs`が所有する。手動・CI・各エージェントのHook adapterはこのCLIから同じパッケージ検査を呼べる。

| 場所 | 責務 |
| --- | --- |
| `scripts/checks/` | 品質検査の実行、受入仕様（`--spec`）の評価、クリーンcheckout検証 |
| `scripts/hooks/` | Antigravity / Codexイベントの解析、編集ファイル判定、Python自動整形、検査結果の返却と重複実行・停滞防止 |

## 共通コマンド

ルートから実行する。いずれも検査対象のソースを自動修正しない。

```sh
pnpm quality                  # backend・frontend・開発ツールの全体検査
pnpm quality:backend          # backendの個別検査
pnpm quality:frontend         # frontendの個別検査
pnpm quality:scripts          # scriptsツールの個別検査
pnpm quality:changed          # HEADとの差分と未追跡ファイルから対象スコープを自動選択
pnpm quality:changed --phase quick
pnpm quality:changed --list   # 実行計画だけ表示
pnpm agent:check --phase quick # エージェント共通の変更範囲検査（受入仕様必須）
pnpm agent:check --report tmp/quality/result.json # 完了前の検査と構造化レポート
node scripts/checks/verify-clean-checkout.mjs --ref <commit> # 指定commitを隔離worktreeでクリーン再検証
```

`full`は対象側のlint・format確認・型検査・単体テストを実行する。`quick`はlint・実行入口の構文確認に加え、backendではプロジェクトのMypyを実行する。失敗・起動不能・タイムアウトは非0で終了し、他の検査も続けて結果を表示する。一時ファイルはプロジェクト内のGit管理外領域（`tmp/quality`）を使い、uv cacheは`UV_CACHE_DIR`指定時にその場所、未指定時に`.uv-cache`を使う。

結合テスト（実PostgreSQL、ブラウザE2E）は変更パスだけから自動選択しない。必要な場合は受入仕様JSONで明示選択する。

`--report <path>`は実行前に全検査を`not_run`として保存し、各検査後に状態・終了コード・所要時間・コマンドを更新する。状態は`passed`・`failed`・`start_error`・`timeout`・`incomplete`・`not_run`。

## 仕様に基づくテスト選択

作業の受入条件を[仕様JSONの例](../docs/development/quality-task.example.json)の形式でテストへ対応付ける。`version: 1`、作業を示す`task`、要件ごとの一意な`id`・`acceptance`・空でない`checks`が必須。

- `kind: python`は`backend/tests/`の既存テストを選ぶ。任意の`test`にpytestの関数・クラス・`TestClass::test_method`を指定できる。
- `kind: node`は`scripts/`の既存`.test.mjs`を選ぶ。
- `kind: vitest`は`frontend/tests/`の既存テストを選ぶ。
- `kind: suite, name: postgres`（または`integration`）は`pnpm test:integration`、`name: browser`は`pnpm test:e2e`を選ぶ。

```sh
pnpm quality:changed --spec docs/development/quality-task.example.json --list
pnpm quality:changed --spec docs/development/quality-task.example.json --phase quick
pnpm quality:changed --spec docs/development/quality-task.example.json --report tmp/quality/results.json
```

実際の作業用はGit管理外の`tmp/quality/task.json`に置くと、手動・PostToolUse・Stopが同じ仕様を読む。`pnpm agent:check`とエージェントHookはコードスコープ変更時にこの仕様を必須にする。

## 修正フィードバックと停滞検出

失敗時はテストID・型/lint診断を抽出し、`feedback`に診断、修正手順、参照ドキュメントへのリンク、対応要件IDを記録する。

同一作業（turn ID）の連続する失敗集合を診断IDで比較する。同じ診断の反復が3回なら`stagnated`、失敗試行が通算6回なら`attempt_limit`とし、Stopからの自動修正ループを停止して未解決の報告を促す。

## Antigravity hooks

[.agents/hooks.json](../.agents/hooks.json)に登録する。イベントアダプター [`backend/tools/hooks/antigravity_adapter.py`](../backend/tools/hooks/antigravity_adapter.py) 経由で呼び出す。

- `quality-gate`:
  - `PostToolUse` (`matcher: "edit_file|write_file|replace_file_content|write_to_file|multi_replace_file_content"`, timeout 600): ファイル編集後にPythonコードのRuff自動整形および編集ループ検出（同一ファイル5回編集で警告）を行う。
  - `PreInvocation` (timeout 30): 直前のPostToolUseで記録したquick検査結果・編集ループ警告を`injectSteps`の一時メッセージとしてエージェントへ渡す。
  - `Stop` (timeout 600): 差分・未追跡ファイルに対する受入・回帰検査を実行し、失敗時は `{"decision": "continue", "reason": "..."}` を返して完了を差し戻す。
- `privacy-gate`:
  - `PostToolUse` (`matcher: "edit_file|write_file|replace_file_content|write_to_file|multi_replace_file_content|run_command"`, timeout 60): 編集・コマンド実行後に個人パス・禁止語の漏洩を即座に検査する。
  - `Stop` (timeout 60): 終了直前に個人パス・禁止語の漏洩を検査し、検出時は完了を差し戻す。

## Codex hooks

[.codex/hooks.json](../.codex/hooks.json)に登録する。Codex環境でのファイル編集後（PostToolUse）および終了時（Stop）に同じ品質ゲートとプライバシーゲートを実行する。
