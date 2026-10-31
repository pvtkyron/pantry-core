"""Behavioral route checkpoints against disposable init-only Git remotes."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ACTION = Path(__file__).with_name("checkpoint.sh")
STATE = "Distribution/release/pantry-core-route-state.ini"
MESSAGE = "distribution: checkpoint Pantry Core route state [control-state]"


class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pantry-route-checkpoint-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.remote = self.root / "remote.git"
        self.source.mkdir()
        self.remote.mkdir()
        self.git(self.remote, "init", "--bare", "--initial-branch=main", "-q")
        self.git(self.source, "init", "--initial-branch=main", "-q")
        for repo in (self.source, self.remote):
            self.git(repo, "config", "user.name", "checkpoint fixture")
            self.git(repo, "config", "user.email", "fixture@example.invalid")
        self.pantry = self.source / "Distribution"
        (self.pantry / "release").mkdir(parents=True)
        self.config = self.pantry / "SrcVersion.ini"
        self.config.write_text("[runtime.contract]\nroute=source\n")
        self.state = self.source / STATE
        self.state.write_text("; Pantry-Source: " + "0" * 40 + "\nold=route\n")
        (self.source / "peer.txt").write_text("peer source\n")
        (self.source / "notes.txt").write_text("notes source\n")
        self.git(self.source, "add", ".")
        self.git(self.source, "commit", "-qm", "source fixture")
        self.sha = self.git(self.source, "rev-parse", "HEAD")
        self.git(self.source, "remote", "add", "origin", str(self.remote))
        self.git(self.source, "push", "-q", "origin", "main")
        # Real Actions checkouts at exact SHA have a detached HEAD.
        self.git(self.source, "checkout", "--detach", "-q", self.sha)
        self.generated = f"; Pantry-Source: {self.sha}\nroute=published\n"
        self.state.write_text(self.generated)
        self.config.write_text("[runtime.contract]\nroute=generated\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def git(repo: Path, *args: str) -> str:
        env = os.environ.copy()
        # Fixture commits do not depend on the operator's signing preferences.
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false")
        return subprocess.run(
            ("git", "-C", str(repo), *args), env=env, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.strip()

    def invoke(self, *, source_root: Path | None = None, source_sha: str | None = None):
        env = os.environ.copy()
        env.update(PANTRY_ROUTE_SOURCE_ROOT=str(source_root or self.pantry),
                   PANTRY_ROUTE_SOURCE_SHA=self.sha if source_sha is None else source_sha,
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false")
        return subprocess.run(("bash", str(ACTION)), cwd=self.root, env=env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def assert_success(self, result, marker: str) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout)

    def assert_failure(self, result, marker: str) -> None:
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(marker, result.stderr)

    def make_remote_commit(self, message: str) -> str:
        tree = self.git(self.remote, "rev-parse", "main^{tree}")
        return self.git(self.remote, "commit-tree", tree, "-p", self.sha, "-m", message)

    def write_hook(self, repo: Path, name: str, body: str) -> None:
        hooks = repo / ("hooks" if repo == self.remote else ".git/hooks")
        hook = hooks / name
        hook.write_text("#!/usr/bin/env bash\nset -eu\n" + body + "\n")
        hook.chmod(0o755)

    def assert_checkpoint(self, candidate: str) -> None:
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), candidate)
        self.assertEqual(self.git(self.source, "show", "-s", "--format=%P", candidate), self.sha)
        self.assertEqual(self.git(self.source, "diff-tree", "--no-commit-id", "--name-only", "-r", candidate), STATE)
        self.assertEqual(self.git(self.source, "show", "-s", "--format=%s", candidate), MESSAGE)
        self.assertEqual(self.git(self.source, "show", f"{candidate}:{STATE}"), self.generated.strip())

    def test_pushes_only_state_and_preserves_unrelated_index_and_worktree(self):
        (self.source / "peer.txt").write_text("peer staged work\n")
        self.git(self.source, "add", "peer.txt")
        (self.source / "notes.txt").write_text("unrelated local work\n")
        before_index = self.git(self.source, "diff", "--cached", "--binary")
        result = self.invoke()
        self.assert_success(result, "[PUSHED]")
        candidate = self.git(self.source, "rev-parse", "HEAD")
        self.assert_checkpoint(candidate)
        self.assertEqual(self.git(self.source, "diff", "--cached", "--binary"), before_index)
        self.assertEqual((self.source / "notes.txt").read_text(), "unrelated local work\n")
        self.assertEqual(self.config.read_text(), "[runtime.contract]\nroute=source\n")
        self.assertEqual(self.git(self.source, "for-each-ref", "--format=%(refname:short)", "refs/heads"), "main")

    def test_existing_identical_remote_checkpoint_is_a_safe_noop(self):
        self.assert_success(self.invoke(), "[PUSHED]")
        checkpoint = self.git(self.source, "rev-parse", "HEAD")
        self.git(self.source, "checkout", "--detach", "-q", self.sha)
        self.state.write_text(self.generated)
        before_index = self.git(self.source, "diff", "--cached", "--binary")
        result = self.invoke()
        self.assert_success(result, "[SKIP]")
        self.assertEqual(self.git(self.source, "rev-parse", "HEAD"), self.sha)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), checkpoint)
        self.assertEqual(self.git(self.source, "diff", "--cached", "--binary"), before_index)

    def test_remote_advanced_before_commit_skips_without_staging(self):
        peer = self.make_remote_commit("peer advanced")
        self.git(self.remote, "update-ref", "refs/heads/main", peer, self.sha)
        before_index = self.git(self.source, "diff", "--cached", "--binary")
        result = self.invoke()
        self.assert_success(result, "[SKIP]")
        self.assertEqual(self.git(self.source, "rev-parse", "HEAD"), self.sha)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), peer)
        self.assertEqual(self.git(self.source, "diff", "--cached", "--binary"), before_index)

    def test_race_during_push_skips_and_preserves_peer(self):
        peer = self.make_remote_commit("peer raced")
        self.write_hook(self.source, "pre-push",
                        f"git -C {shlex.quote(str(self.remote))} update-ref refs/heads/main {peer} {self.sha}\nexit 1")
        result = self.invoke()
        self.assert_success(result, "[SKIP]")
        self.assertIn("during push", result.stdout)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), peer)
        self.assertEqual(self.git(self.source, "show", "-s", "--format=%P", "HEAD"), self.sha)
        self.assertEqual(self.git(self.source, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"), STATE)

    def test_rejected_push_with_unchanged_remote_fails(self):
        self.write_hook(self.remote, "pre-receive", "exit 1")
        result = self.invoke()
        self.assert_failure(result, "push failed while remote main was unchanged")
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.sha)
        self.assertNotEqual(self.git(self.source, "rev-parse", "HEAD"), self.sha)

    def test_wrong_generated_pin_fails_before_restoring_or_committing(self):
        self.state.write_text("; Pantry-Source: " + "f" * 40 + "\nwrong=pin\n")
        config = self.config.read_bytes()
        self.assert_failure(self.invoke(), "source pin rejected")
        self.assertEqual(self.config.read_bytes(), config)
        self.assertEqual(self.git(self.source, "rev-parse", "HEAD"), self.sha)

    def test_local_head_drift_fails(self):
        (self.source / "drift.txt").write_text("local source drift\n")
        self.git(self.source, "add", "drift.txt")
        self.git(self.source, "commit", "-qm", "unexpected local commit")
        self.assert_failure(self.invoke(), "commit changed locally")
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.sha)

    def test_invalid_source_pin_fails(self):
        self.assert_failure(self.invoke(source_sha="not-a-commit"), "inputs rejected")

    def test_non_distribution_source_is_rejected(self):
        self.assert_failure(self.invoke(source_root=self.source), "integrated Workspace Distribution")

    def test_nested_distribution_git_checkout_is_rejected(self):
        self.git(self.pantry, "init", "-q", "--initial-branch=main")
        self.assert_failure(self.invoke(), "integrated Workspace Distribution")

    def test_staged_configuration_error_preserves_worktree_and_index(self):
        self.config.write_text("user staged configuration\n")
        self.git(self.source, "add", "Distribution/SrcVersion.ini")
        self.config.write_text("generated worktree configuration\n")
        before_index = self.git(self.source, "diff", "--cached", "--binary")
        result = self.invoke()
        self.assert_failure(result, "unexpected index changes")
        self.assertEqual(self.config.read_text(), "generated worktree configuration\n")
        self.assertEqual(self.git(self.source, "diff", "--cached", "--binary"), before_index)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), self.sha)


if __name__ == "__main__":
    unittest.main()
