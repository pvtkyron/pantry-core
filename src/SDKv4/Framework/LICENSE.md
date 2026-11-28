## Definitions

### Live2D Cubism Components

Cubism Web Framework is included in Live2D Cubism Components.

Cubism Web Framework は Live2D Cubism Components に含まれます。


## Cubism SDK Release License

*All business* users must obtain a Cubism SDK Release License. "Business" means an entity with the annual gross revenue more than ten million (10,000,000) JPY for the most recent fiscal year.

* [Cubism SDK Release License](https://www.live2d.com/en/download/cubism-sdk/release-license/)

直近会計年度の売上高が 1000 万円以上の事業者様がご利用になる場合は、Cubism SDK リリースライセンス（出版許諾契約）に同意していただく必要がございます。

* [Cubism SDK リリースライセンス](https://www.live2d.com/ja/download/cubism-sdk/release-license/)


## Live2D Open Software License

Live2D Cubism Components is available under Live2D Open Software License.

* [Live2D Open Software License](https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html)
* [Live2D Open Software 使用許諾契約書](https://www.live2d.com/eula/live2d-open-software-license-agreement_jp.html)


## Live2D Proprietary Software License

Live2D Cubism Core is available under Live2D Proprietary Software License.

* [Live2D Proprietary Software License Agreement](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)
* [Live2D Proprietary Software 使用許諾契約書](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_jp.html)


---

Please contact us from [here](https://www.live2d.jp/contact/) for more license information.

<!-- merged-from: CHANGELOG.md -->

## Merged from CHANGELOG.md

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## [4-r.1] - 2020-01-30

### Added

* Add `.editorconfig`, `.gitattributes` and `.gitignore`.
* Add document `README.md` and `CHANGELOG.md`.
* Add `package.json` for development and build.
* Add Prettier and ESLint for format and check code quolity.

### Changed

* Move source files to `/src` directory.
* Reformat code using Prettier and ESLint.


[4-r.1]: https://github.com/Live2D/CubismWebFramework/compare/ce2585a919ac6e99f64dd468933772c6f1abbcc7...4-r.1

<!-- merged-from: README.md -->

## Merged from README.md

# Cubism Web Framework

Live2D Cubism 4 Editor で出力したモデルをアプリケーションで利用するためのフレームワークです。

モデルを表示、操作するための各種機能を提供します。
モデルをロードするには Live2D Cubism Core ライブラリと組み合わせて使用します。

ビルドを行うことで、ブラウザで利用可能な JavaScript ライブラリとして利用することができます。


## ライセンス

本 SDK を使用する前に、[ライセンス](LICENSE.md)をご確認ください。


## 開発環境

### Node.js

* 13.7.0
* 12.14.1
* 10.18.1

### TypeScript

3.7.5


## 開発環境構築

1. [Node.js] と [Visual Studio Code] をインストールします
1. Visual Studio Code で本プロジェクトを開き、推奨拡張機能をインストールします
    * 拡張機能タブから `@recommended` と入力することで確認できます
1. コマンドパレット（*View > Command Palette...*）で `>Tasks: Run Task` を入力してタスク一覧を表示します
1. `npm: install` を選択して依存パッケージのダウンロードを行います

コマンドパレットのタスク一覧から各種コマンドを実行することができます。

NOTE: デバック用の設定は、`.vscode/tasks.json` に記述しています。

## タスク一覧

### `npm: build`

ソースファイルのビルドを行い、`dist` ディレクトリに出力します。

`tsconfig.json` を編集することで設定内容を変更できます。

### `npm: test`

TypeScript の型チェックテストを行います。

`tsconfig.json` を編集することで設定内容を変更できます。

### `npm: lint`

`src` ディレクトリ内の TypeScript ファイルの静的解析を行います。

`.eslintrc.yml` を編集することで設定内容を変更できます。

### `npm: lint:fix`

`src` ディレクトリ内の TypeScript ファイルの静的解析及び自動修正を行います。

`.eslintrc.yml` を編集することで設定内容を変更できます。

### `npm: clean`

ビルド成果物ディレクトリ（`dist`）を削除します。


## コンポーネント

### effect

自動まばたきやリップシンクなど、モデルに対してモーション情報をエフェクト的に付加する機能を提供します。

### id

モデルに設定されたパラメータ名・パーツ名・Drawable名を独自の型で管理する機能を提供します。

### math

行列計算やベクトル計算など、モデルの操作や描画に必要な算術演算の機能を提供します。

### model

モデルを取り扱うための各種機能（生成、更新、破棄）を提供します。

### motion

モデルにモーションデータを適用するための各種機能（モーション再生、パラメータブレンド）を提供します。

### physics

モデルに物理演算による変形操作を適用するための機能を提供します。

### rendering

モデルを描画するためのグラフィックス命令を実装したレンダラを提供します。

### type

フレームワーク内で使用する型定義を提供します。

### utils

JSONパーサーやログ出力などのユーティリティ機能を提供します。


## Live2D Cubism Core for Web

当リポジトリには Cubism Core for Web は同梱されていません。

[Cubism SDK for Web] からダウンロードしてください。

[Cubism SDK for Web]: https://www.live2d.com/download/cubism-sdk/download-web/


## サンプル

標準的なアプリケーションの実装例は [CubismWebSamples] を参照ください。

[CubismWebSamples]: https://github.com/Live2D/CubismWebSamples


## マニュアル

[Cubism SDK Manual](https://docs.live2d.com/cubism-sdk-manual/top/)


## 変更履歴

当リポジトリの変更履歴については [CHANGELOG.md](LICENSE.md#merged-from-changelogmd) を参照ください。
