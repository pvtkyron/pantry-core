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
