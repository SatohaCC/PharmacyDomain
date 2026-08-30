# AGENTS.md

薬局・調剤ドメイン（マルチテナント法人 / 店舗 / スタッフ）のオニオンアーキテクチャ開発ルール。

## コマンド & 品質ゲート

```bash
uv sync --locked                 # 依存同期
uv run pytest -q                 # 全テスト実行（アーキテクチャ規則の検証を含む）
uv run mypy app tests            # 型チェック (strict = true)
uv run ruff check . && uv run ruff format --check .  # Lint & Format チェック

# 実PostgreSQLに対する結合テスト（TEST_DATABASE_URL が無ければ自動スキップ）
docker compose up -d postgres
TEST_DATABASE_URL=postgresql+asyncpg://pharmacydomain:pharmacydomain-dev-password@127.0.0.1:5432/pharmacydomain \n  uv run pytest -m integration -q

# 個別実行（違反箇所を特定したいとき）
uv run python -m tools.check_imports --verbose --fail-on-violation  # 依存の向き
uv run python -m tools.check_lcom --verbose --fail-on-violation     # クラス凝集度
uv run python -m tools.check_fake_conformance --verbose --fail-on-violation  # フェイクのProtocol適合
```

- **言語・コメント**: ドキュメント、docstring、エラーメッセージ、テスト名はすべて**日本語**。
- **品質要求**: `mypy --strict` と `ruff` のチェックを必ずパスさせること。
- **CI**: 上記5つのゲートは `.github/workflows/quality-gate.yml` が `main` への push と全 pull request で実行する。結合テストは PostgreSQL サービスを持つ別ジョブで走る。ゲートを増減するときは、このファイル・本節のコマンド一覧・`tests/tools/test_ci_quality_gate.py` の `REQUIRED_GATES` の3つを揃えないと pytest が落ちる。**ブランチ保護は未設定なので、赤いまま `main` へ push すること自体は止まらない**（GitHubのリポジトリ設定でしか変えられず、リポジトリ内のファイルからは強制できない）。
- **パッケージ構成**: `app/` `tests/` `tools/` 配下で `.py` を持つディレクトリには必ず `__init__.py` を置く。名前空間パッケージのままだと、(1) そのディレクトリだけを指定して `pytest` を回したときにルートが `sys.path` に入らず `app` を import できない、(2) 別ディレクトリに同名モジュールを置いた瞬間にトップレベル名が衝突して収集が壊れる。`tests/tools/test_package_layout.py` が強制する。
- **結合テストの分離**: 実DBを要するテストは `tests/integration/` に置き、`TEST_DATABASE_URL` が無ければ自動でスキップする。スキップは「実行したが何も確かめていない」状態なので、CIでは必ずDBを与える専用ジョブで `-m integration` を走らせる。マーカーは `tests/integration/conftest.py` が自動で付ける（各モジュールで付け忘れると、DBの無いジョブ側へ紛れ込む）。
- **アーキテクチャ規則**: 依存の向き・凝集度・フェイクのProtocol適合は `tools/` の静的チェッカが強制する。設定は `pyproject.toml` の `[tool.import_rules]` / `[tool.lcom]` / `[tool.fake_rules]`、実行は `tests/tools/test_architecture_rules.py` 経由で `pytest` に含まれる。設計ルールを追加するときは、文章だけでなくチェッカの設定にも反映する。

## アーキテクチャ & 設計ルール

