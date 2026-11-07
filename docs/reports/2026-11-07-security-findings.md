# セキュリティ監査結果の統合記録

確認日: 2026-11-07

## 判定の読み方

この記録は、性質と検証段階が異なる2つの監査結果を一緒に参照できるようにしたものです。件数を合算して「24件の脆弱性」とは扱いません。

- **Codex Security: 報告対象3件** — 固定リビジョンのソースと独立レビューに基づく報告対象。重大度は中2件・低1件。アプリ、テスト、本番環境は実行しておらず、本番Ingress等の制御も未確認です。
- **security-audit Skill: 要検証候補21件** — 全件 needs_validation。監査レポート上の確認済み脆弱性は0件で、重大度も付与されていません。必要なOS隔離環境がなく、対象コード・テスト・ビルド・Hook・ブラウザー・サービスを実行せず、必須validatorも未実行のため、監査状態は incomplete です。
- 両監査は対象スナップショット、手順、検証水準が異なります。候補と報告対象に重なりが見える場合も、元の判定を保ち、同一の発見として統合しません。

## 監査の出典と範囲

### Codex Security

- Scan ID: dad5ee8b-c50b-4b95-bef2-119adb84f387
- 対象リビジョン: 8cdb3f57db5a6142d0399cac8dc0d8eac829ed94
- 対象: リポジトリ全体。1,554 tracked files をインベントリし、認証・認可、NSIPS、永続化、フロントエンド、CI等を重点確認。coverage は partial。
- 根拠資料: %USERPROFILE%\.codex\state\plugins\codex-security\scans\PharmacyDomain\8cdb3f57db5a6142d0399cac8dc0d8eac829ed94_20261106T141245Z_6ktky5je\report.md と同ディレクトリ内の findings.json、coverage.json。
- 制約: テスト・アプリ動作は実行していません。実運用のIngress、要求上限、レート・同時実行制御、TLS、DB設定、ログ保持、依存関係アドバイザリは確認対象のスナップショットから判断できません。

### .agents/skills/security-audit

- 対象参照: commit cf18e5ee3dfd242a134e42c009e8ff70870b02d8。レポートによると監査時のworktreeはdirtyで、commit後の患者一覧変更を含む作業ツリーも静的確認しています。
- 対象範囲: リポジトリ全体、standard profile。
- 結果資料: %USERPROFILE%\security-audit-skill\PharmacyDomain\run-1\REPORT.md、NEEDS-VALIDATION.md、findings.json。
- 実行状況: 21候補すべて needs_validation。必須validatorは実行されていません。OS強制隔離環境がなかったため、target codeやテスト等を実行せず、実DB/HTTP・ブラウザー・負荷検証もしていません。

## Codex Security の報告対象3件

### 1. 認証済みNSIPSリクエストが権限確認前に無制限の変換処理を行う

- 重大度: **中**。確信度: **中**。分類: CWE-400。
- Finding ID: csf_c0770a2425afad8ef3547d7e
- Fingerprint: codex-security/v1:sha256:ba918cbf917e4f549dede7d4445b746281f2bd737e8e8a362f24ebd637b84378
- 要旨: 認証済み利用者が上限のない入れ子NSIPSデータを送信でき、ルートは MANAGE_RECEPTION の確認前に全件を変換します。同権限を持つ利用者はさらにfingerprint計算、原本全体のシリアライズ、DB保存へ進めるため、処理資源を消費する可能性があります。本番の受信上限・レート制御は未確認です。
- 主な箇所: backend/app/presentational/routers/nsips.py、backend/app/application/integration/commands/ingest_nsips.py
- 推奨対応: FastAPIのモデル生成前に要求byte数を制限し、RP・薬品・加算数、文字列長、fingerprint数、保存する原本サイズも上限化する。Ingressとアプリの上限を一致させ、利用者・店舗単位のレート／同時実行制御を設ける。

### 2. 未認証ログイン要求がハッシュ処理枠を占有し、正規ログインを遅らせる

- 重大度: **中**。確信度: **高**。分類: CWE-400。
- Finding ID: csf_773144742459d29b4a5d04e1
- Fingerprint: codex-security/v1:sha256:00d29b1e3da3797c70ef32337b6318024bbf6af22b4b3f88cbcea62c7b7fdc55
- 要旨: 未認証の呼出者が存在しないアカウントIDでログイン要求を繰り返すと、ダミーscrypt検証が実行され、サービスインスタンスあたり2枠の処理枠とDB transactionを占有するため、同じインスタンスで新規ログインが遅延または拒否される可能性があります。既存セッションや他のAPIへの影響は確認されていません。
- 主な箇所: backend/app/presentational/routers/local_authentication.py、backend/app/infrastructure/identity/postgres/local_authentication.py
- 推奨対応: password hashの前に送信元・リスクに基づく制限を適用し、待ち行列を上限化する。ダミー検証を維持しつつ、scrypt中にDB transactionを保持しない構成を検討する。

