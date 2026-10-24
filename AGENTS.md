# Repository agent rules

These rules apply to every human or AI agent working in this repository.

## Mainline
- `main` is the only development branch. Do not create or retain feature, fix, release, backup, recovery, or checkpoint branches.
- Reconcile any unique work onto `main` with a linear fast-forward/replay workflow, verify it, then delete the extra ref.
- Do not force-push shared history and do not create merge commits just to preserve temporary branches.
- Keep one authoritative implementation for each behavior; do not leave parallel old/new/v2/final/legacy paths.

## Security and signing
- Never commit private keys, PFX/PKCS#12, JKS, passwords, tokens, or decrypted secret material, even when the repository is private.
- Public certificates, fingerprints, and non-secret signing metadata may be tracked in the repository's canonical security location.
- Private release-signing material belongs only in protected local state or GitHub Actions secrets.
- Do not mint a fallback signing identity when a canonical identity already exists. Rotation requires updating all pins/consumers and completing signed verification before retiring the old identity.

## Source discipline
- Do not commit scratch clones, backups, caches, generated dumps, one-shot migration files, or build artifacts unless they are an explicit maintained repository contract.
- Reuse the existing source/build/release owner instead of adding a duplicate path.
- Inspect existing changes before editing, preserve unrelated work, run the relevant tests/checks, and only then push to `main`.
- Repository cleanup must use exact scoped paths; never use drive/root-wide or broad wildcard deletion.

## Hosted build and publication contract

- Keep hosted orchestration in this repository's `.github/`; fix native, managed, signing and packaging behavior in its authoritative Workspace source. Use the supplied isolated checkout on `main`.
- The supported full release is pinned sources → Java/D8, both Android ABIs and signed Windows Launcher → verified handoffs/Prepare → Windows and Linux Doctor → canonical mirror verification → headless smoke. A passed compile alone does not establish publication.
- Route `KyronLink/` code changes to `component-kyronlink` with the exact changed Workspace SHA; the existing regression workflow owns its Linux Android job. Require real app/helper Java compilation, AAPT2/D8, Mundo ABI/source checks and proxy/DNS behavior with no skipped or zero-test success. Keep docs-only changes idle and retain any independent Launcher/native/full-release route in mixed changes. `component-apk` is the RevTranslator ABI lane, not the Kyron Link APK builder. For four-part Temurin versions, pin the official release metadata `version.semver` value accepted by setup-java; do not pass the raw Java version or loosen the pin.
- Keep the Workspace full-release path independent from SDK and Web project checks. Those projects have their own source router and component validation flows; changes to their reusable workflows must not trigger or gate the Workspace compiler/promotion path.
- Keep `Distribution/src/**` changes on the Pantry Component Router's DEX lane and Pantry Delta path; do not also launch the full Workspace build for a Java-only change. Mixed changes that touch a full-release contract still require the full pipeline.
- Route changes confined to `Launcher/**` through the signed Launcher component lane and changes confined to `VeraInternal/**` through the native-lib component lane. Mixed component/source-contract changes keep the atomic full release; a newer source dispatch supersedes an older pinned release run.
- Keep workflows with an active caller, push/repository-dispatch route, schedule, or manual entrypoint. Remove a workflow only after confirming none of those uses or live run history remain.
- The Pantry mirror gate may reuse prior work only when the exact Pantry SHA is currently published and a successful mirror run attests that same SHA. Otherwise dispatch and require a successful exact-source mirror plus the exact `Pantry-Source` on `main`.
- Prepare restores authenticated lane artifacts and promotes them with `-SkipBuild`; provision only the SHA-locked managed Python via Workspace `etc/build/setup-python.ps1`. Do not restore the shared compiler cache or install Android/Java/.NET/LLVM toolchains in Prepare. Keep source-pin/clean-index checks, native staging self-tests, signatures and provenance verification intact.
- Native-only builds (`include_nativebridge: false`) use the proven pinned NDK + LLVM bootstrap shared with the native component lane. Do not add Java, Android SDK or managed .NET provisioning to that path without an actual new build dependency and a measured hosted run.
- Source routing must never treat a failed Git comparison as an empty or partially valid file list. Refresh the same two immutable Workspace revisions once, compare them again, and retain the source cursor without dispatching if recovery fails. Preserve the behavioral missing-object, partial-output, permanent-failure and failed-refresh fixtures in `.github/tests/test_router_large_change_lists.py`.
- Preserve exact source and delivery SHAs, authenticated handoff lane identities, artifact hashes and the promoted revision. A newer remote `main` must not silently replace the revision that was built and verified.
- Hosted signer setup uses `-Ephemeral -RequireExistingIdentity`. Preserve the canonical `identity.json` Git blob, signer fingerprints and header inventory. Never rewrite signer metadata, timestamps or machine paths during compilation to repair an audit failure.
- Keep the prebuild input audit immutable through recording and repeat verification. Diagnose a mismatch with the input trace; never regenerate the baseline after compilation, omit changed inputs or accept an unsigned cache hit.
- A delta requires route state pinned to the published `Pantry-Source`. Without that state, use the canonical full mirror before partial packing. Keep missing signed-record checks strict; a changed compiled DEX route cannot be inherited from unrelated checked-in bytes.
- Checkpoint route state only after publication verification, for the exact source SHA and the exact state file. Preserve concurrent source work and use a normal fast-forward push. Keep full-mirror fallback outside the delta publication lock.
- Only the canonical publisher owns generated `kyron/` records and root snapshots. Retain signatures, expected-ref leases, control-plane preservation and exact published-source verification. Never edit opaque payloads or replace remote history by hand.
- Run focused behavioral regressions for changed owners. Reuse successful expensive builds when their effective inputs still match; record the workflow/run, source, delivery and published revisions when reporting readiness. Keep failed, skipped and unexecuted checks distinct.
- Before changing delta routing or checkpoint behavior, run `python .github/tests/test_pantry_delta_routing.py` (PyYAML required), `python .github/actions/pantry-route-state/test_checkpoint.py`, Bash syntax checks and actionlint on the affected workflows. Preserve the missing/stale-state fallback, exact-source, strict failure and concurrent-push fixtures.

