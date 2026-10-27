# Repository agent rules

- Work on the existing main branch; preserve user changes and shared history.
- Never commit credentials, private keys, signing material or secret values.
- Keep application source, maintained documentation and public-site checks here.
- Keep and execute the named GitHub Actions workflows, reusable lanes, manual inputs and schedules in Pantry Core. Private repositories own source only; do not relocate execution into Workspace or restore a private request collector. Use configured secrets to read exact private source commits into a separate checkout from the public automation recipe. Never commit private application source, credentials, signing material or decrypted handoffs to public Git history or artifacts. Preserve canonical signatures, frozen Bootstrap anchors, provenance and publication leases.
- Preserve generated delivery records; only their authenticated publisher may replace them.
- Verify the relevant public-site checks before committing a change.

<!-- merged-from: CONTRIBUTING.md -->

## Merged from CONTRIBUTING.md

# コントリビュート

変更は小さく、テスト可能で、レビュー/ロールバックしやすく保ちます。このリポジトリでは現在のProject運用ルールに従い、既存`master`へ検証済みの変更を積みます。作業用branchを勝手に増やしません。

## セットアップ

```bash
npm ci
npm start
```

本番ビルド:

```bash
npm run build:prod
```

## 変更原則

- 無関係なUI、runtime、content、SDK vendor、生成bundleを同じ変更へ混ぜない。
- 既存変更を破壊的reset/forceで消さない。
- ref更新はfast-forwardを基本にする。
- Blogfa変更ではnative fallbackを維持する。
- 公開ルート変更時はnavigation、sitemap、canonical URLを確認する。
- SDK source変更時だけ必要な生成bundleを更新する。
- Project Rev固有の短縮/最適化を上流SDK Core/Frameworkへ押し込まない。
- browserへ秘密情報を置かない。
- 公開UIの新規テキストは原則日本語。

## Live2D変更

production経路:

```text
live2d-loader.js
  → live2d_bundle.js
  → live2d-runtime.js
       → waifu-tips.json / model/
```

旧`waifu-tips.js`のsource patch/eval経路をproductionへ戻しません。listener/timer/fetch/object URLを追加する場合はruntimeが所有し、`destroy()`で解放します。

## マージ/公開前ゲート

最低限:

```bash
npm run build:prod
npm run check:delivery
npm run check:runtime
npm run check:static
```

影響範囲に応じて:

```bash
npm run check:ja
npm run check:blogfa
npm run check:type
npm run check:vnext
npm run check:editorial
```

`check:runtime`には実ライフサイクルsmokeが含まれます。テストを無効化して通すのではなく、壊れた所有契約を修正してください。

## 手動確認

- 影響する静的ページをbrowserで確認。
- JavaScript console/network errorを確認。
- Blogfa/CDN失敗時にnative本文が残ることを確認。
- Live2D変更時はSDKv2/v4代表モデル、切替、disable/enable/resetを確認。
- mobile/reduced-motionを確認。

## 依存/toolchain

major更新はruntime refactorと混ぜません。lockfile、webpack、TypeScript、SDK互換性をまとめて検証できる独立変更にします。`npm audit fix --force`を無検証で実行しません。

<!-- merged-from: README.md -->

## Merged from README.md

# Project Rev / Live2D Web版