### 3. 不正パスワード5回で対象アカウントの新規ログインが15分間拒否される

- 重大度: **低**。確信度: **高**。分類: CWE-645。
- Finding ID: csf_45a0fb989b6fb2bf45282abb
- Fingerprint: codex-security/v1:sha256:ecff1fedc4da3594975c5a48c9b59bc0725c44b71ca36c8161c0f054ff6b7398
- 要旨: 対象の法人ID・ログインIDを知る呼出者は、不正パスワードを5回送ることで対象アカウントの新しいローカルログインを15分間拒否させられる可能性があります。既存セッションは継続し、影響は対象アカウントの新規ログインに限定されるとの評価です。
- 主な箇所: backend/app/presentational/routers/local_authentication.py、backend/app/infrastructure/identity/postgres/local_authentication.py
- 推奨対応: アカウント単位の強制ロックだけに依存せず、送信元制限、段階的遅延またはリスク判定、利用者が安全に回復できる経路を組み合わせる。

## security-audit Skill の要検証候補21件

以下は監査レポートに記載された候補です。根拠の一部がソース上にあっても、記載した実行条件・運用設定・業務契約が確認されていないため、脆弱性として確定していません。重大度は付けません。

| # | 候補 / Fingerprint | 静的根拠と未確認点 |
|---:|---|---|
| 1 | 別法人の本人IDを使ったスタッフ紐付けが存在有無を漏らす可能性 · access-control/account-person-cross-corporate-link | 別法人に存在するperson IDと未存在IDで、例外経路からHTTP応答が異なる可能性。使い捨てDBとHTTP経路でstatus/bodyを比較していません。 |
| 2 | 法人の患者一覧を全件メモリへ展開する可能性 · api.patient-list.unbounded-corporate-materialization | 法人内患者を取得・復元後に検索する経路。実データ件数・payload分布、worker/DB資源、Ingress・レート制限とスケール時の影響は未確認です。 |
| 3 | 薬歴下書き更新APIの反復入力に個数上限がない · api.request.unbounded-collection-materialization | 追加メモ・算定加算の個数上限が見当たらず、変換・保存量が入力に応じて増える可能性。負荷実測と本番の本文・件数・レート上限は未確認です。 |
| 4 | 未認証のログイン失敗で特定アカウントが一時ロックされる可能性 · auth.local-login-target-lockout | アカウントIDを知る呼出者の失敗試行でロックされる経路。実配備のログイン到達経路、送信元／アカウント制限、回復手順は未確認です。 |
| 5 | 公開ログイン要求が他のログインを遅らせる可能性 · auth.login.public-scrypt-request-amplification | 未知IDにもダミーscryptを行い、インスタンスの2処理枠を使う経路。正規ログイン遅延の実測と本番のレート・同時接続制御は未確認です。 |
| 6 | Pull request test jobs lack an explicit duration limit · ci.pull-request-jobs-without-explicit-timeout | PR test jobsに明示的なtimeoutがない可能性。fork承認、同時実行枠、課金・利用上限などGitHub側の実効設定が不明で、共有資源への影響は未確定です。 |
| 7 | 患者更新が法人権限の変更後に保存される可能性 · clinical-store-write-guard.patient-stale-membership | 権限確認後にmembership降格が競合すると、古いActorで保存する可能性。隔離DBでの競合結果と、降格確定後の既認可要求を許容する業務契約は未確認です。 |
| 8 | 開発用Composeが公開された場合に固定トークンで管理者権限を得られる可能性 · deployment.compose.dev-static-token-exposed-via-frontend-proxy | 開発起動点に既定トークン／ロールがある一方、Composeはloopback bind。本番の起動点、外部到達経路、実効環境変数・主体設定は未確認です。 |
| 9 | Repository hooks can launch quality checks with the host process environment · devtools.repo-hook-inherits-developer-process-authority | Hookから起動する子プロセスがhost環境を継承する可能性。対応ホストでのHook自動実行・未信頼workspaceの承認動作、子プロセスの隔離は未確認です。 |
| 10 | 認証ユーザー切替後に以前のAPI応答が再利用される可能性 · frontend.api.cache.authenticated-response-reuse | 主体依存の /me 応答に明示的なno-store指定が見当たらない可能性。同一ブラウザーでの再利用、応答header、実配備proxy/CDNのcache設定は未確認です。 |
| 11 | 管理画面のフレーム埋め込み制限が確認できない · frontend.ui-redress.frame-protection-absent | 同梱Nginxにframe制限が見当たらない可能性。最終配信headerと、frame内の認証token/API操作が成立する条件はブラウザー・配備環境で未確認です。 |
| 12 | プライバシー検査フックが変更ファイル全体を読み込む · hooks.privacy-gate.unbounded-changed-file-read | Hookが変更ファイルを全量読み込む経路。hostによる未信頼Hook実行とmemory cap、隔離環境での資源影響は未確認です。 |
| 13 | 店舗の薬歴管理権限で法人共通の記載区分を変更できる可能性 · medication-history-catalog.store-role-corporate-write | 店舗向け薬歴権限で法人単位カタログを更新する経路。店舗管理者へ編集を委ねるか、法人管理者に限定するか業務契約が未確定です。 |
| 14 | 未上限のraw NSIPS入力を解析してから拒否する可能性 · nsips.raw-parser.unbounded-input-before-version-gate | raw入力を全行解析・蓄積してから未対応versionとして拒否する可能性。Ingress本文上限、レート・同時実行制御、worker資源、拒否前解析の実行確認は未確認です。 |
| 15 | NSIPS訂正のたびに受付原本の履歴が増える可能性 · nsips.reception-source-history-growth | 訂正ごとに前回原本を履歴へ追加する経路。複数訂正時のpayload増分、DB容量、頻度制御、保持方針は未確認です。 |
| 16 | NSIPS取込の権限確認前に構造化入力を変換する · nsips.structured-conversion.before-manage-reception | MANAGE_RECEPTION の確認前に構造化入力を変換する可能性。拒否前処理の実行確認と本番の本文・レート・同時実行制御は未確認です。 |
| 17 | 構造化NSIPS入力に繰り返し項目数の上限がない · nsips.structured-input.unbounded-nested-materialization | 入れ子要素数に応じて変換、fingerprint、原本JSON化、保存を行う経路。CPU・メモリ・保存量の実測と実効入力・資源上限は未確認です。 |
| 18 | CSVのエラー表示に端末制御文字が混入する可能性 · operator-cli-catalog-import:terminal-control-output | CSV由来の値が未加工で例外出力に入る可能性。制御文字を含む合成CSVの出力と対象端末での解釈は未確認です。 |
| 19 | 無効・統合済み患者IDへのEvent作成の可能性 · patient.lifecycle.inactive-event-write | 患者状態を確認せずEventを作成する経路。INACTIVE/MERGED後の遅延登録や統合元ID利用を許容するか、状態別の業務ルールが未確定です。 |
| 20 | 名寄せ後も有効な外部患者IDから受付が統合元へ紐付く可能性 · patient.merge.external-identifier-lifecycle | 統合後も外部ID対応が統合元を指す場合のNSIPS受付経路。外部IDの付替え要否と付替え前受付の期待関連先が未確定です。 |
| 21 | 並行マージで統合先が統合済み状態になる可能性 · patient.merge.target-status-race | A→T処理中にT→Uが確定すると、事前に読んだTを統合先として保存する可能性。隔離DBでの競合再現と多段redirectの契約は未確認です。 |

### 候補と報告対象の対応

- Skill候補4はCodex Security報告対象3、候補5は報告対象2とテーマが重なります。各々を独立した候補として記録し、候補側に追加の確定判定は行いません。
- Skill候補16・17はCodex Security報告対象1とNSIPS処理経路が重なります。候補16は権限確認前の変換、候補17は繰り返し項目数と後続処理に焦点があり、元の候補状態を保ちます。
- 21候補のうち上記以外にもCodexの対象範囲と近いテーマはありますが、両レポートの検証条件・対象時点が異なるため、重複排除や重大度の引継ぎはしていません。

### 候補1の後続対応メモ

「別法人の本人IDを使ったスタッフ紐付け」は、security-audit実行時点の記録では needs_validation のままです。その後、2026-11-07に承認済みFeature Pipelineで LinkStaffPersonUseCase の法人整合性対応と回帰確認を行い、DB/HTTP確認を含むPipelineがPASSとなりました。この後続対応は監査原本の判定を書き換えるものではありません。監査候補を正式に閉じる場合は、変更後リビジョンで同じ比較条件を再評価し、結果を別記録に残してください。

## チケット状況

この記録への変更指示に従い、今回の監査結果についてGitHub Issueは作成していません。
