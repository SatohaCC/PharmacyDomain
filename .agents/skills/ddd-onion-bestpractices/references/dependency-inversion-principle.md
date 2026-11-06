---
name: dependency-inversion-principle
description: Port所有権、Composition Root、FastAPI DI、資源の寿命。
---

# DIP / DI

## 依存の逆転と配線

利用側のDomain/Applicationが必要な抽象を定義し、Infrastructureが実装する。実行時に外側を呼ぶことと、内側が具象をimportすることは別。Protocol採用だけでは、引数/戻り値にORM/SDK型が漏れる結合は解消しない。

```text
Presentation -> Application -> Domain
Infrastructure -> Application/DomainのPort
Composition Root -> 全層を組み立てる（内層から参照しない）
```

Composition Rootは構築と資源管理を行う。業務判断やusecaseの手順をここで実行しない。main/create_appを薄く保つか、配線をどのファイルへ置くかは対象の起動構成に合わせる。

## グラフの寿命と状態の寿命を分ける

| 対象 | 共有の判断と所有者 |
|---|---|
| Engine/pool、SDK client、immutable設定 | ライブラリの共有安全性を確認し、通常はアプリ起動時に生成・終了時に解放 |
| session/UoW/transaction、リクエスト固有の認可状態 | 操作/リクエスト単位。並行処理間で共有しない |
| Repository/Application Service | 型名で寿命を決めない。保持する可変状態の寿命に合わせる。factoryだけを持つ共有可能なserviceも、sessionを捕捉して共有不可のserviceもある |
| 背景処理/stream/並行子task | 使う期間を明示し、元リクエストの終了済み資源を再利用しない |

SQLAlchemy AsyncSessionは並行taskごとに分ける。requestが一つでも、その中で並行実行するなら同一Sessionを無条件に共有しない。[公式仕様](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)

取得直後からcleanup所有者を定め、通常終了・途中の構築失敗・例外・キャンセルをfinally/context manager等で扱う。ひとつのclose失敗で他資源の解放が飛ばないようにし、失敗を握りつぶして成功にしない。rollback/closeとcommit成功は別の契約。

## FastAPIでの二段階DI

- **起動時**: lifespan/compositionで共有可能な資源とfactoryを組み立てる。app.stateへ置くのは外側へ公開するApplication契約/依存解決用の参照。全Repository/Service/Sessionを一律singletonにする指示ではない。
- **操作時**: Applicationに定義したUoW/handler factory等の契約を通じて必要なスコープを作る。配線は外側に置き、ApplicationへSession型を持ち込まない。
- **request provider**: 採用したPresentation契約の範囲でdependencies.py等からapp.stateのApplication向け契約を取り出す。PresentationがInfrastructureをimportできない場合、Session/具象Repositoryをproviderで直接作らず、Rootで配線したfactory/handlerへ委譲する。
- **テスト**: Dependsの差替えとPort/Fakeを使い、通常・例外・並行操作のスコープを確認する。app.state利用それ自体を境界違反としない。

`yield`依存のcleanup時点、StreamingResponse、BackgroundTasks、scope引数の扱いはFastAPIの版と使用期間に依存する。installed/pinned versionと[公式dependency仕様](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)を確認して提案する。返却後のcleanupにcommitを隠し、確定前の成功応答を作らない。必要ならusecase確定と応答/streamの契約を分ける。

## レビューの判定

importだけでなく「誰が作り、何を捕捉し、誰と共有し、誰が閉じるか」を追う。具体的な状態捕捉/制御フローから問題を示し、未提示のtransaction実装やHTTP mappingを推測で欠陥扱いしない。Fakeで別インスタンスを確認しても実DBの分離性やライブラリの安全性を証明したとは報告しない。

原典: [Palermo Onion](https://jeffreypalermo.com/2008/07/the-onion-architecture-part-1/)、[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)。このSkillのPresentation依存制限は採用する厳格プロファイルであり、全Onion実装共通の唯一の配置規約ではない。
