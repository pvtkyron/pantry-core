# AI execution rules

Read and follow the repository-root `AGENTS.md` before changing anything. It is the canonical rule set; this file only makes those rules discoverable to GitHub-hosted AI tools.

- Work only on `main`. Reconcile verified unique work onto `main` before deleting any non-main ref; never create merge commits or force-push shared history.
- Never commit private keys, PFX/PKCS#12, JKS, passwords, tokens, or decrypted secret material. Where Workspace signing is required, the canonical GitHub Actions contract is `KYRON_CODESIGN_PFX_B64` + `KYRON_CODESIGN_PASSWORD`, and the certificate must match `security/signing/canonical-signer.json`.
- Never mint a fallback signer merely to make CI pass. Missing canonical signing material is a fail-closed condition.
- Destructive cleanup must resolve and validate an exact allowlisted target first. Never issue drive-root, home-root, workspace-root, or broad-wildcard recursive deletes.
- Keep one authoritative source path per behavior and remove temporary migration/scratch artifacts when the verified migration is complete.
