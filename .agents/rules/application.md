---
trigger: always_on
description: オニオンアーキテクチャ Application層の配置、Command/Query、公開契約、認可、保存前Guardの規則。
---

# Application層の開発ルール

Applicationは認可、ユースケースの進行、トランザクション内の操作、Domainの呼び出しと公開境界を所有する。標準ライブラリ・Domain・宣言されたApplicationの公開契約に依存し、FastAPI・SQLAlchemy・SDK・ファイル操作・実行基盤はInfrastructureへ分離する。

## 配置と操作の分離

各業務コンテキストはFeature-firstとCommand/Query分離を採用する。

```text
application/<context>/
  commands/<operation>.py          # 更新Handler・専用入力・結果
  commands/models.py               # 複数の更新操作・契約が共用する入力
  commands/dtos/<meaning>.py        # 更新側の共用結果
  commands/services/<task>.py       # 更新側の共有処理
  commands/policies/<policy>.py
  queries/<operation>.py           # 参照Handler・専用条件・結果
  queries/models.py                # Readerと共有する検索条件
  queries/dtos/<meaning>.py         # 参照側の共用投影
  queries/services/<task>.py
  queries/policies/<policy>.py
  interfaces/<capability>.py       # 利用側所有のProtocol
  interfaces/<subject>_query_reader.py
  boundary_models.py              # 公開境界の不変入力・認証結果・原本の値
  boundary_interfaces/<capability>.py # HTTPから利用する抽象認証契約
  values.py                       # 側に依存しない値・純粋な変換
  policies.py
  errors.py
```

必要な役割だけを置く。専用CommandとHandlerは同居させ、共有が必要な契約だけをmodelsへ出す。Handler/DTO/Serviceを汎用名の小ディレクトリへ細分化しない。Feature直下のmodels.py・dto.py・support.py・services.pyや再公開Facadeは残さない。commandsとqueriesのHandler・Reader・DTO・モデル・補助Serviceは相互にimportしない。中立のProtocolを挟んで反対側のモデルへ到達する経路も禁止する。

Handlerから他Handlerを直接importしない。再利用する操作は利用側が所有する能力Protocolまたは側ごとの共有Serviceへ依存させ、具象の接続はComposition Rootが行う。DTOや入力モデル、Protocolから具象Handlerへ逆依存しない。集約は外側へ返さず、明示的なDTO・ID・不変な境界値へ変換する。

## 読取と更新の契約

Queryは参照用Protocolを通して不変なDTO・参照モデルを受ける。Domain Repositoryを直接利用せず、QueryReaderへ保存・削除を持たせない。初期値を保存するカタログ確保はEnsureCategoryCatalogUseCaseという更新操作として区別する。単にGetという名前へ変えるだけで更新処理を参照側へ残さない。

QueryReaderの実装はInfrastructureに置く。既存Repositoryからの投影も許可し、SQLによる直接射影を必須にしない。Domainサービスの業務判定はApplicationのServiceへ閉じ込める。公開範囲・店舗権限・判定日などの判断はApplicationが決める。公開JSON・保存JSONはdataclasses.asdictを使わず、明示変換する。HTTP境界はCommand結果とQuery結果を既存のHTTP応答へ明示変換する。

更新の再送・冪等性は専用のCommand契約と結果で扱い、表示用QueryReaderやDTOを流用しない。

## コンテキスト依存と公開範囲

backend/application-architecture.tomlのdepends_onとpublic_modulesを両方満たす。宣言と実モジュールの循環は禁止する。未登録コンテキスト・非公開モジュールを追加して検査をすり抜けさせない。型専用・関数内・別名・package形式のimportも対象とする。絶対importを使い、wildcard・動的import・初期化子の再公開は禁止する。

業務コンテキストは原則独立とし、Staff→Storeの既存の許可方向を維持する。NSIPS取込は取込側所有の操作Protocolと公開入力・結果へ依存する。Store/Staff/Patient/Coverage/Reception/CareEventは法人の具象CorporateAccessServiceをimportせず、CorporateAccessBoundaryに依存する。

本プロジェクト固有の共通責務は次のように扱う。

- commonは時計・ページング・入力正規化・UoW・ロックなどの共通契約を所有し、標準ライブラリだけに依存する。FeatureやDomainの語彙を持ち込まない。
- access_controlは信頼済み操作者・権限と認可方針を所有し、個別Applicationコンテキストへ依存しない。
- composition/adaptersは利用側所有の境界を実装する横断変換・保存前Guardを所有する。検証材料の取得にDomain Repositoryを使用できる。ここへQueryReaderの具象永続化を置かない。
- composition/registryは操作を束ねる不変な登録情報、composition/runtimeは実行スコープProtocolと認証済み操作者からの開始境界を所有する。具象の資源生成はInfrastructureとbootstrapが行う。HTTPから使用する公開スコープは保持する。
- boundary_modelsは不変dataclassと列挙だけを置く。業務Serviceを隠さず、更新結果・参照投影の共有場所として使わない。boundary_interfacesには明示的なProtocolだけを置く。Presentationは内部Reader・共有Service・Policy・値の代わりに、公開UseCase・入出力・抽象認証契約・実行スコープを利用する。

