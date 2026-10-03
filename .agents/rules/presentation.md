---
trigger: always_on
description: オニオンアーキテクチャ Presentation層（FastAPI、HTTPルータ、エラー翻訳、認証窓口、OpenAPI）の開発ルール。
---

# Presentation層（HTTP境界 & API）開発ルール

Presentation層はFastAPIによるHTTPエンドポイント、リクエスト/レスポンス変換、例外翻訳、認証窓口を担当します。内側からは参照されず、DBドライバ（SQLAlchemy）を直接触りません。

## ルーティング & 認証

- **層の位置**: HTTPルータ・例外翻訳・認証窓口は `app/presentational/` に置く。内側からは参照されない。`app.presentational` から `sqlalchemy` を直接触ることを禁止する。
- **認証はProtocolの向こう側**: `ActorContextProvider` が受け取るのはBearerトークンだけで、ロールと所属法人を決めるのは実装側の責務とする。HTTP入力から `ActorContext` を組み立てない。既定実装 `UnconfiguredActorContextProvider` は常に401を返す。
- **認証はルータ単位で掛ける**: `APIRouter(dependencies=[Depends(get_actor_context)])` とする。ルート関数の引数に頼らない。
- **全ユースケースにルートを与える**: `tests/presentational/test_route_coverage.py` が登録簿の全束・全ユースケースに対して、対応するルータが参照していることを検査する。
- **検証できないIDをパスへ載せない**: ユースケースが受け取らないIDをURLへ入れない（例: 外部患者ID操作は `/patient-external-identifiers/{identifier_id}`）。
- **権限判定をルータへ持ち込まない**: ベンダー専用操作かどうかはユースケースが `Permission` で要求し、`AuthorizationService` が判定する。
- **開発用の認証は起動点ごと分ける**: 固定トークンで通す開発用の窓口は `app/presentational/dev_main.py` に置き、`create_dev_app()` を uvicorn の `--factory` から呼ぶ。`Dockerfile` の `CMD` は `app.main:app` のまま変えず、開発用の起動点を指すのは `compose.yaml` だけにする。
- **エンジンはlifespanでだけ作る**: `create_app()` はモジュール読み込み時にDBへ触らない。トランザクションの開始と確定は `PostgresRequestScope` に任せ、ルータは `commit` も `rollback` も呼ばない。

## リクエスト & レスポンス規約

- **本文の形を1つに揃える**: `DomainError` / `ApplicationError` / `PresentationError`、FastAPI の `RequestValidationError`、Starlette の `HTTPException` をすべて `ErrorResponse`（`code` / `message` / `errors`）へ翻訳する。500だけは翻訳しない。
- **失敗応答の契約は1箇所**: ステータス・本文・OpenAPIへの記載は `app/presentational/errors.py` だけが持つ。ルータで `try/except` を書かない。
- **認証方式をOpenAPIへ載せる**: `Authorization` を `Header()` で直接読まず、`fastapi.security.HTTPBearer` を `Depends` に置く。
- **返しうるエラーをOpenAPIへ書く**: ルータとルートに `error_responses(...)` を渡す。書き込みルートは楽観ロック衝突でも409になるので、`POST` と `PATCH` には必ず409を書く。
- **入れ子の入力はApplication層のDTOをそのまま使う**: 処方箋の剤・調剤内容などの入れ子は、Presentation層で写し取らずに `*Input` をリクエストモデルの型に置く。
- **未知の項目は拒否する**: リクエスト本文は `RequestModel`（`extra="forbid"`）を継承させる。
- **状態の非対称を真偽値へ畳まない**: 退職と有効化の非対称は真偽値へ隠さず、`POST /retirement` と `POST /reactivation` に分ける。
- **応答にドメインの語彙を載せない**: Application層のDTOはドメインプリミティブを保持してよいが、**応答モデルに使うDTO**は素の型（`str` など）へ落とす。任意のID参照は `optional_id()` で落とす。`tests/presentational/test_response_shapes.py` が検査する。
