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
