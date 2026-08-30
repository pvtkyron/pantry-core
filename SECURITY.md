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
