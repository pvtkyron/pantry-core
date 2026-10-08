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
