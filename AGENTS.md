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
- Audit allowed source Actions using `git rev-parse HEAD:<path>` against the reviewed Git blob, retaining exact filename/set restrictions. Worktree LF/CRLF conversion must not manufacture drift; a real workflow edit still requires review and a new expected blob.
- Handoff crypto regression lives in `.github/tests/test_workspace_handoff.py` and requires `cryptography==46.0.4`; set `KYRON_TEST_PWSH` to Windows PowerShell 5.1 in hosted regression. Preserve the authenticated byte format, MAC-before-decrypt ordering and single byte-array returns.
