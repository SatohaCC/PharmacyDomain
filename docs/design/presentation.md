# HTTP境界

PresentationはApplicationの公開入力・結果・実行Protocolへ接続し、Domain・Infrastructureを直接参照しません。
業務判断と認可は[Application](application.md)、具象生成は[DI・bootstrap](infrastructure.md)が所有します。

## ルートと認証窓口

ルータ単位で認証依存を掛け、Bearer認証をOpenAPIへ公開します。HTTP入力からActorやロールを作りません。
未接続の認証窓口は401へ倒します。UseCaseが検証できないIDをURLへ追加せず、公開操作のルート漏れはテストで検査します。

本番と固定トークンを使う開発起動点を分けます。アプリ生成時のモジュール読込でDBへ触らず、エンジンはlifespanで生成します。
HTTP依存はApplicationの実行スコープを使い、ルータからcommit・rollbackを呼びません。認証方式の運用は[認証ガイド](../local-authentication.md)を参照します。

## 入出力と失敗応答

業務失敗の分類はApplication、HTTPステータス・本文・OpenAPIへの変換はPresentationが所有します。
認証・入力検証も共通のcode・message・errorsへ揃え、未知例外を業務エラーとして握り潰しません。
共通のApplicationRouteとエラー定義を使い、各ルータでDomain例外を個別に捕捉しません。
依存解決中の失敗も同じ変換境界で扱い、書込みルートは楽観ロック衝突の409をOpenAPIへ記載します。

本文は未知項目を拒否するRequestModelを使います。入れ子の入力はApplicationが公開するInput型を再利用し、
応答はHTTP向けの素の型へ明示変換します。内部のDomain型を別名で隠して公開しません。
退職と再有効化のように意味が非対称な操作は、真偽値にまとめず別の操作として表します。
