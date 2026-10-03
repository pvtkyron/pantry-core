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
