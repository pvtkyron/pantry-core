"""Bounded, fail-closed recovery for canonical Full Release transport-stage failures.

Never changes source, force-pushes, approves a failed proof or starts a new Full Release.
A retry can re-run a failed job, including its compilation steps when present.
A retry uses GitHub's original-run /rerun-failed-jobs endpoint at most once.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "pvtkyron/pantry-core"
WORKFLOW = ".github/workflows/patisserie.yml"
SHA = re.compile(r"[0-9a-f]{40}\Z")
# Only GitHub-owned checkout and artifact transport steps. Never script/compiler,
# signer, source parity, Doctor, release pin, prepare or publisher failures.
TRANSPORT_STEPS = frozenset({
    "Open Pantry Core automation recipe",
    "Open pinned Workspace and integrated distribution",
    "Open maintained reuse recipe",
    "Open lane recipe",
    "Open prepare recipe",
    "Open canonical handoff recipe",
    "Open capsule helper",
    "Open route state checkpoint recipe",
    "Open original encrypted private source pin",
    "Download Java proof",
    "Download native library lane",
    "Download encrypted executable lane",
    "Download authenticated original prepared delivery",
    "Download encrypted prepared delivery",
    "Upload encrypted prepared delivery",
    "Upload encrypted executable lane",
    "Upload encrypted native library lane",
    "Upload encrypted Java lane",
})


@dataclass(frozen=True)
class Decision:
    retry: bool
    reason: str
    failing_steps: tuple[str, ...] = ()


def safe_label(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9 ._:/-]", "?", str(value))[:96]


def decide(event: dict, live: dict, jobs_response: dict, current_main: str) -> Decision:
    run = event.get("workflow_run") or {}
    if event.get("action") != "completed" or event.get("repository", {}).get("full_name") != REPO:
        return Decision(False, "untrusted-event")
    if not isinstance(run, dict) or run.get("id") != live.get("id"):
        return Decision(False, "original-run-identity")
    if (run.get("path") != WORKFLOW or live.get("path") != WORKFLOW or
        run.get("head_branch") != "main" or live.get("head_branch") != "main"):
        return Decision(False, "wrong-release-owner")
    if (run.get("repository") or {}).get("full_name") != REPO or (run.get("head_repository") or {}).get("full_name") != REPO:
        return Decision(False, "wrong-release-repository")
    if (run.get("event") not in ("workflow_dispatch", "repository_dispatch") or
        live.get("event") != run.get("event")):
        return Decision(False, "non-release-event")
    if (run.get("run_attempt") != 1 or live.get("run_attempt") != 1 or
        live.get("status") != "completed" or run.get("conclusion") != "failure" or live.get("conclusion") != "failure"):
        return Decision(False, "already-retried-or-not-failed")
    head = run.get("head_sha")
    if not isinstance(head, str) or not SHA.fullmatch(head) or live.get("head_sha") != head:
        return Decision(False, "release-sha-mismatch")
    if current_main != head:
        return Decision(False, "source-moved-or-already-published")
    jobs = jobs_response.get("jobs")
    if not isinstance(jobs, list) or type(jobs_response.get("total_count")) is not int or jobs_response["total_count"] != len(jobs):
        return Decision(False, "incomplete-job-proof")
    failed = [j for j in jobs if j.get("conclusion") in ("failure", "timed_out", "cancelled", "startup_failure")]
    if not failed:
        return Decision(False, "no-failed-job")
    selected = []
    for job in failed:
        if job.get("status") != "completed" or job.get("conclusion") != "failure":
            return Decision(False, "unsafe-job-conclusion", tuple(selected))
        steps = [s for s in job.get("steps", []) if s.get("conclusion") == "failure"]
        if len(steps) != 1 or steps[0].get("name") not in TRANSPORT_STEPS:
            names = tuple(safe_label(s.get("name", "unknown")) for s in steps)
            return Decision(False, "compiler-proof-or-unknown-failure", tuple(selected) + names)
        selected.append(steps[0]["name"])
    return Decision(True, "single-bounded-transport-retry", tuple(selected))


class GitHub:
    def __init__(self, token: str):
        if not token.strip():
            raise ValueError("Missing GitHub Actions token")
        self.token = token.strip()

    def request(self, path: str, method: str = "GET"):
        req = Request("https://api.github.com/repos/" + REPO + "/" + path,
            data=b"{}" if method == "POST" else None, method=method,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     "Content-Type": "application/json",
                     "User-Agent": "Kyron-CI-ReleaseRecovery"})
        try:
            with urlopen(req, timeout=30) as response:
                body = response.read(2 * 1024 * 1024)
                return json.loads(body) if body and method == "GET" else None
        except (HTTPError, URLError, TimeoutError):
            # Do not dump external error responses: they can include credentials.
            raise RuntimeError("GitHub API unavailable; recovery not submitted") from None


def inspect(api: GitHub, event: dict) -> Decision:
    run = event.get("workflow_run") or {}
    run_id = run.get("id")
    if type(run_id) is not int or run_id <= 0:
        return Decision(False, "invalid-run-id")
    if (event.get("repository") or {}).get("full_name") != REPO or run.get("path") != WORKFLOW:
        return Decision(False, "untrusted-run")
    live = api.request(f"actions/runs/{run_id}")
    if not isinstance(live, dict) or live.get("run_attempt") != 1 or live.get("status") != "completed":
        return Decision(False, "already-retried-or-active")
    jobs = api.request(f"actions/runs/{run_id}/attempts/1/jobs?per_page=100")
    main = api.request("commits/main")
    return decide(event, live, jobs, main.get("sha", ""))


def report(decision: Decision, url: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    msg = ("## Release recovery\n"
           f"- Original release: {safe_label(url)}\n"
           f"- Decision: {'one retry of failed jobs' if decision.retry else 'no automatic retry'}\n"
           f"- Reason: `{decision.reason}`\n")
    if decision.failing_steps:
        msg += "- Failed step(s): " + ", ".join(f"`{safe_label(step)}`" for step in decision.failing_steps) + "\n"
    msg += "- Policy: never rerun compiler, signature, source-pin, Doctor or publisher failures automatically.\n"
    print("[KYRON/RELEASE-RECOVERY] " + decision.reason + (" retry=true" if decision.retry else " retry=false"))
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write(msg)


def main() -> int:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != "refs/heads/main":
            raise ValueError("Canonical release recovery owner required")
        api = GitHub(os.environ.get("GH_TOKEN", ""))
        decision = inspect(api, event)
        run = event.get("workflow_run") or {}
        if decision.retry:
            # Catch manual re-run or a new publication admitted after our first read.
            latest = api.request(f"actions/runs/{run['id']}")
            current = api.request("commits/main")
            if (latest.get("run_attempt") != 1 or latest.get("status") != "completed" or
                latest.get("conclusion") != "failure" or current.get("sha") != run["head_sha"]):
                decision = Decision(False, "source-or-attempt-changed-during-recheck")
            else:
                # No POST retry on ambiguous network failure: duplicate requests are not harmless.
                api.request(f"actions/runs/{run['id']}/rerun-failed-jobs", "POST")
        report(decision, run.get("html_url", ""))
        return 0
    except (ValueError, KeyError, OSError, RuntimeError, TypeError):
        report(Decision(False, "recovery-controller-unavailable"), "")
        # Never report an infrastructure failure as a successful recovery.
        print("::warning::Release recovery could not verify the run; no automatic retry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
