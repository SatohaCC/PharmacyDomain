---
name: unit-of-work
description: 原子性、確定、競合、冪等性、外部副作用の整合性契約。
---

# Unit of Work / consistency

## まず保証範囲を決める

UoWは**同じtransaction資源**内の変更を一単位として確定/破棄する抽象。クラスをUoW/Publisherと名付けただけで、DB・broker・ファイル・検索indexをまたぐ原子性は得られない。読み取りだけなら書込UoWを強制せず、必要なsnapshot等の読取整合性を確認する。

| 所有者 | 契約 |
|---|---|
| Application | 何を一緒に確定するか、成功の意味、競合/再試行/失敗時の方針 |
| Domain | 業務上の状態遷移と不変条件。UoW/Sessionには依存しない |
| Infrastructure | transaction開始/commit/rollback、制約・ロック等の具体実行 |
| Repository | そのスコープ内の読書き。独断でcommitしない |

既存Publisherが永続化と確定をカプセル化してよい。ApplicationのPortとして、原子性・確定点・失敗・返却値が定義されていることを確認する。技術commitの所在と方針の所有者を分け、UoWという名前へ置き換えるためだけの改修をしない。

## ローカルtransactionの契約

- 操作ごとにUoW/Sessionを作り、同じ原子性境界のRepositoryで共有する。別の並行操作へ共有しない。
- 確定前のDomain失敗、保存/constraint失敗、途中の例外では未確定変更を破棄し、資源を解放する。正常終了時の明示commit/合意した自動commitは、既存の成功契約に合わせて一箇所にする。repositoryごとのcommitを混在させない。
- 成功を返す前に必要なcommit結果を確認する。commitを返却後のcleanupへ隠さない。rollbackが既にcommitした結果や外部通知を取り消すとは扱わない。
- commit中の通信断などで結果不明なら、確定/未確定を推測しない。安定した操作キー/照会により解決できる契約を持つ。
- インメモリモデルとDB状態は別。rollback後に変更済みオブジェクトをそのまま正本として使い回さない。

## 並行更新と再実行がある場合

- 値の事前検証だけではlost update/一意性/二重実行を防げない。DB一意制約、versionを条件にした更新/CAS、ロック等から、今回の不変条件に合う確定時の保護を選ぶ。衝突は明示した結果へ変換する。
- 状態・資格・契約の事実が更新中に変わり得るなら、操作時/確定時にどのsnapshotを有効とするか決め、必要な範囲を再取得・ロック後再検証する。認証tokenの古い主張だけで現在の業務状態を保証しない。
- 同じrequest_id等で再実行する場合、キーのscope、同キー別payloadの拒否、処理中の重複、確定済み結果の再提示、保持期間を決める。プロセスメモリのsetだけで耐障害性を約束しない。
- 成功したコマンドの再送を、新しいversionによる失敗へ変えてよいか明示する。結果再提示を約束するなら、認可を再確認し、確定済み操作の識別と新規更新の検証順を設計する。

## 外部通知・複数ストアがある場合

同一DBなら、業務変更と送信義務を同じtransactionに保存するoutboxを選択肢にできる。relayが確定済み義務を配送し、consumerは重複配送に対応する。必要な保証が小さい場合まで、event sourcingや分散基盤を自動導入しない。

- commit前送信はrollback後の通知、commit後の単純送信はcrashによる未配送を起こし得る。どちらも失敗窓を検討する。
- 外部効果の完了前に「処理済み」印を独立確定すると、効果を失う恐れがある。効果とdedupの同一transaction、または冪等な外部操作/version保護等、実際の資源に合う方法を選ぶ。
- 送信後のack/記録失敗で再配送される。event ID、consumerの冪等性、順序/旧versionの扱い、再試行・失敗の可視化・復旧を決める。outboxだけでexactly-onceを保証しない。
- index更新等を非同期にするなら、検索の遅延・失敗・再構築/再実行と、APIの成功が何を意味するかを分ける。永続化の成功を「配送済み/索引反映済み」と呼ばない。

## 受入確認

今回必要な行だけを選び、前提・操作・観測結果・検証する層を具体化する。

| 場面 | 観測する契約 |
|---|---|
| 業務違反/保存失敗/commit前例外 | 変更が残らず、通知や成功結果を出さない |
| commit成功後に応答を失う | 同一操作の照会/再試行で結果を解決し、二重更新しない |
| 同versionへの並行更新 | 合意した勝者/競合結果となりlost updateを防ぐ |
| commit後のbroker障害/relay再起動 | 義務が失われず、再試行/復旧可能で状態を観測できる |
| 配送重複/順序逆転 | 二重効果や旧状態への巻き戻りを防ぐ |
| 一方のstoreだけ成功 | 局所確定を認めた復旧/補償・再実行方針を検証する |

Domain/PortのFakeは呼出し契約を検証する手段。DBのisolation/ロック/constraint、brokerやindexの耐久性・冪等性は必要な実環境で検証する。

原典: [Cosmic Python UoW](https://www.cosmicpython.com/book/chapter_06_uow)、[Richardson transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)。例の配置やフレームワークをそのまま対象へコピーせず、保証と所有権を参照する。
