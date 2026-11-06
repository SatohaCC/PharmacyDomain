---
name: application-layer
description: ユースケース、Port、入出力・認可・失敗契約の責務。
---

# Application

## 所有する契約

Applicationはユースケースの順序、必要なPort、入力/結果、アクセス認可、整合性・確定方針を所有する。業務上の状態遷移や値の計算はDomainへ委譲する。条件分岐があるというだけで業務ロジックと判定せず、その判断の意味と所有者で分ける。

厳格な既定ではDomain/標準ライブラリ/許可されたApplication契約だけを参照し、Presentation/Infrastructure/Config/Pydanticへ依存しない。設定値は必要な型付き入力として注入する。

## ユースケースの経路

1. 型付き入力と主体/スコープを受け取り、入口の認可を確認する。必要な事実をPortから取得する。
2. Domainの操作/ポリシーで業務判断する。認証済みであることは、状態や資格に関する業務ルールを代替しない。
3. 必要な保存・競合制御・確定を[UoW契約](unit-of-work.md)に従って実行する。
4. Applicationが所有する結果/失敗へ変換して返す。技術例外やDomain型を、禁止された外側の依存先へ漏らさない。

Application ServiceとUse Caseを必ず二重に用意する必要はない。既存の公開操作と必要なオーケストレーションを一箇所で所有し、Composition Rootやrouteへ業務フローを漏らさない。

## Portと読み取り

- 抽象は利用側が必要とする契約で定義する。集約のRepository抽象はDomain、Query/通知/外部サービス/UoW等のユースケースPortはApplicationが自然な所有者になる。
- 単純な一覧・検索・集計はApplicationのQuery Portが結果投影を返す形でもよい。InfrastructureはSQL/索引の具体実装を持つ。読み取りに架空のAggregateや全書込用Repositoryを強制しない。
- Queryでも、複数読込の一貫したsnapshotが必要ならその読み取り整合性を決める。「読取専用だからDB transaction不要」と断定しない。
- 同じ名前でもDomain集約、読取投影、公開DTOの契約は異なる。ORM/SDKモデルをそのまま返さず、必要な値を明示変換する。

## 公開型とエラー

PresentationからDomain importを禁止する場合、外向けApplication契約は公開Primitive値やApplication型で完結させる。内部PortがDomain型を使うことと区別する。DTO→Application入力→Domain、Domain→Application結果→DTOの変換点を明示する。

回復可能なDomain失敗は、その意味を保つApplication例外/結果へ必要な境界で変換する。契約上の区別が必要なConflict/NotFound/Validationを一律の失敗へ潰さない。既存の公開失敗契約があるならそれに合わせる。技術的な失敗を成功へ変換せず、原因は必要に応じて保持する。HTTPステータスはPresentationが決める。

汎用ValueError等への変換というコード形状だけでは、意味の欠落や公開契約違反を確定できない。何を区別する契約か、他の失敗と本当に混同されるか、呼出側の扱いを確認する。未提示なら失敗契約の確認事項として示し、専用例外型の推奨を実証済み欠陥としない。

## コンテキスト間の調整

利用側は所有元の許可された公開ID/契約を参照し、必要な事実を自分のモデルへ変換する。Domainサービスの呼出しや導出はApplication内に閉じ、配線だけのComposition Rootへ業務判断を移さない。

`workflow -> query -> catalog`、`import_workflow -> projection -> catalog`、models/contractsから具象usecaseへの逆依存禁止等は、採用しているプロジェクトの静的契約として確認する。他プロジェクトへ同名パッケージを新設する規約ではない。既存の厳格な契約をignore追加で回避しない。

## 検証

実DomainモデルとPortのFakeで、順序・失敗伝播・確定前の結果返却禁止・認可・再試行結果を観測する。競合/rollback/一意制約/外部通知は、必要な実アダプター検証を別に示す。

参考: [Cosmic Python CQRS](https://www.cosmicpython.com/book/chapter_12_cqrs)。読み書きの責務分離を判断材料とし、CQRS基盤導入を全ユースケースの前提にしない。