[![Project Rev Site](https://github.com/pvtkyron/pantry-core/actions/workflows/site.yml/badge.svg)](https://github.com/pvtkyron/pantry-core/actions/workflows/site.yml)

Project Revは静的ファーストのストア/編集サイトです。BlogfaとLive2Dは任意拡張として分離し、どちらが失敗しても主要コンテンツとナビゲーションを残します。

Live2DのSDK系譜は[`Konata09/Live2dOnWeb`](https://github.com/Konata09/Live2dOnWeb)に由来します。Project Rev固有のランタイム、検証、公開ルート、Blogfa連携、保守文書はこのリポジトリで管理します。

## 構成

- `index.html`, `shop.html`, `journal.html`, `about.html`, `faq.html` — 正規の静的ルート。
- `products/`, `posts/` — 製品と記事。
- `assets/rev-editorial-1.css`〜`6.css` — 保守用Editorial CSS。
- `assets/rev-editorial.css` — 6分割ソースから生成する単一配信CSS。
- `assets/live2d-loader.js` — 遅延起動、enable/disable/reset、SDK/runtimeロードを所有する薄いローダー。
- `assets/live2d-runtime.js` — モデル、ツール、tips JSON、listener/timer/fetch/object URLのライフサイクル所有者。
- `assets/blogfa-live2d-addon.js` — Blogfa固有のCDN固定、DOM/CSS、canvas健全性、fail-safe。
- `assets/blogfa-runtime-manifest.json` — Blogfa/runtime世代の単一バージョン源。
- `waifu-tips.json` — 本番tipsデータ。
- `waifu-tips.js` — 旧互換/上流系譜用。現在の本番ランタイムでは実行しません。
- `model/` — SDKv2/v4モデル、テクスチャ、モーション、音声。
- `src/SDKv2/`, `src/SDKv4/` — Live2D SDKソース。上流Core/Frameworkは理由なく短縮・整形しません。
- `dist/live2d_bundle.js` — 生成済みSDKブラウザバンドル。
- `scripts/` — ビルド、静的整合性、runtime contract、実ライフサイクルsmoke等。

## 開発と検証

```bash
npm ci
npm start
npm run build:prod
npm run check:delivery
npm run check:runtime
npm run check:static
npm run check:ja
npm run check:blogfa
npm run check:vnext
npm run check:editorial
```

`check:runtime`は2段です。

1. `check-live2d-runtime.js` — productionがcode-as-text/regex patchへ戻っていないこと、共有API、cleanup、Blogfa委譲等を静的検証。
2. `smoke-live2d-runtime.js` — fake DOM/SDK上で`mount → SDK2→SDK4 → destroy → mount`を実行し、listener/timerが重複しないことを検証。

`check:static`はHTMLの`href/src/poster/srcset`、サイトマップに加え、モデルJSONのpath-bearingフィールドからmoc/texture/motion/sound等の実ファイルを検証します。

## 本番Live2D経路

```text
assets/live2d-loader.js
  ├─ dist/live2d_bundle.js
  └─ assets/live2d-runtime.js
       ├─ waifu-tips.json
       └─ model/
```

通常ページとBlogfaで同じruntimeを使います。`waifu-tips.js`をfetch→regex→eval/Blob実行する経路は本番から除去済みです。

公開API:

- `REV_LIVE2D_LOAD()`
- `REV_LIVE2D_STATUS()`
- `REV_LIVE2D_RESET()`
- `REV_LIVE2D_DISABLE()`
- `REV_LIVE2D_ENABLE()`

自動起動は`saveData`、低速回線、モバイル、`prefers-reduced-motion`を尊重します。

## Blogfa本番経路

```text
blogfa-custom-html-snippet.html
  ├─ assets/blogfa-responsive.js
  ├─ assets/blogfa-supervisor.js
  └─ assets/blogfa-editorial.js
       └─ assets/blogfa-live2d-addon.js
            └─ assets/live2d-loader.js
```

`assets/blogfa-bootstrap.js`と旧widget入口は互換/履歴用です。production entryへ再混入しないことをCIで確認します。

## 配信とセキュリティ

`_headers`はnosniff、referrer/permissions policy、HSTS、cross-domain policy、cache/CORS境界を定義します。CSPは既存inline/外部依存との互換性を別途検証してから導入します。壊れる可能性のあるCSPを見栄えだけで追加しません。

本番依存はCIで`npm audit --omit=dev --audit-level=high`を実行します。古い開発toolchainのmajor更新は、SDK/webpack互換性とlockfileをまとめて検証できる独立変更として扱います。

## 文書

- [アーキテクチャ](docs/README.md#merged-from-architecture)
- [Blogfaランタイム](docs/README.md#merged-from-blogfa-runtime)
- [Live2D保守](docs/README.md#merged-from-live2d-maintenance)
- [デプロイ](docs/README.md#merged-from-deployment)
- [トラブルシューティング](docs/README.md#merged-from-troubleshooting)
- [セキュリティ](AGENTS.md#merged-from-securitymd)

<!-- merged-from: SECURITY.md -->

## Merged from SECURITY.md

# セキュリティポリシー

## 対象範囲

報告対象はProject Revの公開HTML、`assets/`ランタイム、Blogfa連携、生成済みLive2Dブラウザバンドルです。`src/SDKv2`、`src/SDKv4`、`model/`の第三者SDK/モデルには上流所有者とライセンスがあります。

## 脆弱性の報告

公開Issue/PRへ攻撃手法の詳細、秘密トークン、認証情報、機微データを投稿しないでください。非公開連絡では可能なら以下を含めます。

- 影響ファイル/ルート
- 最小再現手順
- 期待/実際の挙動
- browser/runtime version
- 影響評価
- 安全に共有できる最小例

## クライアント境界

このリポジトリは静的ファーストです。ブラウザへ届くHTML/JavaScript/設定は公開情報として扱います。

絶対にcommitしないもの:

- GitHub/API token
- private key
- session cookie
- payment credential
- production secret
- private-only endpoint credential

## Live2D実行境界

productionは`waifu-tips.js`をsource textとして取得・regex patch・eval/Blob実行しません。

```text
assets/live2d-loader.js
  → dist/live2d_bundle.js
  → assets/live2d-runtime.js
       → waifu-tips.json / model/
```

runtimeはlistener、timer、fetch AbortController、object URL、SDK状態を所有し、destroy時に解放します。新しい実行経路を追加する場合も同じ所有境界へ統合してください。

## 配信ヘッダー

`_headers`は以下を維持します。

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- restrictive `Permissions-Policy`
- HSTS
- `X-Permitted-Cross-Domain-Policies: none`
- asset/model cache/CORS境界

CSPは価値がありますが、現在のinline/remote依存を先に棚卸しし、動作確認を含む独立変更として導入します。互換性確認なしの厳格CSPは適用しません。

## 依存関係

CIで本番依存を`npm audit --omit=dev --audit-level=high`します。dev toolchainのmajor更新はbreaking changeを含み得るため、lockfile/webpack/TypeScript/SDK互換性をまとめて検証する独立作業にします。

`npm audit fix --force`を無検証で実行しません。

## 障害分離

セキュリティ修正でも静的本文、Blogfa native fallback、Live2D任意性を維持します。Live2D/CDN障害で本文を利用不能にしないでください。
