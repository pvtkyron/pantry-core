# Pantry Core documentation

## Contents

- [Project Rev architecture](#merged-from-architecture)
- [Blogfa runtime](#merged-from-blogfa-runtime)
- [Deployment](#merged-from-deployment)
- [Live2D maintenance](#merged-from-live2d-maintenance)
- [Troubleshooting](#merged-from-troubleshooting)

<!-- merged-from: ARCHITECTURE.md -->

## Merged from architecture

# Project Rev アーキテクチャ

## 基本原則

静的HTMLを最優先にし、ストアUI、Blogfa、Live2Dを段階的な拡張として重ねます。拡張の失敗を本文へ伝播させません。

```text
公開HTML
  ├─ Editorial / store
  └─ assets/live2d-loader.js
       ├─ dist/live2d_bundle.js
       └─ assets/live2d-runtime.js
            ├─ waifu-tips.json
            └─ model/

Blogfa
  └─ blogfa-custom-html-snippet.html
       ├─ assets/blogfa-responsive.js
       ├─ assets/blogfa-supervisor.js
       └─ assets/blogfa-editorial.js
            └─ assets/blogfa-live2d-addon.js
                 └─ assets/live2d-loader.js
```

## Live2Dの責務分離

### `assets/live2d-loader.js`

薄い起動層です。

- `saveData`、低速回線、モバイル、reduced-motionを考慮した遅延起動。
- SDK bundleとruntimeの外部scriptロード。
- `LOAD/STATUS/RESET/DISABLE/ENABLE`公開API。
- timeout/fail-safe。

### `assets/live2d-runtime.js`

実行状態の単一所有者です。

- SDKv2/v4モデルのロード/切替/release。
- toolbarとkeyboard accessibility。
- `waifu-tips.json`の取得とtips binding。
- listener/timer/fetch/object URLの追跡とcleanup。
- `destroy → mount`可能な再入可能ライフサイクル。

旧`waifu-tips.js`は互換/系譜用に残しますが、本番でsource fetch、regex patch、inline/Blob evalしません。

## SDK境界

`src/SDKv2/`と`src/SDKv4/`は世代境界を維持します。特にCore/Frameworkなど上流領域をProject Revの見た目上の短縮だけで改変しません。最適化はまずloader/runtime/build境界へ置きます。

## Blogfa境界

- `blogfa-responsive.js` — native viewport/responsive補助。
- `blogfa-supervisor.js` — 起動状態、復旧、fallback。
- `blogfa-editorial.js` / widget — Project Rev/Shadow表示の所有者。
- `blogfa-live2d-addon.js` — Blogfa固有のCDN固定、DOM/CSS、canvas health、cleanup。

responsive層からShadow DOMへ直接styleを注入しません。Shadow内部はwidget/editorial側が所有します。

`assets/blogfa-bootstrap.js`と旧widgetは互換/履歴用で、現在のproduction entryではありません。

## バージョン/生成物

`assets/blogfa-runtime-manifest.json`の`version`をruntime世代のsource of truthにします。Editorial CSSの生成/check側はここからversionを読みます。

`assets/rev-editorial.css`は6分割CSSから生成します。`dist/live2d_bundle.js`はSDK source変更時に生成する成果物です。無関係な文言変更でbundleを再生成しません。

## 検証レイヤー

- `check:static` — HTML、srcset、sitemap、モデル実参照。
- `check:runtime` — production runtime契約 + Node VMライフサイクルsmoke。
- `check:delivery` — bundle budget、webpack mode、headers、Wrangler、生成物。
- `check:blogfa` — responsive/Shadow/runtime generation。
- `check:vnext` — 軽量化とproduction pathの回帰防止。
- `check:editorial` — 統合CSSとEditorial/Blogfa表示契約。

ライフサイクルsmokeはSDK2→SDK4切替、destroy、再mount後にlistener/timerが重複しないことを実行検証します。

## 障害境界

```text
静的本文      → 常に残す
Store/UI      → 失敗しても本文を残す
Blogfa拡張    → 失敗時はnative本文へ
Live2D        → 失敗時はマスコットだけ停止
```

retryを全層へ足さず、最初に壊れた所有境界を修正します。

## セキュリティ/配信

ブラウザへ届く場所へ秘密情報を置きません。`_headers`で基本security/cache policyを維持し、CSPはinline/外部依存を棚卸しした独立変更として導入します。

webpackはCLIの`--mode`を正規入力とし、developmentはsource mapあり/minifyなし、productionはsource mapなし/minifyありです。toolchain major更新はruntime refactorと混ぜません。

<!-- merged-from: BLOGFA_RUNTIME.md -->

## Merged from Blogfa runtime

# Blogfa ランタイム契約

## 目的

Blogfaネイティブ面を基本可用性として残し、Project RevとLive2Dを任意拡張として重ねます。不健全な拡張が健全な本文を消してはいけません。

## 本番入口

```text
blogfa-custom-html-snippet.html
  ├─ assets/blogfa-responsive.js
  ├─ assets/blogfa-supervisor.js
  └─ assets/blogfa-editorial.js
       └─ assets/blogfa-live2d-addon.js
            └─ assets/live2d-loader.js
                 ├─ dist/live2d_bundle.js
                 └─ assets/live2d-runtime.js
```

`assets/blogfa-bootstrap.js`、`assets/blogfa-widget.js`、`assets/blogfa-widget-v2.js`は互換/履歴経路です。現在のproduction entryへ戻さないことをCIで確認します。

## 責務

- `blogfa-responsive.js` — viewport、safe-area、native側responsive。
- `blogfa-supervisor.js` — health、復旧上限、fallback。
- `blogfa-editorial.js` / v3 widget — Project Rev/Shadow表示。
- `blogfa-live2d-addon.js` — commit SHA固定、CDN fallback、Live2D DOM/CSS、canvas可視性、fail-safe cleanup。
- `live2d-loader.js` — 共通起動/lifecycle API。
- `live2d-runtime.js` — SDK/UI/tips/cleanupの単一所有者。
- `blogfa-runtime-manifest.json` — runtime世代のsource of truth。

## Shadow DOM所有

responsive層からShadow DOMへ直接CSSを注入しません。Shadow内部はwidget/editorial側が所有します。これにより二重style、古いbootstrap、native CSSとの競合を避けます。

## Live2D addon契約

Blogfa addonが所有するのはBlogfa固有の境界だけです。

1. store health待機。
2. GitHub commit SHA解決とCDN固定。
3. `assets/waifu.css`取得。
4. Live2D DOM/tool生成。
5. `window.__REV_LIVE2D_CONFIG__`設定。
6. `assets/live2d-loader.js`起動。
7. canvas可視性確認。
8. 失敗時cleanup。

addonは`waifu-tips.js`を取得/regex patch/inline実行しません。通常ページと同じ`assets/live2d-runtime.js`へ委譲します。

toolbarは生成時点からkeyboard操作とARIAを持ちます。hidden toolには不要なfocus/listenerを付与しません。

## プレースホルダー

`<-BlogUrl->`、`<-BlogTitle->`、`<-PostLink->`等はBlogfa runtime tokenです。ローカルファイルとして静的検証しません。

## デバイス契約

主要境界:

| 条件 | 目的 |
|---|---|
| `≤1180px` | 小型desktop/notebook |
| `≤900px` | tablet / 1カラム化 |
| `≤680px` | smartphone |
| `≤460px` | 小型smartphone |
| `≤360px` | 最終安全域 |
| 低いlandscape | 本文優先 |
| `pointer:coarse` | 実タッチ領域 |
| `prefers-reduced-motion` | 不要motion停止 |
| `print` | 補助UI除外 |

viewportは`width=device-width,initial-scale=1,viewport-fit=cover,interactive-widget=resizes-content`を維持します。

## 障害分離

```text
CDN/GitHub失敗       → native/Project Rev本文を維持
Project Rev health NG → native Blogfaへfallback
Live2D timeout/404    → Live2Dだけcleanup
canvas不可視          → Live2Dだけfailed-safe
```

再読み込み無限ループを作りません。全部へretryを追加せず、最初に失敗した所有境界を直します。

## runtime version

`assets/blogfa-runtime-manifest.json`の`version`を単一source of truthとして扱います。build/checkへ同じversion literalを複製しません。

## 検証

```bash
npm run check:runtime
npm run check:static
npm run check:blogfa
npm run check:editorial
```

`check:runtime`はproduction pathの静的契約だけでなく、destroy/re-mountの実行smokeも含みます。

デバッグ時:

```text
REV_SYSTEM_HEALTH()
REV_LIVE2D_HEALTH()
REV_LIVE2D_STATUS()
REV_RESPONSIVE_REFRESH()
```

## セキュリティ

ブラウザへ届くテンプレート/JavaScriptへGitHub token、cookie、秘密API key、非公開認証情報を埋め込みません。公開クライアントデータは公開情報として扱います。

<!-- merged-from: DEPLOYMENT.md -->

## Merged from deployment

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

<!-- merged-from: LIVE2D_MAINTENANCE.md -->

## Merged from Live2D maintenance

# Live2D 保守ガイド

## 現在の本番構成

```text
assets/live2d-loader.js
  ├─ dist/live2d_bundle.js
  └─ assets/live2d-runtime.js
       ├─ waifu-tips.json
       └─ model/
```

- `src/SDKv2/` — SDKv2ランタイム。
- `src/SDKv4/` — SDKv4ランタイム/Framework。
- `model/` — moc、texture、motion、physics、pose、sound等。
- `dist/live2d_bundle.js` — SDK生成物。
- `assets/live2d-loader.js` — 遅延起動と公開ライフサイクルAPI。
- `assets/live2d-runtime.js` — モデル/UI/tips/cleanupの状態所有者。
- `waifu-tips.json` — 本番tipsデータ。
- `waifu-tips.js` — 旧互換/上流系譜。現在のproduction runtimeでは実行しません。

## 本番runtime契約

`assets/live2d-loader.js`以外へbundle/runtime起動を複製しません。設定は`window.__REV_LIVE2D_CONFIG__`へ渡します。

公開API:

```text
REV_LIVE2D_LOAD()
REV_LIVE2D_STATUS()
REV_LIVE2D_RESET()
REV_LIVE2D_DISABLE()
REV_LIVE2D_ENABLE()
```

`assets/live2d-runtime.js`は次を所有します。

- SDKv2/v4 load/change/release。
- toolbar click/keyboard listener。
- tips JSONのfetchとDOM binding。
- timeout/interval。
- AbortController。
- screenshot Object URL。
- `destroy()`による全所有資源の解放。

再mount前は必ず`destroy()`が走るため、listener/timerを重複させません。

## 旧tips JSとの境界

以前のproductionは`waifu-tips.js`をテキスト取得し、regex patchして実行する設計でした。現在は廃止しています。

本番loader/runtimeへ以下を戻さないでください。

- `fetch('...waifu-tips.js')`してsource文字列を実行。
- export除去用regex。
- `new Blob([patchedCode])`によるcode-as-text実行。
- Blogfa専用の別tips patcher。

旧`waifu-tips.js`を変更する必要がある場合は、互換用途なのかproduction機能なのかを先に分けてください。新しいproduction機能は可能な限り`live2d-runtime.js`またはtips JSONへ置きます。

## モデル変更

SDK世代を確認してから変更します。SDKv2とSDKv4のモデル形式は互換ではありません。

同時に確認するもの:

- moc/moc3
- textures
- motions / expressions
- physics / pose / display info
- sounds

`npm run check:static`はモデルJSONのpath-bearingフィールドだけを辿ります。`Name`/`Id`等の表示メタデータをパスとして誤判定しません。

## ビルド

SDK sourceを変えた場合:

```bash
npm run build:prod
npm run check:delivery
npm run check:runtime
npm run check:static
```

production bundleは600KB budget内に保ちます。`.br`/`.gz`を生成物としてcommitせず、転送圧縮はhosting/CDNへ任せます。

webpackのmode契約:

- development: minifyなし、inline source mapあり。
- production: minifyあり、source mapなし。

## ライフサイクル検証

```bash
npm run check:runtime
```

静的contract checkに加えて`smoke-live2d-runtime.js`がfake DOM/SDK上で実際に以下を行います。

```text
mount SDK2
→ SDK4へ切替
→ destroy
→ listener/timer = 0
→ 再mount
→ listener数が増殖しない
→ destroy
```

runtime cleanupを変更する場合、このsmokeを弱めず挙動を修正してください。

## パフォーマンス

- 本文をLive2Dのロード待ちにしない。
- saveData/低速/reduced-motionで積極的自動起動を避ける。
- 全motion/soundを一括preloadしない。
- hidden toolへ不要listenerを付けない。
- fetchはdestroy時にabortする。
- object URLは必ずrevokeする。
- UI変更だけでSDK bundleを再生成しない。

## 上流SDK

上流Core/Frameworkを行数削減目的だけで整形しません。upstream diff、ライセンス、将来更新が悪化します。Project Rev固有最適化はglue/runtime/buildへ置きます。

## 手動確認

1. 通常ページで遅延起動する。
2. SDKv2とSDKv4の代表モデルが描画される。
3. モデル切替、motion、表情、音声を代表ケースで確認する。
4. disable → enable → reset/loadを確認する。
5. asset timeout/404でも本文が残る。
6. mobile/reduced-motionで本文を邪魔しない。
7. BlogfaでLive2Dだけ失敗させてもnative/Project Rev本文が残る。

<!-- merged-from: TROUBLESHOOTING.md -->

## Merged from troubleshooting

# トラブルシューティング

## 最初に障害境界を決める

1. 静的HTML/CSS/Store
2. Blogfa editorial/supervisor
3. Live2D addon/loader/runtime
4. SDK/model asset

全部へretryを足さず、最初に壊れた所有境界を直します。

## 最初の検証

```bash
npm run check:static
npm run check:runtime
npm run check:delivery
```

Blogfa/UI変更なら:

```bash
npm run check:blogfa
npm run check:vnext
npm run check:editorial
```

## Live2Dが出ない

利用可能ならconsoleで:

```text
REV_LIVE2D_STATUS()
REV_LIVE2D_HEALTH()
```

順番:

1. `#waifu`, `#live2d2`, `#live2d4`が存在する。
2. `assets/live2d-loader.js`が取得できる。
3. `dist/live2d_bundle.js`が取得できる。
4. `assets/live2d-runtime.js`が取得できる。
5. `waifu-tips.json`とmodel assetに404がない。
6. statusが`failed`/`missing`/`disabled`/`hidden`のどれか確認。
7. Live2Dが壊れても本文が残ることを確認。

production経路で`waifu-tips.js`を探す必要はありません。旧互換ファイルであり、本番runtimeは実行しません。

ユーザー無効化状態は`REV_LIVE2D_ENABLE()`で解除できます。runtimeだけ再初期化する場合は`REV_LIVE2D_RESET()`後に`REV_LIVE2D_LOAD()`を使います。

## reset/reloadで挙動が二重になる

まず:

```bash
npm run check:runtime
```

smoke testは`mount → SDK2→SDK4 → destroy → mount`を実行し、destroy時`listenerCount=0`/`timerCount=0`、再mount後のlistener数が増殖しないことを検証します。

失敗した場合は新しいglobal flagで症状を隠さず、`live2d-runtime.js`で所有していないlistener/timer/fetch/object URLを探します。

## BlogfaだけLive2Dが出ない

`REV_LIVE2D_HEALTH()`の`status`、`checks`、`failures`を確認します。

Blogfa addonは独自tips patcherを持ちません。共通loader/runtimeの取得またはhealth境界を直してください。

## モデル404/破損

```bash
npm run check:static
```

validatorはモデルJSONのpath-bearingフィールドだけを追跡します。`Name`/`Id`に`.png`等が含まれてもasset参照とは限りません。

実404では以下を確認:

- pathの大文字/小文字
- Unicode名
- relative path
- moc/moc3
- texture
- motion/expression
- physics/pose/display info
- sound

Windowsで通るcase mismatchはLinux/CDNで失敗します。

## Blogfaが空白になる

```text
Blogfa native
→ blogfa-custom-html-snippet.html
→ responsive
→ supervisor/editorial
→ Project Rev health
→ optional Live2D addon
```

Project Rev層が不健全ならnative本文が残るのが正しい挙動です。`assets/blogfa-bootstrap.js`をproduction snippetへ追加しないでください。

## Shadowだけ崩れる

Shadow style所有はwidget/editorial側です。responsive scriptからShadow rootへ直接CSSを注入する修正はしません。

確認:

- `REV_EDITORIAL_MOUNT`
- 統合`assets/rev-editorial.css`
- 必要時のみ6分割fallback
- stale bootstrapの再混入

## CIだけ失敗する

最初の赤いstepを確認します。典型例:

- path case / 未commit asset
- stale generated CSS/bundle
- JavaScript syntax
- manifest version drift
- model reference
- Blogfa placeholder
- runtime lifecycle smoke
- vNext size/production-path contract
- webpack dev/prod mode contract

checkerが古いexact stringへ依存していないかも確認します。テストを消すのではなく、現在の意味的contractを検証する条件へ直します。

## npm警告

現行dev toolchainは古い依存を含みます。本番依存auditはCIで別途0 high以上を要求します。dev dependency major更新はruntime refactorと混ぜず、lockfile/webpack/TypeScript/SDKをまとめて検証します。

## セキュリティヘッダー

HSTS等は`_headers`にあります。CSPを追加する場合はinline script/style、CDN、GitHub/Blogfa経路を先に棚卸ししてください。いきなり厳格CSPを入れて表示を壊さないでください。