## 認可とテナント境界

認証基盤が生成したActorContextと、操作対象のcorporate_idを分離する。ResolveActorUseCaseはReaderのget_by_subjectからアカウント・本人・所属の不変な参照事実を受け取り、停止状態・対応の整合を検証してResolvedActorContextを構築する。Readerへ有効性判定やロール付与を移さない。HTTP入力から信頼済み操作者を組み立てない。ベンダー管理者は全法人、法人管理者は自法人だけを操作できる。他テナントや未存在は404相当の例外へ畳み込み、参照BoundaryのRaisesに明記する。

無効法人の通常操作はCorporateAccessServiceで拒否し、法人状態変更はベンダー管理者専用とする。店舗ロールはApplicationの権限表とRepositoryReadScopeによるSQLの取得条件の両方で制限する。宣言の無いテーブルは読めない。取得後のフィルタだけで代替しない。

ユーザーの権限は一般ユーザー（店舗単位）・管理薬剤師（有効な任命の一店舗）・法人管理者（法人単位）として加算する。法人管理権限と店舗の利用範囲を分け、法人管理者に店舗利用権限を付与できる。管理薬剤師は自店舗を利用するユーザーの自店舗分だけを編集・停止・再開でき、複数店舗利用者や法人管理者も対象に含める。他店舗の付与内容、法人管理権限、法人アクセス権全体の状態、アカウント全体の状態は変更できない。有効な管理薬剤師本人の店舗権限は法人管理者が変更する。アカウント全体の停止はベンダーと自法人の法人管理者に限り、最後の有効管理者の保護と他法人の404隠蔽を維持する。管理権限は注入時計の業務日と確定任命から解決し、更新時も同じ法人ロック内で任命・本人・所属を再確認する。

Coverageは患者資格・有効性・適用組合せ・固定値・選択履歴、Receptionは外部受付原本・訂正履歴・監査判断を所有する。Receptionへ資格履歴Repositoryを移さない。到達可能なClaim操作が無い間はClaim権限を作らない。

## 保存前Guardと排他制御

本人未特定の更新は保存前のResolvedActorWriteGuardで拒否する。FastAPIのyield依存終了後や確定直前へ判定を遅らせない。招待受諾は専用UoWを使う。

本人特定・店舗状態・スタッフ任命の整合はCompositeWriteGuardへ順序付きで宣言し、UnitOfWork.before_saveへ接続する。検証と別集約への書込みを混在させず、書込みはユースケースの明示的な手順に置く。

Guardが別集約を読み直す場合は、その集約を書く側と同じOrganizationLockのキーを先に取得する。get()でロックせず、対象集約を保存するときに取得する。

## 入力・時計・テスト

業務日はcommon/clock.pyのbusiness_date(clock)、現在日時は注入時計から決める。任意項目の空文字はcommon/input_normalization.pyのto_optional_textでNoneへ正規化する。再エクスポートは作らず定義元からimportする。任意値の変換はcommon/optional_conversion.pyのunwrap・build_optionalへ寄せる。ページングはPage[T]を返す。

Domainモデルをモックしない。実オブジェクトとインメモリRepository、または明示的にProtocolを継承した読取フェイクを使う。全メンバを実装し、保存結果・認可拒否前にReaderが呼ばれないこと・公開情報・業務日を観測する。PostgreSQLの店舗取得条件は実DBテストで確認する。

## ハーネスと品質ゲート

backend/tools/check_application_architecture.pyがAPP000〜APP015をASTで検査する。構文、配置、相対/wildcard/import初期化、外層依存、役割方向、Handler依存、公開範囲、commonの独立、I/O、動的import、循環、Presentation境界、Command/Query分離、Repository参照を対象とする。個別違反の抑制・baselineは作らない。

ルートからpnpm --filter pharmacydomain-api run lint:applicationとlint:application:harnessで診断できる。通常のpnpm lint:backendでも両方を実行し、pytestも実ソース・合成例・CLIを検証する。通常ゲートは全規則を使う。imports/enforcedやfeatureを絞った診断の成功を、全規則適合と報告しない。

終了コードは適合0・違反1・設定/入力不正2。対象コードはimportせず、JSONの診断パスはリポジトリ相対、行番号は1始まりとする。AST検査は任意の実行時動作やDTOの意味を完全には証明しないため、業務・HTTP・実DBテストを併用する。
