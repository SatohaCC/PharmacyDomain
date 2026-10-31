# Domainファイル命名統一の計画・テスト仕様

作成日: 2026-10-18

計画・テスト仕様とも承認済み。2026-10-18に移行と検証を完了。

## 目的と範囲

medi-chatのDomainと指定スキルの推奨構造に合わせ、12業務コンテキストをidentifiers・exceptions・primitives・value_objects・entities・repositories・servicesの役割別モジュールへ整理する。必要のない役割の空ファイルは作らない。

集約境界、クラス名、公開操作、業務判断、保存JSON、HTTP契約は維持する。foundation/sharedは業務コンテキスト用の7モジュール規則の対象外とする。Application・Infrastructure・Presentationは参照更新のみとし、それ自体の命名変更は別段階とする。

## 移行単位

全コンテキストのrepository.pyをrepositories.pyへ改名する。storeのmanager_repository.pyも同じ役割へ統合する。

| コンテキスト | Entity・集約の主な移動元 | その他の整理 |
| --- | --- | --- |
| corporate | corporate.py | search.pyを定義の役割で配置 |
| medicine_catalog | medicine.py | 既存の役割別モジュールを維持 |
| reception | reception.py | 内部の値とEntityの依存を確認 |
| staff | staff.py | store_source.pyの参照値をvalue_objects.pyへ |
| care_event | event.py、event_definition.py | 内部の値とEntityの依存を確認 |
| store | store.py、manager_assignment.py | manager_service.pyをservices.pyへ。business_hours.py・lifecycle.py・manager_source.pyを定義の役割で分配 |
| patient | patient.py、external_identifier.py | merge_service.pyをservices.pyへ。heading.py・lifecycle.py・profile_history.pyを定義の役割で分配 |
| coverage | patient_coverage.py、coverage_selection_record.py | combination.py・coverage_selection.py・coverage_snapshot.pyのVOをvalue_objects.pyへ。priority_rules.pyの定義も分類 |
| identity | account_person.py、user_account.py、membership.py、invitation.py、staff_person_link.py | administrator_service.pyをservices.pyへ。混在するEnum・値は役割別に配置 |
| prescription | prescription.py | dosage.py・interaction_audit.py・reference_primitives.py・reference_values.pyを定義の役割で分配 |
| dispensing | dispensing_process.py | prescription_source.py・reference_primitives.py・reference_values.pyを定義の役割で分配 |
| medication_history | medication_history_record.py、patient_medical_profile.py、category_catalog.py、既存entities.py | fact_correction.py・dispensing_source.py・reference_primitives.pyを定義の役割で分配 |

これはファイル単位の対応表であり、混在モジュール全体を一括移動しない。各移行直前にクラス・関数・定数と依存を分類する。Protocolは保存・検索抽象と外部情報取得抽象を区別し、後者を保存Repositoryへ意味変更しない。Entityが必要とする純粋関数は上位のservices.pyへ動かして逆依存を生まないよう、所有する値・Entityとの配置を判断する。

薬歴など統合後に大きくなる箇所は、責務と依存方向を優先する。標準構造を外れる分割が必要なら、理由と配置を実装前に計画へ追記する。集約の分割・統合という業務設計変更は行わない。

## テスト仕様

| 観点 | 検証内容 | 実装方針 |
| --- | --- | --- |
| 命名の統一 | 12コンテキストに役割不明のモジュール、旧repository.py、不要な内部ディレクトリが残らない | 役割検査を拡張。コンテキストは実ディレクトリから列挙し、新設時の検査漏れを防ぐ |
| 検査の有効性 | 仮のコンテキストへ旧命名や未登録のモジュールを置くと失敗し、必要な標準モジュールだけなら成功する | 一時ディレクトリで違反注入。実ソースは汚さない |
| 定義の責務 | primitivesに複合値、value_objectsにEntityを置けない | 既存のモデル役割検査を維持・拡張。代表的な違反と正常例を確認 |
| 内部依存 | Primitive→Entity、VO→Repository、Entity→Serviceの逆依存を拒否する | 実Import Linterを使う既存の違反注入テストを移行後の名前へ更新 |
| 許可依存 | Entity→VO、Repository→Entity、Service→Repositoryを許可する | 同じ検査で正常例も実行し、全面禁止による偽の成功を防ぐ |
| 越境依存 | 他コンテキストのEntity・VO・Repository・Serviceは禁止し、公開ID参照は許可する | 既存のコンテキスト境界・公開ID検査を新パスへ更新 |
| 契約の網羅性 | 新しいモジュール名が依存契約から漏れない | 既存の契約網羅性テストを更新。as_packagesは対象が単一モジュールかパッケージかで判断し、違反注入で検出を確認 |
| import循環 | 先行importのないPython processでも移行後の具象モジュールを読み込める | 既存cold startテストを拡張。空のパッケージ初期化子のimportだけで成功扱いにしない |
| 振る舞い維持 | 既存のDomain・UseCase・Fake・HTTP・永続化契約が保たれる | 既存テストのimportを更新して再実行。業務テストの期待値を命名変更に合わせて緩めない |
| 保存互換性 | JSON変換・復元、実DBの保存と取得が維持される | 既存codec・Repository・実PostgreSQL結合テストで確認 |
| パッケージ | 初期化子の再公開・実行文がない | 既存package layoutテストを使用 |

