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
