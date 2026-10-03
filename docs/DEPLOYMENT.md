# デプロイガイド

## 公開面

Project Revには3つの公開経路があります。

1. 正規の静的サイト。
2. Cloudflare Workers Static Assets (`wrangler.jsonc`)。
3. GitHub/CDNアセットを利用するBlogfa連携。

Blogfa/Live2Dの失敗を正規静的サイトへ伝播させません。

## 公開前ゲート

```bash
npm ci
npm run build:prod
npm run check:delivery
npm run check:runtime
npm run check:static
npm run check:ja
npm run check:blogfa
npm run check:vnext
npm run check:editorial
```

Cloudflare:

```bash
npm run cf:dry-run
npm run cf:deploy
```

`build:prod`はproduction mode、minifyあり、source mapなしです。development buildはminifyなし/inline source mapありです。webpack configのmodeを再びhardcodeしないでください。

## Live2D公開経路

```text
assets/live2d-loader.js
  ├─ dist/live2d_bundle.js
  └─ assets/live2d-runtime.js
       ├─ waifu-tips.json
       └─ model/
```

旧`waifu-tips.js`はproduction asset chainではありません。公開時にcode-as-text patch経路を復活させないでください。

SDK source変更時:

1. `npm run build:prod`
2. `npm run check:delivery`
3. `npm run check:runtime`
4. `npm run check:static`
5. SDKv2/v4代表モデルを手動確認

runtime/glueだけの変更で上流SDK Core/Frameworkを無関係に整形しません。

## Editorial CSS

編集元は`assets/rev-editorial-1.css`〜`6.css`です。`npm run build:css`で`assets/rev-editorial.css`へ統合します。runtime versionはmanifestから取得します。

## 静的/SEO変更

- root深度に応じた相対asset pathを維持。
- ルート追加/削除/改名時は`sitemap.xml`とクロール可能リンクを同時更新。
- `404.html`の`noindex`を維持。
- `_headers`のsecurity/cache contractを維持。
- 秘密情報をHTML/JavaScriptへ置かない。

`check:static`はHTML/サイトマップ/Live2Dモデル参照を検証します。

## Blogfa変更

現在のproduction entryは`blogfa-custom-html-snippet.html`です。legacy bootstrap/widgetを本番へ戻さないでください。

確認:

- Blogfa placeholderを維持。
- native/safe経路を維持。
- CDN/GitHub取得失敗を試す。
- Shadowとnative CSS所有を混ぜない。
- addonが共通loader/runtimeを使う。
- Live2D失敗で本文を消さない。

## 配信ヘッダー

`_headers`で以下を維持します。

- `X-Content-Type-Options: nosniff`
- strict referrer policy
- permissions policy
- HSTS
- cross-domain policy
- `/assets`, `/dist`, `/model`のcache境界
- SDK/model配信用CORS

CSPは既存inline/remote依存を棚卸しした独立変更として導入します。検証なしに追加して本番を壊さないでください。

## 依存関係

CIは本番依存へ`npm audit --omit=dev --audit-level=high`を実行します。古いdev toolchainのmajor更新はwebpack/TypeScript/SDK互換性とlockfile更新を一緒に検証できる別変更にします。`npm audit fix --force`を公開前のついでに実行しません。

## ロールバック

原因となる最小commitを戻します。Blogfa障害時はnative面、Live2D障害時は本文を残し、障害境界より広いロールバックを避けます。