- **正典の分担**: プロジェクト目的と全体像は [docs/README.md](docs/README.md)、重要な設計判断と理由は [docs/decisions.md](docs/decisions.md)、外部根拠と未解決事項は対応する `docs/ddd/` 文書に置く。現在の型と振る舞いは `app/`、実行可能な保証は `tests/` と `tools/`、実装手順と品質ゲートは本ファイルを正典とする。
- **文書とコードの分離**: コードと通常テストは `docs/` のパス・見出し・ADR番号・文書用の不変条件IDを参照しない。必要な理由は、その箇所だけで理解できる語彙でdocstringやテスト名に書く。文書にはクラス・フィールド・テスト・不変条件の網羅表を複製せず、目的、境界、採否の理由、一次資料の解釈、未解決事項が変わるときだけ更新する。`tests/tools/test_docs_decoupling.py` は、文書を指すことが構文だけで確定する3形式（パス・ADR番号・不変条件ID）を検出して強制する。見出し名は改名・削除後の古い参照を判定できず、普通のドメイン語彙とも衝突するため、機械検査の対象にしない。
- **依存の向き**: 外 → 内（`app/domain/` は FastAPI, DB, `app/application/` に一切非依存）。`tools/check_imports.py` が強制する。
- **共通コードの配置**: Domainモデリング基盤は `app/domain/foundation/`、所有者のいない語彙と複数コンテキストで共有する規則は `app/domain/shared/`、Application層の共通処理は `app/application/common/` に置く。DDDのShared KernelはDomain語彙だけを指し、Application共通処理をShared Kernelと呼ばない。`foundation` は標準ライブラリだけ、`shared` は `foundation` だけ、`application/common` は標準ライブラリだけに依存させる。新しいコンテキストを追加するときは `[tool.import_rules.forbidden]` の3パッケージの禁止先と対応する設定テストも更新する。
- **テナント境界**: コンテキストは `corporate` / `store` / `staff` / `patient` / `coverage` / `reception` / `claim` / `prescription` / `dispensing` / `medication_history` / `medicine_catalog` の11。集約間は **ID 参照のみ**（他集約のエンティティを直接保持しない）。他テナントデータへのアクセスは 403 ではなく 404（`XxxNotFoundError` または `TenantBoundaryNotFoundError`）として隠蔽する。
- **認証・認可境界**: 認証基盤が生成した信頼済み `ActorContext` をApplication層へ渡し、Command / Queryの対象 `corporate_id` と分離する。ベンダーシステム管理者は全法人、法人管理者は `ActorContext.corporate_id` と一致する自法人だけを操作できる。HTTP入力から `ActorContext` を組み立てない。
- **法人ライフサイクル**: `CorporateStatus.INACTIVE` の法人に対するStore / Staff / Patient / Coverage / Receptionの通常操作は `CorporateAccessService` で拒否し、状態変更はベンダーシステム管理者専用とする。Corporate自体には管理者ユーザーやロールを保持させない。
- **Applicationコンテキストの依存**: Store / Staff / Patient / Coverage / Reception は法人コンテキストや他コンテキストのApplication実装を import しない。対象法人の認可・有効状態は `access_control` の `CorporateAccessBoundary`（Protocol）にだけ依存させる。CoverageはPatientのAggregateやApplication実装を参照せず、`PatientId`の存在確認はID参照Protocolまたは永続化制約で行う。Receptionは店舗・患者・資格選択の参照Boundaryにだけ依存し、資格台帳やPatient/StoreのAggregateを保持しない。Coverage台帳からClaim Snapshotを作る接続は `app/application/composition/` の実アダプタへ閉じ込める。実装 `CorporateAccessService` とComposition実装を import するのは Composition Root とテストのみ。逆向きの import は `tools/check_imports.py` が検出する。新しいコンテキストを追加するときは `[tool.import_rules.forbidden]` にも規則を足す。
- **集約の不変性**: `Entity` / `AggregateRoot` は `@dataclass(frozen=True, eq=False, kw_only=True)`。状態変更メソッド（`change_*`）は `dataclasses.replace()` で新インスタンスを返すため**必ず戻り値を受け直す**。
- **Domain Primitive**: フィールドは `value` 1つで位置引数で生成（`StoreName("サンプル名")`）。`Base*` は継承専用としフィールドの型には使わない。IDは UUIDv7（`XxxId.generate()` / `XxxId.parse()`）。
- **複数集約ルール**: 複数集約に跨る検証（例: スタッフと店舗の法人一致）は、本物の集約を受け取る無状態 **Domain Service**（`StaffStoreAssignmentService` 等）が担当する。法人の存在・有効状態・Actor権限の検証はApplication層の `CorporateAccessService` が担当する。単一集約で完結する不変条件を Domain Service 側にも重複して置かない（片方を壊しても気づけなくなる）。
- **スタッフ所属履歴の不変条件**: `Staff.affiliations` は、所属期間を `[start_date, end_date]`（`end_date=None` は無期限）とみなしたとき、(1) `is_primary=True` の所属が店舗を問わず互いに重ならないこと、(2) 同一 `store_id` の所属が主所属・兼務を問わず互いに重ならないことを `Staff.validate()` が構築時に強制する。導出メソッド（`current_home_store_id` / `current_concurrent_store_ids`）は例外を送出しない全域関数とする。読み取り時に不整合を検出する設計は、検出が遅れるうえ例外を期待しない呼び出し元へ漏れるため採らない。
- **退職は所属履歴へ書き込む**: `Staff.deactivate(retired_on)` は退職日を必須で受け取り、退職日以降に及ぶ所属をその日で打ち切る。適用日を取る導出の内側で日付なしの `is_active` を見て打ち切ってはならない（退職した瞬間に、在籍していた過去日の所属まで引けなくなる）。退職日より後に開始する配属予約が残っている場合は期間として成立しないので、黙って捨てず `AffiliationDateConflictError` で拒否する。所属を増やす操作（`transfer_home_store` / `assign_concurrent_store`）は無効化済みスタッフに対して `InactiveStaffAssignmentError` で拒否し、既存の期間を閉じる `remove_concurrent_store` は許可する（退職後に履歴を訂正できなくなるほうが害が大きい）。有効化は所属を復元しない。
- **空文字の正規化**: 任意項目の空文字・空白は Application 境界（`to_optional_text`）で `None` に正規化する（項目解除を意味する）。定義は Application共通基盤の `app/application/common/input_normalization.py` に1つだけ置き、各コンテキストの `support.py` は再エクスポートするだけに留める（複製するとコンテキスト間で正規化ルールが分岐する）。
- **資格の時間境界**: `CoveragePeriod` は終了日を含む `[valid_from, valid_to]`、`CoverageActivation` は無効化発効日を含まない `[activated_on, deactivated_on)` とする。実効期間は両者の交差であり、無効化発効日当日は無効。同日再無効化だけを冪等として許可し、異なる発効日への変更は拒否する。Domain / Applicationで `date.today()` を暗黙利用せず、適用日を明示する。これは ruff の `DTZ` ルール（`flake8-datetimez`）が強制する。`date.today()`（DTZ011）と tz なしの `datetime.now()`（DTZ005）は lint で落ちるため、現在時刻が要るなら `app/application/common/clock.py` の `Clock` を注入する。唯一の正当な例外は Composition Root の `SystemUtcClock` で、こちらは `datetime.now(UTC)` なので DTZ に触れない。naive 日時が拒否されることを確認するテストだけは `# noqa: DTZ001` で意図を明示する。
- **適用資格の履歴**: `PatientCoverage` は個別資格の台帳として維持し、最後に使った組み合わせを保持しない。受付時の選択はReceptionの `CoverageSelectionRecord` に、業務日 `applied_on`、`CoverageSelection`、認可Actor由来の記録者、注入Clock由来のUTC記録時刻を保存する。最新履歴は同一法人・店舗・患者の初期候補にすぎず、`CoverageValidityBoundary` で `CoverageSelection` を適用日ごとに再構築・等価比較する。`is_still_valid=False` の候補を自動適用してはならない。
- **選択は枠で持つ**: 元資格IDと請求固定値を「ID列」と「Snapshot」の平坦な2フィールドへ分けない。分けると両者の対応が並び順の規約になり、件数一致しか検証できなくなる。`CoverageSelection` は医療保険枠0〜1個と公費枠0〜4個からなり、各枠が `source_coverage_id` と `values`（Claim の Snapshot 要素）を分離不能に1対1で束ねる。公費の順位は `values` 側にあるので、並べ替えてもIDとの対応が動かない。`CoverageSelectionRecord.snapshot` と `.source_coverage_ids` は枠構造からの導出 property であり、独立した記憶域を持たない（永続化実装を入れるときも `selection` だけをマップし、この2つは列にしない）。集約が守れるのは枠構造の一致までで、「その元IDが本当にその資格を指すか」は `CoverageValidityBoundary` の再検証に依存し続ける。
- **資格の適用枠**: 医療保険は同一患者・同一期間に1件だけで適用順位は1に固定する。公費は第一から第四までを順位で管理し、医療保険1件と複数の公費（例: 第一公費・第二公費）を同時に `CoverageSnapshot` へ固定できる。公費は同じ順位の期間だけを競合させ、異なる順位は併用可能とする。医療保険の一意性は「同一制度かつ同一順位」の判定に含まれるため、`PatientCoverageConflictService` で `coverage_type` を別途分岐させない。
- **レセプト番号の桁数**: 電子レセプトで桁数が定まる番号は、桁数をプリミティブの不変条件として持たせる。保険者番号（`InsurerNumber`）は6桁または8桁、公費負担者番号は8桁、公費受給者番号は7桁、枝番は2桁。桁数規定のない被保険者記号・番号は `CoverageSymbol` / `CoverageCode` として空でないことだけを要求する。Claim側の `ClaimInsurerNumber` / `ClaimPublicPayerNumber` / `ClaimPublicRecipientNumber` / `ClaimCoverageBranchNumber` にも同じ検証を持たせ、Boundary実装が不正値を凍結できないようにする。
- **スナップショットの必須項目**: `InsuranceCoverageSnapshot.benefit_ratio` は必須。給付割合は患者負担額を決める値であり、スナップショットが存在する目的そのものなので台帳側（`InsuranceCoverageDetails`）と必須性を揃える。公費は `CoverageSnapshot` で第一公費から順位が連続していることを検証する（第一公費が空で第三公費だけを持つ組み合わせはレセプト提出時に返戻される）。
- **公費順位の規則は1箇所**: 「上限4件・重複なし・第一公費から連続」の判定は Shared Kernel の `app/domain/shared/priority_rules.py` の `find_priority_violation()` だけが持つ。`CoverageCombination`（選択時）と `CoverageSnapshot`（凍結前の最終防衛）は役割が違うので**検証点は2つ残す**が、規則本体を2箇所に書くと片方だけ直る事故が起きる。各コンテキストは違反種別を自分の例外型とメッセージへ対応づけるだけにする。Coverage と Claim は互いに import できないため、共有先は Shared Kernel になる（共有規則は int の列だけを扱い、個別コンテキストに依存しない）。
- **無効化と一意性**: 無効化後に一意キーを再利用できるかは**集約ごとに異なる業務判断**であり、全称のルールにしない。`PatientExternalIdentifier` は有効な行にだけ一意性を要求し再利用を許す（誤った患者へ紐付けた外部IDを無効化してから正しい患者へ付け替えるため。無効化を終端にすると外部IDが恒久的に使えなくなる）。`Staff` はスタッフコードを無効化後も再利用させない（過去の調剤録・監査の追跡を壊さないため）。どちらに倒すかは `tests/domain/test_lifecycle_dialects.py` の `ACTIVE_FLAG_KEY_REUSE` に記録し、実挙動は各コンテキストの契約テストで固定する。判断を書かずに `is_active` を足すことはできない（表に行が無いと落ちる）。
- **ライフサイクル表現**: 集約の無効化の表し方は `none` / `active_flag` / `status_enum` / `dated_activation` の4方言に限る。日付つき無効化（`dated_activation`）が最も表現力が高いが、遡及判定を必要とする到達可能なUseCaseが現れるまでは全集約へ広げない。方言の追加・集約の追加・既存集約の方言変更は `tests/domain/test_lifecycle_dialects.py` の表を編集しない限り pytest が落ちる。
- **Reception権限**: 資格台帳の編集・参照は `MANAGE_COVERAGE` / `VIEW_COVERAGE`、受付時の資格選択履歴の登録・参照は `MANAGE_RECEPTION` / `VIEW_RECEPTION` として分離する。到達可能なClaim UseCaseがない間はClaim権限を定義しない。
- **Repositoryの最終防衛**: `PatientCoverageRepository.save()` は実効期間の競合を、`PatientExternalIdentifierRepository.save()` は有効な外部IDの重複を、同じ集約IDを除外した上で原子的に拒否する契約とする。Applicationの事前readは早期エラー用であり原子性の代替ではない。この契約は `tests/contracts/test_repository_contracts.py` が `tests/fakes/` 配下の実装を**自動列挙**して全実装に課すため、新しい実装を足しても登録漏れが起きない。PostgreSQL実装では、この最終防衛を一意制約と部分一意インデックスが担う。
- **テストダブルの適合性**: テストダブルは実装する Protocol を明示継承し、**全メンバを上書きする**。上書きし忘れると Protocol 本体の `...` を実装として継承し、呼んでも例外にならず `None` が返るため、Protocol 側の改名・追加にフェイクが静かに追随できなくなる。`tools/check_fake_conformance.py` が pytest 内で検出する。対象パスは `pyproject.toml` の `[tool.fake_rules]` に列挙する。**本番の永続化アダプタも同じ穴を持つ**ので（Protocolを明示継承しているため）、`app/infrastructure` も対象に含める。
- **Domain依存規則**: `tools/check_imports.py` でCoverageからPatient Aggregate/RepositoryとClaim/Receptionへの直接依存、ClaimからCoverage/Reception・Patient・StoreのAggregate/Repositoryへの直接依存、ReceptionからCoverage台帳やPatient/Store Aggregate/Repositoryへの直接依存を禁止する。集約間はID Primitive、不変Snapshot、またはBoundaryで参照する。
- **集約モジュール単位の禁止**: Domain Service が他コンテキストの集約を引数で受け取る場合（`DispensingConsistencyService` が `Prescription` を、`MedicationHistory` が `DispensingProcess` を）、パッケージ全体では禁止できない。**集約モジュールにだけ**禁止を課す（`"app.domain.dispensing.dispensing_process"` の行）。こうしないと `validate()` から他集約を読めてしまい、ロードできない検証を書ける。
- **非テナントのコンテキストは `medicine_catalog` だけ**: 薬価基準は国が定めるので法人ごとに内容が違わない。`corporate_id` を付けて法人ごとに複製すると、改定のたびに全テナント分を更新する羽目になる。したがって `Medicine` 集約も `MedicineCatalogRepository` も法人IDを取らず、取り込みは `require_vendor_system_admin()` でベンダー専用にする。`tests/domain/medicine_catalog/test_medicine.py` が「法人IDを持たない」ことを固定する。「自局で採用している薬か」はテナントごとの判断だが、それは別集約（自局採用薬・未実装）の責務。
- **参照マスタは時点で引く**: 麻薬指定も経過措置期限も改定で変わる。`MedicineCatalogRepository.find_effective()` と `MedicineRestrictionBoundary.classify()` は **`as_of` を必ず取る**。「今」で引くと過去の処方を新しいマスタで判定してしまう。処方箋の判定に渡すのは**交付日**であって処理実行日ではない。
- **所有者のいない語彙はShared Kernelへ**: `PatientId` のような「集約の同一性」は所有コンテキストから import する。一方、薬品名・用量・用法はどの集約の同一性でもなく、複数コンテキストが同じものを必要とする。こうした**所有者のいない語彙**は `app/domain/shared/medicine.py` / `dosage.py` に置く。所有コンテキストへ置くと、薬歴が「他院で買ったOTCの名前」を表すために Prescription を import することになる。
- **用量に `float` を使わない**: 実在する用量刻み（0.05刻み等）で不均等服用の合計が一致せず、正当な処方を弾く（6,859通りのうち869通りで失敗する）。`BaseNonNegativeDecimal` / `BasePositiveDecimal` を使い、Application境界では `str` で受けて `Decimal` へ変換する。`tests/domain/test_decimal_primitives.py` が全数で固定する。
- **判定できないことを「該当しない」に倒さない**: 医薬品マスタが無い状態で麻薬区分を「該当しない」と答えると、麻薬処方箋の必須項目チェックが素通りする。`MedicineRestrictionFlag` は `UNKNOWN` を明示的に持ち、Domain Service がそれを拒否する（fail-closed）。到達可能なUseCaseを作らないのではなく、**作った上で失敗させる**（分岐を書くと、マスタが入ったときに消し忘れる）。
- **`is_active` は集約ルートだけ**: 期間（`ended_on` 等）から導出できる子レコードに真偽フラグを足すと、同じ事実の表現が2つになり必ず食い違う。`tests/domain/test_active_flag_placement.py` が `app/domain` の全 dataclass を走査し、`is_active` を持つクラスの集合を表で固定する。方言表（`test_lifecycle_dialects.py`）は集約ルートしか見ないので、これが子レコード側の歯止めになる。
- **投影集約に直接編集を許さない**: `PatientMedicalProfile`（頭書き）は薬歴からの投影であり、状態変更は `apply(record)` だけ。個別の `register_*` を公開すると、薬歴に由来しない要素を作れて再構築が不可能になる。保存順序は `save(record)` → `save(profile)` で固定し、同じ UnitOfWork で確定する。後者が失敗した場合も薬歴から作り直せる。
- **Boundaryの例外契約**: 参照Boundary（Protocol）の `Raises:` に、他テナント・未存在をどの例外へ畳み込むかを明記する。他テナントのデータは存在を隠すため404相当の `XxxNotFoundError` に揃え、`AuthorizationError` を送出しない（存在が漏れる）。契約は `tests/fakes/` のフェイク実装（Receptionは `tests/fakes/reception_reference_boundaries.py`）とユースケーステストで実行可能な形にし、定義だけで raise されない例外を残さない。