## Hosted regression stability
- Enable `git config --global core.longpaths true` before Windows checkouts: recovered KyronLink package paths exceed the default Windows Git path limit.
- Workspace, SDK and Web sources own no GitHub Actions definitions. Reject any source `.github/workflows/*.yml` or `*.yaml` before compilation. Keep orchestration and PowerShell validation here; do not restore the retired Workspace updater workflow or its former blob allowlist.
- Handoff crypto regression lives in `.github/tests/test_workspace_handoff.py` and requires `cryptography==46.0.4`; set `KYRON_TEST_PWSH` to Windows PowerShell 5.1 in hosted regression. Preserve the authenticated byte format, MAC-before-decrypt ordering and single byte-array returns.

<!-- merged-from: AI_README.md -->

## Merged from AI_README.md

# AI / Automation Repository Rules

These rules apply to every AI agent, automation, IDE assistant, CI helper, and human maintenance task in this repository.

## Mainline only
- `main` is the only development branch. Do not create or retain feature, fix, release, backup, recovery, snapshot, or AI branches.
- Reconcile unique work into `main`, verify it, then delete the extra branch locally and remotely.
- Keep history linear. Use fast-forward updates; do not create merge commits and do not force-push shared history.

## Signing and secrets
- Never commit private keys, PFX/JKS private material, passwords, tokens, recovery codes, or decrypted signing state.
- Track only public certificates, public keys, fingerprints, and signer metadata under the repository security source-of-truth.
- Private signing material belongs only in approved protected local state or GitHub Actions Secrets.
- CI and release builds must fail closed when required signing material is unavailable; never mint fallback identities just to pass a build.

## CI ownership
- Respect the designated centralized CI owner. Source repositories must not grow ad-hoc GitHub Actions workflows.
- If this repository is the designated CI owner, keep workflows centralized and reusable here instead of duplicating them across source repositories.

## Destructive operations
- Never use broad recursive delete targets against a drive root, repository root, state root, SDK root, home directory, or wildcard-expanded parent.
- Resolve canonical paths first and delete only exact disposable targets from an explicit allowlist.
- Generated/cache/output directories are deleted only by their known owner. Do not create backup trees unless explicitly requested.

## Repository hygiene
- Keep source, durable tests, maintained docs, and recurring build/release tooling in Git; keep scratch files, caches, packages, generated reports, and build artifacts out.
- Reuse canonical build/test/release lanes and verify before claiming success.
- A task is not complete until branch inventory, working-tree state, required tests/builds, signing status, and remote `main` are verified.

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
