---
name: infrastructure-layer
description: 永続化と外部アダプターの実装・復元・技術境界。
---

# Infrastructure

## 実装の責務

Application/Domainが所有するPortの具体実装、DB/外部API/SDK/ファイル形式との変換、資源管理を担う。業務判断をSQL/SDK mapperへ分散させず、必要なDomain操作の調整はApplicationへ置く。

- 保存形式とDomainを明示変換する。ORMモデル/Session/SDKレスポンスを内層の契約へ漏らさない。DBからの復元でもモデルの不変条件を守る。
- Repositoryは必要な集約の読書きを実装し、独断でcommitしない。flush/採番と確定は区別する。UoW/Publisherでの技術commitはApplication所有の契約に従う。[UoW](unit-of-work.md)
- 競合・一意制約・接続失敗を、合意したPort失敗へ変換する。Constraint違反を区別できないまま全て業務Validationにしない。
- 技術的な入力の解析と、その結果に対する業務判断を分ける。Domainサービスを起動配線から直接呼び出してusecaseを迂回しない。
- Factory/Session/Client等の寿命とcleanupは[DIP/DI](dependency-inversion-principle.md)に従い、ライブラリの共有安全性を確認する。

## アダプター間の独立性

対象の依存契約を確認し、相互importを増やす前に共通データ型/Port/変換の所有者を決める。Composition/CLIへの逆依存や、共有mapperから特定アダプターへの依存を作らない。

以下はXML/索引等を持つ厳格な構成の例で、他プロジェクトに同名モジュールを要求しない。

- 外部API/分類/解析/入力形式のアダプター間を独立させる。
- definition_loaderが正本の設定を所有し、各アダプターが参照する。loaderからアダプターへ依存させない。
- persistenceからsourcesへ依存させず、共通payload mapperを入力形式アダプターに閉じ込めない。
- PublicationRuntime/RegistrationPublisherがdecode/encodeを要するならSourceDecoder/ArtifactEncoder等のPortを注入する。

これらを採用したプロジェクトでは静的契約を守り、移動・再公開・ignore追加で迂回しない。新しい構成では必要な責務と依存から最小限に決める。

## 検証

Repository/Query/Publisherの契約をアダプター差替えでも確認する。Fakeのテストに加え、DBの制約/競合/rollback、外部通信/復旧、原本の往復変換等を必要な実環境で検証する。異なるDB製品やFakeの成功を、本番DB固有の振る舞いの成功に置き換えない。
