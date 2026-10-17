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
