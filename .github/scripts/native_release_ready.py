#!/usr/bin/env python3
"""Read-only dual-ABI approval gate and authenticated signed-candidate receipt lookup."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SHA = r"[0-9a-f]{64}"
MESSAGE = re.compile(rf"^signed-native-candidate-v1 source=([0-9a-f]{{40}}) sha32=({SHA}) sha64=({SHA}) run=([1-9][0-9]*) attempt=([1-9][0-9]*); NOT_PUBLISHED$")


def contract_pins(value):
    result = {}
    for bits, abi in (("32", "armeabi-v7a"), ("64", "arm64-v8a")):
        rows = []
        for channel in ("release", "insider"):
            pins = re.findall(rf"(?m)^{channel}_lib_sha256_{bits}=({SHA})\s*$", value)
            if len(pins) != 1:
                raise ValueError(f"Invalid or ambiguous {channel}/{bits} native approval pin")
            rows.extend(pins)
        result[abi] = rows[0] if rows[0] == rows[1] else None
    return result


def approved_releases(releases, pins):
    expected = {"runtime-lane-v1.json"}
    for abi in pins:
        expected.update((f"libkyron-{abi}.so", f"libkyron-{abi}.release.json", f"libkyron-{abi}.so.kyron-finalized"))
    if not all(pins.values()):
        return
    for release in releases:
        assets = release.get("assets") or []
        names = [a.get("name") for a in assets]
        if len(names) != len(set(names)) or not expected.issubset(names):
            continue
        by_name = {a["name"]: a for a in assets}
        if not all(by_name[n].get("state") == "uploaded" and (by_name[n].get("size") or 0) > 0 for n in expected):
            continue
        if all(by_name[f"libkyron-{abi}.so"].get("digest") == "sha256:" + digest for abi, digest in pins.items()):
            yield release


def approved(releases, pins):
    return any(approved_releases(releases, pins))


def source_approved(releases, pins, workspace, specs):
    """Bind approved bytes to unchanged canonical Git inputs, never just old pins."""
    from workspace_input_key import tree
    current = tree(workspace, "HEAD", specs)
    for release in approved_releases(releases, pins):
        target = release.get("target_commitish", "")
        if not re.fullmatch(r"[0-9a-f]{40}", target):
            continue
        result = subprocess.run(["git", "-C", str(workspace), "merge-base", "--is-ancestor", target, "HEAD"], capture_output=True, timeout=60)
        if result.returncode == 1:
            continue
        if result.returncode:
            raise ValueError("Approved native source ancestry inspection failed")
        if tree(workspace, target, specs) == current:
            return True
    return False


def parse_receipt(message, source_sha):
    match = MESSAGE.fullmatch(message.strip())
    if not match or match.group(1) != source_sha:
        raise ValueError("Native candidate receipt provenance mismatch")
    return {"armeabi-v7a": match.group(2), "arm64-v8a": match.group(3)}


def clean_token(value):
    token = value.strip(" \t\r\n\ufeff")
    if not token or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ValueError("Native approval credential has invalid characters")
    return token


def fetch_json(url, token):
    req = Request(url, headers={"Authorization": "Bearer " + clean_token(token), "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "kyron-release-readiness"})
    for attempt in range(1, 6):
        try:
            with urlopen(req, timeout=30) as reply:
                return json.load(reply)
        except HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 5:
                raise
            reason = "HTTP " + str(error.code)
        except URLError as error:
            if not isinstance(error.reason, (TimeoutError, ConnectionError)) or attempt == 5:
                raise
            reason = "connection interrupted"
        except (TimeoutError, ConnectionError):
            if attempt == 5:
                raise
            reason = "connection interrupted"
        print(f"[NATIVE/API][RETRY] temporary {reason}; attempt={attempt}/5")
        time.sleep(min(2 ** (attempt - 1), 8))


def candidate_receipt(repo, token, source_sha, inputs_sha256=""):
    """Read an authenticated, tiny, source-pinned Actions artifact; never infer publication."""
    name = "kyron-native-receipt-" + source_sha
    url = f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&name={name}"
    response = fetch_json(url, token)
    matches = [row for row in response.get("artifacts", []) if row.get("name") == name and row.get("expired") is False]
    if inputs_sha256:
        if not re.fullmatch(SHA,inputs_sha256):
            raise ValueError("Canonical native input fingerprint rejected")
        seen={row.get("id") for row in matches}
        for page in range(1,6):
            listing=fetch_json(f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100&page={page}",token)
            rows=listing.get("artifacts",[])
            for row in rows:
                if (row.get("id") not in seen and row.get("expired") is False and
                        re.fullmatch(r"kyron-native-receipt-[0-9a-f]{40}",row.get("name",""))):
                    matches.append(row);seen.add(row.get("id"))
            if len(rows)<100:break
    for item in sorted(matches, key=lambda row: row.get("created_at", ""), reverse=True):
        original_source=item["name"][len("kyron-native-receipt-"):]
        original_name=item["name"]
        runner = item.get("workflow_run") or {}
        run_id = runner.get("id")
        if (not isinstance(run_id, int) or run_id <= 0 or runner.get("head_branch") != "main"
                or runner.get("repository_id") != runner.get("head_repository_id")
                or not isinstance(item.get("size_in_bytes"), int) or not 0 < item["size_in_bytes"] <= 32768):
            raise ValueError("Native candidate receipt owner, branch or size rejected")
        run = fetch_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
        path = run.get("path")
        if (run.get("repository") or {}).get("full_name") != repo or run.get("head_branch") != "main" or run.get("status") != "completed" or path not in (
                ".github/workflows/patisserie.yml", ".github/workflows/component-lib.yml", ".github/workflows/source-watch.yml"):
            raise ValueError("Native candidate receipt producer rejected")
        jobs = fetch_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token).get("jobs", [])
        expected = {
            ".github/workflows/source-watch.yml": ("Recover verified native receipt without rebuilding",
                ("Verify original signed run and all six candidate file digests", "Upload long-lived lightweight candidate receipt only")),
            ".github/workflows/patisserie.yml": ("Record verified signed native candidate (not published)",
                ("Register verified signed pair without asserting publication", "Preserve small verified native candidate receipt")),
            ".github/workflows/component-lib.yml": ("Record verified signed candidate (publication not implied)",
                ("Register verified signed pair without asserting publication", "Preserve small verified native candidate receipt")),
        }[path]
        matched_jobs = [job for job in jobs if job.get("name") == expected[0] and job.get("conclusion") == "success"]
        if len(matched_jobs) != 1:
            raise ValueError("Native candidate verified uploader job missing")
        steps = {step.get("name"): step.get("conclusion") for step in matched_jobs[0].get("steps", [])}
        if any(steps.get(name) != "success" for name in expected[1]):
            raise ValueError("Native candidate producer signature/upload steps missing")
        with tempfile.TemporaryDirectory(prefix="kyron-native-receipt-") as temp:
            env = os.environ.copy()
            env["GH_TOKEN"] = clean_token(token)
            command = ["gh", "run", "download", str(run_id), "-R", repo, "-n", original_name, "-D", temp]
            result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=45)
            if result.returncode != 0:
                raise ValueError("Authenticated native receipt download rejected")
            files = list(Path(temp).rglob("*"))
            if len(files) != 1 or files[0].name != "native-candidate-receipt.json" or not files[0].is_file():
                raise ValueError("Native receipt inventory rejected")
            receipt = json.loads(files[0].read_text(encoding="utf-8"))
            if (receipt.get("schema") != 1 or receipt.get("source_sha") != original_source
                    or receipt.get("producer_run_id") != run_id
                    or receipt.get("verified") is not True or receipt.get("published") is not False):
                raise ValueError("Native receipt source, producer or publication status rejected")
            if original_source!=source_sha:
                if not inputs_sha256 or receipt.get("inputs_sha256")!=inputs_sha256:
                    continue
            elif inputs_sha256 and receipt.get("inputs_sha256") and receipt["inputs_sha256"]!=inputs_sha256:
                continue
            pair = {"armeabi-v7a": receipt.get("sha32"), "arm64-v8a": receipt.get("sha64")}
            if not all(isinstance(value, str) and re.fullmatch(SHA, value) for value in pair.values()):
                raise ValueError("Native receipt dual-ABI digest rejected")
            return pair
    return None


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: native_release_ready.py Distribution/SrcVersion.ini")
    repo = os.environ.get("PRIVATE_SOURCE_REPOSITORY", "")
    token = os.environ.get("PRIVATE_SOURCE_TOKEN", "")
    pantry = os.environ.get("GITHUB_REPOSITORY", "")
    pantry_token = os.environ.get("PANTRY_TOKEN", "")
    source_sha = os.environ.get("WORKSPACE_SHA", "")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token
            or pantry != "pvtkyron/pantry-core" or not pantry_token or not re.fullmatch(r"[0-9a-f]{40}", source_sha)):
        raise SystemExit("Authenticated pinned native release metadata access unavailable")
    pins = contract_pins(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    releases = fetch_json(f"https://api.github.com/repos/{repo}/releases?per_page=100", token)
    candidate = candidate_receipt(pantry, pantry_token, source_sha, os.environ.get("NATIVE_INPUTS_SHA256", ""))
    ready = approved(releases, pins)
    match = bool(candidate and candidate == pins)
    specs_path = os.environ.get("NATIVE_SPECS_FILE", "")
    workspace = Path(sys.argv[1]).resolve().parents[1]
    bound = source_approved(releases, pins, workspace,
        json.loads(Path(specs_path).read_text(encoding="utf-8-sig"))) if specs_path else False
    outputs = {"ready": ready, "source_approved": bound, "candidate_verified": candidate is not None, "candidate_matches_pins": match}
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for key, value in outputs.items():
                output.write(f"{key}={str(value).lower()}\n")
    print("[NATIVE/APPROVAL][%s] approved_metadata=%s source_approved=%s signed_candidate=%s candidate_matches_pins=%s" %
          ("READY" if ready else "WAIT", str(ready).lower(), str(bound).lower(), str(candidate is not None).lower(), str(match).lower()))


if __name__ == "__main__":
    main()
