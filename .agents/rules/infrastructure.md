---
trigger: always_on
description: オニオンアーキテクチャ Infrastructure層（PostgreSQL、SQLAlchemy、永続化、排他制約、DI束）の開発ルール。
---

# Infrastructure層（永続化 & DI）開発ルール

Infrastructure層はPostgreSQLへの永続化アダプタとユースケースの配線（Composition Root）を担当します。Domain層やApplication層からはimportされず、DIによってProtocolへ接続されます。

## ディレクトリ構成 & 責務

- **層の位置**: 永続化アダプタは `app/infrastructure/postgres/`、ユースケースの配線（Composition Root）は `app/infrastructure/di/` に置き、Domain / Application からは import しない。接続は `di/` が Protocol へ行う。
- **Infrastructureのファイル構成**: `postgres/` は **SQLAlchemy に触る場所**に限る（`schema`, `connection`, `codec`, `repository_base`, `repositories/`）。配線は `di/` へ分け、`root`、`registry`、`bundles/` を置く。
- **Repositoryは1集約1ファイル**: ファイル名は Repository 名から `Postgres` と `Repository` を除いたものに揃える。
- **ユースケース配線は束のまま**: `di/bundles/` を `organization` / `patient_care` / `clinical` / `medicine_catalog` の4つにまとめる。`medicine_catalog` だけを単独の束に残すのは、法人IDを取らない唯一のコンテキストだから。
- **ユースケース束はアクセス時に組み立てる**: `PostgresUseCaseRegistry` はプロパティで初めて該当コンテキストの束を作り、同一スコープ内でキャッシュする。

## データマッピング & スキーマ整合性

- **1行1集約**: 集約は JSONB の `payload` 列を正とし、検索・一意性制約に必要な値だけを列へ複製する。読み込み時に列と payload の食い違いを検出して復元を拒否する。
- **列の導出は1度だけ書く**: 集約から検索列を導く処理は `app/infrastructure/postgres/repository_base.py` の `AggregateMapping.search_columns` にだけ置く。書き込み（`row_values`）も復元時の照合（`decode`）も同じ関数を使う。
- **集約の読み書きは基底経由に限る**: 読み取りは `PostgresRepositoryBase.find_one` / `find_all`、保存は `save_aggregate` を通す。行の世代（`version`）記録と `upsert` は非公開とし、Repositoryから直接呼べない。
- **列の食い違いを実行前に落とす**: `tests/infrastructure/postgres/test_schema_migration_consistency.py` が、マイグレーションのDDLとスキーマ定義DDLを比較し、Repositoryが書く列がテーブルに存在することをDBなしで検査する。

## トランザクション & 排他制御

- **保存は1文で原子的に**: 事前 `SELECT` で存在を確かめてから `INSERT` / `UPDATE` を分けない。`INSERT ... ON CONFLICT (id) DO UPDATE` の1文にする。
- **楽観ロック**: 全テーブルに `version` 列を置き、更新は「このトランザクションで読み込んだ世代」と一致する行だけに当てる。0行なら `ConcurrentModificationError` を送出する。世代追跡は `PostgresUnitOfWork` がトランザクション単位で保持する。
- **Unit of Work は必須依存**: 複数の集約を書くUseCaseは `UnitOfWork` を**必須の**コンストラクタ引数で受け取る。
- **commit 忘れを握り潰さない**: `PostgresUnitOfWork.__aexit__` は正常終了でも `rollback()` を呼ぶ。`close()` の暗黙のロールバックに任せない。
- **期間の重なりは排他制約で守る**: 「同一患者・同一順位で実効期間が重なる資格」「同一薬品コードで収載期間が重なる行」は `daterange` と `EXCLUDE USING gist` で表し、``btree_gist`` 拡張を使う。範囲の境界は終了日を含む**閉区間 `[]`** とする。
- **任意項目の一意性はNULLを除く**: 店舗コードなどの任意項目は部分一意インデックス（`WHERE ... IS NOT NULL`）にする。
- **無効化と一意性の向きは集約ごとに違う**: 外部患者IDは有効行だけを一意にし（`WHERE is_active`）、スタッフコードは無効化後も再利用させない（`is_active` で絞らない）。
- **`=` はNULLを等しいと扱わない**: NULLを含む組で同一性を表す場合は、非NULLのキー文字列（`identifier_key`）を別に持つ。
- **`AsyncSession` は使い回さない**: セッションは並行実行安全ではないので、Unit of Work とRepositoryは1リクエスト単位で組み立てる。
- **ドライバの挙動をダブルで代用しない**: 制約名は asyncpg 例外の `constraint_name` から取り出す。ダブルを推測で書かず、実物の確認は `tests/integration/` で行う。