テスト名・docstring・エラーメッセージは日本語。通常テストからこの文書やスキルのパスを参照しない。

## 実施と検証

1. 移行前に既存の関連テストと静的検査を実行し、既存失敗と変更による失敗を区別する。
2. 命名・責務・依存の検査を先行させ、違反例が失敗することを確認する。
3. Repository名、比較的小さいコンテキスト、複数集約のコンテキストの順で移行する。各単位で利用側importと検査設定を同時更新する。
4. 各単位のDomain・関連Application・Infrastructureテストと依存検査を実行する。
5. 最後にルートからpnpm test:backend、pnpm typecheck:backend、pnpm lint:backend、pnpm format:check、pnpm importsを実行する。
6. ルート.envのPOSTGRES_PORTを明示読込し、専用DBでpnpm test:integrationを実行する。未実行・スキップは合格扱いにしない。
7. 旧import・旧モジュール・再公開Facadeの残存を確認する。現行ルール文書の配置説明を更新し、過去のdocs/reportsは変更しない。
8. graphify update .でグラフを更新し、新パスの存在、旧パスの消失、エッジ終端の整合を確認する。

新しい品質ゲートのコマンドは追加せず、既存pytestの検査を拡張する。frontend/.tanstack/の既存未追跡ファイルは本作業に含めない。

## 実施結果（2026-10-18）

12業務コンテキストを81の役割別モジュールへ統一し、標準外だった60モジュールを削除した。混在していた定義は個別に配置し、集約の境界とクラス名は維持した。薬歴も直下の標準構造で移行でき、例外的な分割は追加していない。

MedicationHistoryExternalCorrectionMatchはEntityを含む検索結果なのでrepositoriesへ配置した。処方の連番検証関数はVOとEntityの双方が使うためprimitivesへ置いた。Coverageで別ファイルに重複していた同一内容の定数は一つへまとめ、店舗の旧ファイル用__all__は削除した。

移動前に採取したASTとの比較では、665件のクラス・関数・定数定義の本文が一致し、削除した定義は上記__all__だけだった。Domain以外の本番・ツールコード164ファイルも、importを除くASTが一致した。

| 検証 | 結果 |
| --- | --- |
| 先行した命名検査 | 移行前は本番配置の1件が期待どおり失敗、違反注入と正常例の5件は成功 |
| 全バックエンドテスト | 3362 passed、204 skipped、1 warning |
| 全体実行の収集後に追加したケースを含む命名・役割・依存契約テスト | 56 passed |
| 実PostgreSQL結合テスト | 204 passed、3367 deselected、1 warning |
| mypy strict | 738ファイル、問題なし |
| Ruff / format | 成功 |
| Import Linter | 18 kept、0 broken |
| 差分の空白検査・旧Domain import検索 | 問題なし |
| Graphify | 81標準モジュールを収録、削除した60パスの残存なし、12408ノード・44478エッジ、終端欠落0 |

全体実行のスキップはDB未設定等によるものであり、DB検証は別途上記の結合テストで実施した。結合テストはルート.envのPOSTGRES_PORT（5432）を明示読込し、新規の一時DBだけで実行した。終了後に一時DBを削除し、この検証のために起動したPostgreSQLコンテナも停止した。

制限環境での全体テストは非同期処理で進まなくなったため中断し、制限外で全体・実DBテストを実行した。移行前テストの完走結果は得られていない。uvキャッシュとpytest一時領域は作業領域へ切り替えた。警告はStarlette TestClientの非推奨通知。Graphify更新時には既存の概念ノード2件のsource_file欠落とコミュニティ名の再割当通知があったが、移行対象のソースパスと全エッジ終端の検証は成功した。
