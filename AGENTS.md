# AGENTS.md

薬局・調剤ドメイン（マルチテナント法人 / 店舗 / スタッフ）のオニオンアーキテクチャ開発ルール。

## コマンド & 品質ゲート

```bash
uv sync --locked                 # 依存同期
uv run pytest -q                 # 全テスト実行（アーキテクチャ規則の検証を含む）
uv run mypy app tests            # 型チェック (strict = true)
uv run ruff check . && uv run ruff format --check .  # Lint & Format チェック

# 個別実行（違反箇所を特定したいとき）
uv run python -m tools.check_imports --verbose --fail-on-violation  # 依存の向き
uv run python -m tools.check_lcom --verbose --fail-on-violation     # クラス凝集度
```

- **言語・コメント**: ドキュメント、docstring、エラーメッセージ、テスト名はすべて**日本語**。
- **品質要求**: `mypy --strict` と `ruff` のチェックを必ずパスさせること。
- **アーキテクチャ規則**: 依存の向きと凝集度は `tools/` の静的チェッカが強制する。設定は `pyproject.toml` の `[tool.import_rules]` / `[tool.lcom]`、実行は `tests/tools/test_architecture_rules.py` 経由で `pytest` に含まれる。設計ルールを追加するときは、文章だけでなくチェッカの設定にも反映する。

## アーキテクチャ & 設計ルール

