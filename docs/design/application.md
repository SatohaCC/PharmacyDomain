# Applicationの設計

Applicationは認可、入力変換、参照、Domainの呼出し、保存順序と公開境界を所有します。
業務不変条件は[Domain](domain.md)、DB・SDK等の具体的なI/Oは[Infrastructure](infrastructure.md)へ置きます。
配置・許可依存・公開範囲の現在形は`backend/application-architecture.toml`とコードを確認します。

## Command/Queryと公開契約

コンテキストごとに更新と参照を分け、専用入力・結果はHandlerと同居させます。
共有が必要な場合だけ同じ側のmodels・dtos・services・policiesへ切り出します。
CommandとQueryのHandler・Reader・DTO・モデル・補助処理は互いをimportせず、中立のProtocol経由で反対側の型を共有する経路も作りません。

QueryはDomain Repositoryへ直接依存せず、不変なDTO・参照モデルを返すQueryReaderを使います。
Readerへ保存・削除を公開せず、初期カタログ確保や再送・冪等性は更新契約へ分けます。
Readerの実装はInfrastructureへ置き、Repositoryからの投影も許可します。

Handlerから他Handlerを直接importせず、利用側所有の能力ProtocolとComposition Rootで接続します。
HTTPへ公開する不変入力・認証契約と、内部のReader・Service・Policyを区別します。
集約は用途別のDTO・ID・不変な境界値へ明示変換して返し、汎用asdictでJSONを作りません。

## コンテキスト間の接続

| 共通領域 | 責務 |
| --- | --- |
| common | 時計・入力正規化・ページング・UoW・ロックの契約。標準ライブラリだけに依存 |
| access_control | 操作者と認可方針。個別Applicationコンテキストへ依存しない |
| composition/adapters | 利用側Protocolの横断変換と保存前Guard。検証材料の取得にDomain Repositoryを使用できる |
| composition/registry・runtime | 不変の操作登録と実行スコープ。資源の具象生成はInfrastructure・bootstrapへ委譲 |

外部の事実は利用側所有の不変値へ変換し、不足情報を推測しません。Readerや変換アダプタへ業務判定・ロール付与を移しません。
QueryReaderの永続化をcompositionへ置かず、他コンテキストの具象UseCase・Repositoryへの直接依存も広げません。
法人有効性はCorporateAccessBoundary、NSIPS取込は取込側所有の操作Protocolへ接続します。
参照Boundaryには他法人・未存在をどのNotFound系例外へ畳むかを明記します。

## 認証・認可とテナント境界

認証基盤からの信頼済みActorと操作対象のcorporate_idを分離し、HTTP入力からActor・記録者を作りません。
外部主体からアカウントを検索し、本人・所属・停止状態をApplicationが検証して操作者を解決します。
本人・アカウント・法人アクセス権は別集約とし、外部主体を固定し、スタッフ本人リンクの付替えもDBで防ぎます。

ベンダーは全法人、法人管理者は自法人を操作できます。他法人と未存在は同じNotFound系応答へ畳みます。
通常操作は法人有効性を確認し、店舗利用はApplicationの認可とSQL取得範囲の両方で制限します。
宣言のないテーブル読取や、取得後のフィルタだけによる隔離は認めません。

店舗業務では選択済み店舗を使います。スタッフの選択候補は許可店舗と当日の有効所属の積集合です。
テストも店舗選択・所属を明示し、選択未完了と業務実行を区別します。

一般ユーザー・管理薬剤師・法人管理者の権限は加算し、法人管理と店舗利用を分けます。
管理薬剤師が変更できるのは自店舗分だけで、他店舗・法人権限全体・アカウント全体には広げません。
有効な管理薬剤師本人の店舗権限は法人管理者が変更し、アカウント全体の停止はベンダーと自法人の法人管理者に限ります。
最後の有効管理者を保護し、更新時にも同じ法人ロック内で任命・本人・所属を再確認します。

監査は運営者と本人・アカウントを区別し、ベンダー専用操作の履歴も運営者を表現できる型にします。
認証方式・初回利用の手順は[認証運用](../local-authentication.md)を参照します。

## 保存前Guardとトランザクション

複数集約を書くUseCaseはUnitOfWorkを必須依存とし、実行スコープが同じセッションの開始・成功時確定・失敗時rollbackを担当します。
本人未特定の更新は保存前に拒否し、HTTPのyield依存終了後まで判定を遅らせません。招待受諾には専用UoWを使います。

本人特定・店舗状態・任命整合を順序付きのCompositeWriteGuardとして保存前へ接続します。
Guardは検証を担当し、別集約への書込みはUseCaseの明示手順に置きます。
別集約を読み直す前に、その集約を書く側と同じOrganizationLockを取得します。getでロックせず保存時に取得し、競合後は読み直します。

原記録から投影を作る場合は原記録を先に保存し、同じUoWで投影を保存します。再構築可能性は原子性の代替ではありません。
記録時刻・業務日は注入時計から、任意文字列の空欄は共通の正規化でNoneへ、用量は文字列からDecimalへ変換します。
検証手順は[開発ガイド](../development.md)、HTTPへの変換は[HTTP境界](presentation.md)を参照します。
