STATUS: NEEDS_REVISION

# NSIPS薬歴前提取込の実装評価

- **評価日**: 2026-09-23
- **対象**: `for-llm/plan/20260922-nsips-mh-first-fixes.md`、`for-llm/testcase/20260922-nsips-mh-first-fixes.md` と現在の作業ツリーにあるNSIPS薬歴前提取込実装
- **評価者の変更**: アプリケーションコード・テストコードは変更していない。このレポートと進捗記録だけを更新した。
- **判定**: 基本設計の改善と通常品質ゲートは確認できたが、入力の安全性、訂正データの完全な差分検出、NSIPS固有のPostgreSQL原子性が未解決。Generatorへ差し戻す。

## 指摘

### [P1] 未確認のNSIPS列定義を実データとして受け入れ、値を補っている

`app/application/integration/nsips/parser.py` は `csv.reader` の既定区切り文字で解析するため、docstringにあるTSVを扱わない（30–31行）。レコード04は列数が9以上ならRp、それ未満なら調剤日として処理する（56–60行）。列数だけではレコード種別を判別できない。解析結果には `header_version="unverified"` を付けるだけで、後続取込を止めない（124–130行）。さらに氏名の一方が欠けるともう一方を複写し（241–245行）、単位列が無いと `錠`、調製方法フラグ列が無いと `0` を設定する（287–288行）。

テスト自身も合成Fixtureで対象版の仕様適合を主張しないと明記している（`tests/application/integration/nsips/test_parser.py` 1行目）。承認済みテスト仕様のTC-01/02/04/06/07は実仕様・匿名化サンプル待ちである。したがって、現在のraw入力経路が対象NSIPS版を正しく解釈する根拠はなく、未確認の入力を使えるBundleへ変換する危険が残る。

**必要な対応**: 対象版・区切り文字・レコード列の根拠を得てから対応表と実サンプルFixtureを確定する。根拠が得られるまでは `unverified` を単なる情報値にせず、raw経路を明示的に拒否または隔離する。欠損値を既定値や別フィールドから合成しない。

### [P1] 再送・U-fileの差分検出が連携対象全体を比較していない

`app/application/integration/nsips/ingest_nsips.py` の患者差分判定は性別・郵便番号・住所・電話だけを比較し、外部患者番号、漢字/カナ氏名、生年月日は含めていない（645–669行）。処方差分も剤数・剤数量・薬品コード・用量までで、用法指示、薬品単位、調製方法、分割情報、医療機関・処方医などを比較していない（778–813行）。既存薬歴が見つかった場合の加算・調剤日比較はあるが、全受信対象の比較にはなっていない（698–776行）。

差分が見つからない場合、取込は `is_duplicate=True` を返して終了する（217–231行）。そのため、比較対象外の値だけが変わった訂正データは重複として捨てられ、TC-33/34/35が求める保留・競合経路にも進まない。これは計画の「この取込が反映する全項目の差分を比較し、未対応訂正を成功扱いで捨てない」という条件を満たさない。

**必要な対応**: Bundleの連携対象フィールドを一覧化して差分判定を網羅し、表現・自動訂正できない差分は必ず要確認として残す。対象フィールドごとに「差分なら重複にならない」テストを追加する。

### [P1] 承認済みTC-44のNSIPS実PostgreSQLロールバック検証がない

承認済みTC-44は、本番Composition/UoW/RepositoryでNSIPS取込を実行し、薬歴起票など後段失敗時に患者・資格・選択・処方・調剤・薬歴の書込みがすべて消えることを専用PostgreSQL DBで確認する。現在の `tests/integration/` にNSIPS取込のトランザクションテストはなく、`tests/integration/test_nsips_ingestion_transactions.py` も存在しない。既存の汎用・他ユースケースのトランザクションテストは、この取込経路のCompositionと集約書込み順を証明しない。

**必要な対応**: TC-44を実装し、後段失敗時の全件ロールバックと成功時の一括確定を本番配線で検証する。`TEST_DATABASE_URL` を使った統合試験に通るまで、NSIPS経路のDB原子性は未確認として扱う。

### [P2] 構造化入力の空保険番号が要確認にならず、無言で捨てられる

`app/presentational/routers/nsips.py` の `NsipsInsuranceRequest` は必須フィールドを単なる `str` にしており、空文字を拒否しない（104–116行）。一方 `app/application/integration/nsips/mapper.py` は主要項目すべてがtruthyの場合だけ保険資格コマンドを作る（84–100行）。取込側の確認理由も `insurer_number` がtruthyの場合だけ不完全情報を検出する（623–643行）。このため `insurer_number=""` を含む構造化入力では資格が生成されず、`coverage_review_required` も立たない可能性がある。

**必要な対応**: 空白の正規化と必須値検証をHTTP境界で行うか、入力を保持したまま明示的な要確認理由を返す。Mapperで資格が省略される全パターンについて取込結果まで確認するテストを追加する。

### [P3] Application層でClockなしの実時刻フォールバックがある

`IngestNsipsUseCase` は `clock` を任意引数にし（`app/application/integration/nsips/ingest_nsips.py` 143行）、訂正日時を作る際にClockが無ければ `datetime.now(UTC)` を直接呼ぶ（265–269行）。CompositionではClockが注入されているが、依存の欠落を実行時まで検出できず、Application層の時計注入規則にも反する。

**必要な対応**: Clockを必須依存にしてフォールバックを除く。

## 確認できた点

- 未確認の臨床値をnullableで保持し、薬歴確定時に未評価項目を検出する方向は実装されている。
- 必須値がそろわない資格を選択スナップショットへ渡さない処理や、調剤日が無い入力を早期に止める処理が追加されている。
- 構造化HTTP入力のネストモデル、余分なフィールドの禁止、raw/structuredの排他が整備されている。
- 実装済み領域のstrict mypy、Ruff、依存方向・凝集度・Fake適合チェックは通過した。

## 検証結果

- `TEST_DATABASE_URL` を設定した `uv run --locked pytest -q`: **2656 passed, 1 warning**。warningはStarlette `TestClient` と httpx の非推奨通知。PostgreSQLを使う既存統合テストを含む全件は通過したが、上記TC-44の欠落を埋めるものではない。
- `uv run --locked pytest -m integration -q`: **101 passed, 2555 deselected**。
- `uv run --locked mypy app tests tools`: **成功**（597 source files）。
- `uv run --locked ruff check .`: **成功**。
- `uv run --locked ruff format --check .`: **成功**（620 files）。
- `tools.check_imports --verbose --fail-on-violation`: **成功**。
- `tools.check_lcom --verbose --fail-on-violation`: **成功**。
- `tools.check_fake_conformance --verbose --fail-on-violation`: **成功**。

品質ゲートは現在のテストと静的規則への適合を示す。未提供のNSIPS仕様・サンプルへの適合や、未作成のTC-44の原子性を示すものではない。

## Generatorへの差し戻し条件

1. 実仕様・匿名化サンプルの入手状況を確定し、未確認raw形式が取込可能にならない境界を設ける。
2. 再送差分比較を連携対象Bundle全体へ広げ、比較不能・未対応の差分を保留として残す。
3. 承認済みTC-44を本番Composition/UoW/Repositoryと専用PostgreSQLで追加する。
4. 空の構造化保険情報が無言で消えないよう境界検証と取込テストを追加する。
5. Clockを必須依存にする。
6. 上記修正後、全pytest・strict mypy・Ruff・アーキテクチャチェックを再実行し、実DB検証結果を別途報告する。