- **ナレッジベース**: 正典は [okf/](okf/)。設計方針の決定・変更時はコードと合わせて更新する。
- **依存の向き**: 外 → 内（`app/domain/` は FastAPI, DB, `app/application/` に一切非依存）。`tools/check_imports.py` が強制する。
- **テナント境界**: コンテキストは `corporate` / `store` / `staff` / `patient` / `coverage` / `claim` の6つ。集約間は **ID 参照のみ**（他集約のエンティティを直接保持しない）。他テナントデータへのアクセスは 403 ではなく 404（`XxxNotFoundError` または `TenantBoundaryNotFoundError`）として隠蔽する。
- **認証・認可境界**: 認証基盤が生成した信頼済み `ActorContext` をApplication層へ渡し、Command / Queryの対象 `corporate_id` と分離する。ベンダーシステム管理者は全法人、法人管理者は `ActorContext.corporate_id` と一致する自法人だけを操作できる。HTTP入力から `ActorContext` を組み立てない。
- **法人ライフサイクル**: `CorporateStatus.INACTIVE` の法人に対するStore / Staff / Patient / Coverage / Claimの通常操作は `CorporateAccessService` で拒否し、状態変更はベンダーシステム管理者専用とする。Corporate自体には管理者ユーザーやロールを保持させない。
- **Applicationコンテキストの依存**: Store / Staff / Patient / Coverage / Claim は法人コンテキストや他コンテキストのApplication実装を import しない。必要なのは「対象法人の認可と有効状態を確認して集約を得る」ことだけなので、`access_control` の `CorporateAccessBoundary`（Protocol）にだけ依存させる。CoverageはPatientのAggregateやApplication実装も参照せず、`PatientId`の存在確認はID参照Protocolまたは永続化制約で行う。Claimは選択された資格を請求側スナップショットへ変換する `CoverageSnapshotBoundary`、店舗・患者の存在を確認する参照Boundaryに依存し、資格台帳やPatient/StoreのAggregateを保持しない。実装 `CorporateAccessService` を import するのは Composition Root とテストのみ。依存は `claim` → `access_control`、`coverage` → `access_control`、`patient` → `access_control`、`staff` → `store` → `access_control`、`corporate` → `access_control` の一方向で、逆向きの import は `tools/check_imports.py` が検出する。新しいコンテキストを追加するときは `[tool.import_rules.forbidden]` にも規則を足す。
- **集約の不変性**: `Entity` / `AggregateRoot` は `@dataclass(frozen=True, eq=False, kw_only=True)`。状態変更メソッド（`change_*`）は `dataclasses.replace()` で新インスタンスを返すため**必ず戻り値を受け直す**。
- **Domain Primitive**: フィールドは `value` 1つで位置引数で生成（`StoreName("サンプル名")`）。`Base*` は継承専用としフィールドの型には使わない。IDは UUIDv7（`XxxId.generate()` / `XxxId.parse()`）。
- **複数集約ルール**: 複数集約に跨る検証（例: スタッフと店舗の法人一致）は、本物の集約を受け取る無状態 **Domain Service**（`StaffStoreAssignmentService` 等）が担当する。法人の存在・有効状態・Actor権限の検証はApplication層の `CorporateAccessService` が担当する。
- **空文字の正規化**: 任意項目の空文字・空白は Application 境界（`to_optional_text`）で `None` に正規化する（項目解除を意味する）。定義は Shared Kernel の `app/base/application/support.py` に1つだけ置き、各コンテキストの `support.py` は再エクスポートするだけに留める（複製するとコンテキスト間で正規化ルールが分岐する）。
- **適用資格の履歴**: `PatientCoverage` は個別資格の台帳として維持し、「最後に使った組み合わせ」や `last_used_at` を保持しない。調剤・請求時にClaim側の `CoverageSnapshot` と `CoverageUsage` を保存し、最新履歴は同一法人・店舗・患者の初期候補として参照する。候補は適用日で再検証し、資格が無効なら自動適用しない。再検証は `CoverageValidityBoundary`（Protocol）へ委ね、`GetLastCoverageUsageQuery.applied_on` を必須にして `LastCoverageUsageCandidateDto.is_still_valid` として結果を返す。フラグが `False` の候補を自動適用してはならない。
- **資格の適用枠**: 医療保険は同一患者・同一期間に1件だけで適用順位は1に固定する。公費は第一から第四までを順位で管理し、医療保険1件と複数の公費（例: 第一公費・第二公費）を同時に `CoverageSnapshot` へ固定できる。公費は同じ順位の期間だけを競合させ、異なる順位は併用可能とする。医療保険の一意性は「同一制度かつ同一順位」の判定に含まれるため、`PatientCoverageConflictService` で `coverage_type` を別途分岐させない。
- **レセプト番号の桁数**: 電子レセプトで桁数が定まる番号は、桁数をプリミティブの不変条件として持たせる。保険者番号（`InsurerNumber`）は6桁または8桁、公費負担者番号は8桁、公費受給者番号は7桁、枝番は2桁。桁数規定のない被保険者記号・番号は `CoverageSymbol` / `CoverageCode` として空でないことだけを要求する。Claim側の `ClaimInsurerNumber` / `ClaimPublicPayerNumber` / `ClaimPublicRecipientNumber` / `ClaimCoverageBranchNumber` にも同じ検証を持たせ、Boundary実装が不正値を凍結できないようにする。
- **スナップショットの必須項目**: `InsuranceCoverageSnapshot.benefit_ratio` は必須。給付割合は患者負担額を決める値であり、スナップショットが存在する目的そのものなので台帳側（`InsuranceCoverageDetails`）と必須性を揃える。公費は `CoverageSnapshot` で第一公費から順位が連続していることを検証する（第一公費が空で第三公費だけを持つ組み合わせはレセプト提出時に返戻される）。
- **無効化と一意性**: `is_active` を持つ集約の一意性は「有効な行」に対してだけ要求する。外部患者ID（`PatientExternalIdentifier`）は無効化済みの行を衝突扱いにしないため、誤った患者へ紐付けた外部IDを無効化してから正しい患者へ付け替えられる。無効化を終端にすると外部IDが恒久的に使えなくなる。
- **Claim権限**: 資格台帳の編集・参照は `MANAGE_COVERAGE` / `VIEW_COVERAGE`、請求時点の利用履歴の登録・参照は `MANAGE_CLAIM` / `VIEW_CLAIM` として分離する。
- **Domain依存規則**: `tools/check_imports.py` でCoverageからPatient Aggregate/Repositoryへの直接依存、ClaimからCoverage・Patient・StoreのAggregate/Repositoryへの直接依存を禁止する。集約間はID PrimitiveまたはBoundaryで参照する。
- **Boundaryの例外契約**: 参照Boundary（Protocol）の `Raises:` に、他テナント・未存在をどの例外へ畳み込むかを明記する。他テナントのデータは存在を隠すため404相当の `XxxNotFoundError` に揃え、`AuthorizationError` を送出しない（存在が漏れる）。契約は `tests/fakes/claim_reference_boundaries.py` のフェイク実装とユースケーステストで実行可能な形にし、定義だけで raise されない例外を残さない。

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
