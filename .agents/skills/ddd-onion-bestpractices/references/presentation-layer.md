---
name: presentation-layer
description: 公開DTO、境界変換、Application委譲と公開失敗契約。
---

# Presentation

REST/WS/CLI等の外部形式を受け取り、Applicationへ委譲して公開結果へ変換する。業務のオーケストレーション、Domain操作、DB資源の構築は持たない。

## 厳格な依存境界

Applicationと外側のWeb技術/必要なConfigを参照し、Domain/Infrastructureは直接importしない。Domain例外はApplication側で意味を保つ公開失敗へ変換する。具体的HTTP statusはPresentation/global handlerの契約で決める。

この完全禁止を採用しているプロジェクトでは例外を追加しない。他プロジェクトの明示された許可範囲を見ずに同じグラフへ改修することもしない。内部構成が異なるだけの適合コードを欠陥扱いしない。

## Pydanticと変換

- DTOは公開JSON等の構造・型・必須・件数と、境界に必要な入力規則を検証する。型だけの確認に限定しない。
- 業務形式・値域の正本はDomain Primitive。DTOに同じ正規表現や業務validatorを複製しない。Domainの不変条件は別途モデル自身が守る。
- 厳格な既定ではDTOのフィールド/validatorからDomain型を参照しない。公開値 → Application入力 → Primitive/VO、Application結果 → DTOを明示的に変換する。
- DTOをDomain/Application/ORMと兼用せず、暗黙変換に業務判断や欠損補完を隠さない。
- 公開出力は項目を明示してmapperで組み立て、内部フィールドをdataclasses.asdict等で無差別に公開しない。対象でそのAPIをlint禁止している場合は同じ規約に従う。
- 不在/空/未取得、IDの表現、コレクションの順序、日時/金額等の単位を公開契約として定める。原文を出力の都合で書き換えない。

## 依存解決と配置

DI providerは[DIP/DI](dependency-inversion-principle.md)の寿命・公開Portに従う。app.stateからApplication契約を取り出すことと、routeが具象Session/Repositoryを構築することを区別する。

`routes -> dependencies -> adapter service -> dto mappers -> dto models`の階層を採用しているプロジェクトでは守る。他の構成に常に5層を新設せず、DTO adapterとApplication Serviceに同じ業務フローを重ねない。

## エラーと検証

Applicationの失敗分類を公開契約へ対応させる。ドメイン違反/競合/認可失敗/技術障害を、catch-allの成功レスポンスへ変換しない。mappingが未提示なら既存global handlerを確認するまでHTTP不具合と断定しない。

検証は入力不正・明示変換・期待するApplication呼出し・公開項目・失敗mappingと、必要なHTTP/WS/FW動作を分ける。認証や入力補助はDomainの業務ルールや集約の整合性を代替しない。
