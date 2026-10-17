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
