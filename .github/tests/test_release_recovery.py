"""Fail-closed regression fixtures for actual single-retry release recovery."""
import importlib.util
import json
import os
import tempfile
from unittest.mock import patch
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("recovery", ROOT / ".github/scripts/release_recovery.py")
m = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = m
spec.loader.exec_module(m)
SHA = "a" * 40
OLDER = "b" * 40


def fixture(step="Upload encrypted prepared delivery", *, outcome="failure", attempt=1, source=SHA):
    run = {"id": 123, "path": m.WORKFLOW, "head_branch": "main", "head_sha": source,
           "run_attempt": attempt, "conclusion": outcome, "status": "completed",
           "event": "workflow_dispatch", "repository": {"full_name": m.REPO},
           "head_repository": {"full_name": m.REPO}}
    event = {"action": "completed", "repository": {"full_name": m.REPO}, "workflow_run": run}
    jobs = {"total_count": 1, "jobs": [{"name": "Workspace / Prepare", "status": "completed", "conclusion": "failure",
            "steps": [{"name": step, "conclusion": "failure"}]}]}
    return event, run.copy(), jobs


class PolicyTests(unittest.TestCase):
    def test_one_github_artifact_failure_is_retried(self):
        for step in ("Upload encrypted prepared delivery", "Download native library lane", "Open prepare recipe"):
            with self.subTest(step=step):
                self.assertTrue(m.decide(*fixture(step), SHA).retry)

    def test_compilation_doctor_signing_pin_and_publisher_are_never_retried(self):
        for step in ("Compile and verify signed launcher lane", "Taste quietly", "Pin private Pantry delivery",
                     "Promote restored lanes into Pantry", "Publish exact Pantry revision through canonical mirror",
                     "Materialize canonical code signer trust"):
            with self.subTest(step=step):
                d = m.decide(*fixture(step), SHA)
                self.assertFalse(d.retry)
                self.assertEqual(d.reason, "compiler-proof-or-unknown-failure")

    def test_no_retry_once_attempt_two_exists(self):
        e, run, jobs = fixture(attempt=2)
        self.assertFalse(m.decide(e, run, jobs, SHA).retry)

    def test_published_newer_main_refuses_old_candidate(self):
        self.assertEqual(m.decide(*fixture(), OLDER).reason, "source-moved-or-already-published")

    def test_mixed_real_build_failure_prevents_retry(self):
        event, run, jobs = fixture()
        jobs["jobs"].append({"name": "Workspace / EXE", "status": "completed", "conclusion": "failure",
                             "steps": [{"name": "Compile and verify signed launcher lane", "conclusion": "failure"}]})
        jobs["total_count"] = 2
        self.assertFalse(m.decide(event, run, jobs, SHA).retry)

    def test_incomplete_jobs_fail_closed(self):
        event, run, jobs = fixture()
        jobs["total_count"] = 2
        self.assertEqual(m.decide(event, run, jobs, SHA).reason, "incomplete-job-proof")

    def test_cancelled_or_timed_out_job_requires_human_review(self):
        for conclusion in ("cancelled", "timed_out", "startup_failure"):
            with self.subTest(conclusion=conclusion):
                event, run, jobs = fixture()
                jobs["jobs"][0]["conclusion"] = conclusion
                self.assertFalse(m.decide(event, run, jobs, SHA).retry)

    def test_wrong_fork_event_or_run_identity_is_not_retried(self):
        event, run, jobs = fixture()
        event["workflow_run"]["head_repository"] = {"full_name": "fork/malicious"}
        self.assertFalse(m.decide(event, run, jobs, SHA).retry)
        event, run, jobs = fixture()
        run["id"] = 999
        self.assertFalse(m.decide(event, run, jobs, SHA).retry)

    def test_nonrelease_event_is_rejected(self):
        event, run, jobs = fixture()
        event["workflow_run"]["event"] = "pull_request"
        self.assertFalse(m.decide(event, run, jobs, SHA).retry)

    def test_live_run_state_prevents_duplicate_rerun(self):
        class API:
            def request(self, path, method="GET"):
                if path == "actions/runs/123":
                    return {**fixture()[1], "run_attempt": 2}
                raise AssertionError("should not fetch when attempt moved")
        self.assertEqual(m.inspect(API(), fixture()[0]).reason, "already-retried-or-active")


    def test_main_requests_exactly_one_failed_jobs_rerun(self):
        event, run, jobs = fixture()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"event.json"
            summary = Path(temp)/"summary.md"
            source.write_text(json.dumps(event))
            class API:
                calls = []
                def request(self, path, method="GET"):
                    self.calls.append((path, method))
                    if method == "POST":
                        return None
                    if path == "actions/runs/123":
                        return run
                    if path == "actions/runs/123/attempts/1/jobs?per_page=100":
                        return jobs
                    if path == "commits/main":
                        return {"sha": SHA}
                    raise AssertionError(path)
            api = API()
            with patch.object(m,"GitHub",lambda *_: api), patch.dict(os.environ,{
                "GITHUB_REPOSITORY":m.REPO,"GITHUB_REF":"refs/heads/main",
                "GITHUB_EVENT_PATH":str(source),"GITHUB_STEP_SUMMARY":str(summary),"GH_TOKEN":"fake-only"}):
                self.assertEqual(m.main(),0)
            self.assertEqual(api.calls.count(("actions/runs/123/rerun-failed-jobs","POST")),1)
            self.assertIn("one retry of failed jobs",summary.read_text())

    def test_main_does_not_rerun_if_source_changes_before_post(self):
        event, run, jobs = fixture()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"event.json"
            summary = Path(temp)/"summary.md"
            source.write_text(json.dumps(event))
            class API:
                calls=[]
                main_reads=0
                def request(self,path,method="GET"):
                    self.calls.append((path,method))
                    if method == "POST":
                        raise AssertionError("should never retry")
                    if path == "actions/runs/123":
                        return run
                    if path == "actions/runs/123/attempts/1/jobs?per_page=100":
                        return jobs
                    if path == "commits/main":
                        self.main_reads += 1
                        return {"sha":SHA if self.main_reads==1 else OLDER}
                    raise AssertionError(path)
            api = API()
            with patch.object(m,"GitHub",lambda *_: api), patch.dict(os.environ,{
                "GITHUB_REPOSITORY":m.REPO,"GITHUB_REF":"refs/heads/main",
                "GITHUB_EVENT_PATH":str(source),"GITHUB_STEP_SUMMARY":str(summary),"GH_TOKEN":"fake-only"}):
                self.assertEqual(m.main(),0)
            self.assertNotIn(("actions/runs/123/rerun-failed-jobs","POST"),api.calls)
            self.assertIn("source-or-attempt-changed-during-recheck",summary.read_text())

    def test_ci_invokes_recovery_test_as_a_separate_command(self):
        graph = yaml.safe_load((ROOT / ".github/workflows/release-orchestration-checks.yml").read_text())
        script = next(s["run"] for s in graph["jobs"]["public"]["steps"] if "test_workspace_delivery_pin.py" in s.get("run", ""))
        self.assertIn("python .github/tests/test_workspace_delivery_pin.py\npython .github/tests/test_release_recovery.py", script)
        for path in (".github/scripts/release_recovery.py", ".github/tests/test_release_recovery.py", ".github/workflows/release-recovery.yml"):
            self.assertIn(path, graph["on"]["push"]["paths"])

    def test_correct_workflow_wiring_and_permissions(self):
        w = yaml.safe_load((ROOT / ".github/workflows/release-recovery.yml").read_text())
        self.assertEqual(w["on"]["workflow_run"]["workflows"], ["Kyron Full Release · 6h"])
        self.assertEqual(w["jobs"]["recover"]["permissions"]["actions"], "write")
        self.assertIn("run_attempt == 1", w["jobs"]["recover"]["if"])
        self.assertIn("cancel-in-progress", w["concurrency"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