### 永続化（Infrastructure層）

- **層の位置**: 永続化アダプタは `app/infrastructure/` に置き、Domain / Application からは import しない。接続は Composition Root（`app/infrastructure/composition/` パッケージ）が Protocol へ行う。逆向きの import は `tools/check_imports.py` が検出する。
- **1行1集約**: 集約は JSONB の `payload` 列を正とし、検索・一意性制約に必要な値だけを列へ複製する。読み込み時に列と payload の食い違いを検出して復元を拒否する（列だけ書き換えられた行を集約として通さない）。
- **列の食い違いを実行前に落とす**: 「テーブル定義」「マイグレーション」「Repositoryが書く値」は持ち場が分かれるため、食い違っても実DBに繋ぐまで誰も落ちない。`tests/infrastructure/postgres/test_schema_migration_consistency.py` が、マイグレーションをオフラインで実行して得たDDLとスキーマ定義のDDLを比較し、さらにRepositoryが書く列がテーブルに存在することをDBなしで検査する。
- **保存は1文で原子的に**: 事前 `SELECT` で存在を確かめてから `INSERT` / `UPDATE` を分けない。同一IDの同時保存で両方が「存在しない」を見て両方 `INSERT` し、主キー違反が素の `IntegrityError` として漏れる。`INSERT ... ON CONFLICT (id) DO UPDATE` の1文にする。
- **楽観ロック**: 集約を1行のJSONBで持つ以上、後勝ちの上書きは行全体を失う。全テーブルに `version` 列を置き、更新は「このトランザクションで読み込んだ世代」と一致する行だけに当てる。0行なら `ConcurrentModificationError` を送出する。世代の追跡は `PostgresUnitOfWork` がトランザクション単位で保持し、Repositoryごとには持たせない（複数Repositoryが同じ行を読むと世代が分裂する）。
- **Unit of Work は必須依存**: 複数の集約を書くUseCaseは `UnitOfWork` を**必須の**コンストラクタ引数で受け取る。省略可能にすると、渡し忘れが型検査もテストも通ったまま非トランザクション経路へ落ちる。トランザクションを持たないインメモリ経路には `tests/fakes/null_unit_of_work.py` の何もしない実装を渡す。
- **commit 忘れを握り潰さない**: `PostgresUnitOfWork.__aexit__` は正常終了でも `rollback()` を呼ぶ。`close()` の暗黙のロールバックに任せると、`commit()` を忘れた経路が例外なしのデータ消失になる。
- **期間の重なりは排他制約で守る**: 「同一患者・同一順位で実効期間が重なる資格を拒否する」「同一薬品コードで収載期間が重なる行を拒否する」は一意制約では表せない。`daterange` と `EXCLUDE USING gist` で表し、``btree_gist`` 拡張をマイグレーションで有効にする。ドメインの期間はどちらも**終了日を含む閉区間**なので、範囲の境界は `[]` で作る。半開区間にすると、経過措置期限当日の調剤や、終了日の翌日から始まる資格を誤って弾く。
- **任意項目の一意性はNULLを除く**: 店舗コード・保険薬局指定番号のような任意項目は、部分一意インデックス（`WHERE ... IS NOT NULL`）にする。未設定どうしを衝突させると正当な登録を弾く。
- **無効化と一意性の向きは集約ごとに違う**: 外部患者IDは有効行だけを一意にし（`WHERE is_active`）、スタッフコードは無効化後も再利用させない（`is_active` で絞らない）。同じ「無効化フラグ」でも制約の書き方が逆になるので、部分インデックスの条件を機械的に真似しない。
- **`=` はNULLを等しいと扱わない**: 排他制約や一意制約のキーにNULLを取りうる列を使うと、ドメインの等価性とずれる。`MedicineIdentifier` のように NULL を含む組で同一性を表す場合は、非NULLのキー文字列（`identifier_key`）を別に持って揃える。
- **`AsyncSession` は使い回さない**: セッションは並行実行安全ではないので、Unit of Work とRepositoryは1リクエスト単位で組み立てる。
- **ドライバの挙動をダブルで代用しない**: 制約名の取り出し方、`ON CONFLICT` が当たる行数、部分一意インデックスが弾く行は、サーバとドライバが決める。テストダブルは推測ではなく実物の構造を写した形にし、実物の確認は `tests/integration/` で行う。実際、制約名は psycopg2 の `diag` ではなく asyncpg 例外の `constraint_name` にあり、ダブルを推測で書いていた間はDBなしのテストだけが緑になっていた。

## テスト指針

- AAA パターン（`Arrange` / `Act` / `Assert`）。
- **Domain モデルをモックしない**。実オブジェクトと `tests/fakes/` のインメモリ Repository を使用。
- テスト名は `test_<対象>_<条件>_<期待結果>`。

## 新しいユースケースの追加手順

1. `app/application/<context>/<use_case_name>.py` に `XxxCommand` DTO と `XxxUseCase` クラスを同居作成。
2. 処理フロー: Command 文字列 → Primitive 変換 → `CorporateAccessService` → `load_*_or_raise()` → Domain Service（検証） → 集約の `change_*`（戻り値受け直し） → `repository.save()`。認可に必要なActorはCommandへ入れず、UseCaseの依存として注入する。
3. 返却値は `XxxDto.from_entity()`（エンティティを直接返さない）。
4. `__init__.py` の `__all__` に追加し、`tests/application/<context>/test_<use_case_name>.py` を作成。

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
