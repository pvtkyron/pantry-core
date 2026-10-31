#!/usr/bin/env python3
"""Recover a tiny native receipt from an existing, signed and SHA-verified hosted artifact."""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")

def verified_files(root, document, source, run_id, attempt):
    if (document.get("schema") != 1 or document.get("product") != "KyronSignedNativeCandidate"
            or document.get("source_workspace_sha") != source
            or str(document.get("run_id")) != str(run_id)
            or str(document.get("run_attempt")) != str(attempt)):
        raise ValueError("Native candidate provenance mismatch")
    wanted = {f"{abi}/{leaf}" for abi in ("armeabi-v7a", "arm64-v8a")
              for leaf in ("libkyron.so", "libkyron.release.json", "libkyron.so.kyron-finalized")}
    files = document.get("files")
    if not isinstance(files, dict) or set(files) != wanted:
        raise ValueError("Native candidate file inventory invalid")
    observed = {file.relative_to(root).as_posix() for file in root.rglob("*") if file.is_file()}
    if observed != wanted | {"native-candidate.json"}:
        raise ValueError("Native candidate archive contains unexpected files")
    for rel, metadata in files.items():
        path = root / rel
        if (not path.is_file() or path.is_symlink() or path.stat().st_size != metadata.get("size")
                or not isinstance(metadata.get("sha256"), str) or not SHA64.fullmatch(metadata["sha256"])):
            raise ValueError("Native candidate file metadata invalid")
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
            raise ValueError("Native candidate SHA256 mismatch")
    return files["armeabi-v7a/libkyron.so"]["sha256"], files["arm64-v8a/libkyron.so"]["sha256"]

def fetch_json(url, token):
    request = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "kyron-native-candidate-recovery"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)

def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    source = os.environ.get("CANDIDATE_SOURCE_SHA", "")
    run_id = os.environ.get("CANDIDATE_RUN_ID", "")
    attempt = os.environ.get("CANDIDATE_ATTEMPT", "")
    token = os.environ.get("GH_TOKEN", "").strip(" \r\n\t\ufeff")
    if (repo != "pvtkyron/pantry-core" or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or not SHA40.fullmatch(source) or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not re.fullmatch(r"[1-9][0-9]*", attempt)
            or not token.isascii() or not token or any(ord(c) < 33 for c in token)):
        raise SystemExit("Candidate recovery inputs rejected")
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}"
    run = fetch_json(url, token)
    if ((run.get("head_repository") or {}).get("full_name") != repo or run.get("head_branch") != "main"
            or run.get("path") not in (".github/workflows/patisserie.yml", ".github/workflows/component-lib.yml")
            or run.get("status") != "completed"):
        raise SystemExit("Native candidate producer run identity rejected")
    jobs = fetch_json(url + f"/attempts/{attempt}/jobs?per_page=100", token).get("jobs", [])
    native = [job for job in jobs if job.get("name", "").endswith("Compile Android native libraries")
              and job.get("conclusion") == "success"]
    if len(native) != 1:
        raise SystemExit("Signed native job success evidence unavailable")
    steps = {step.get("name"): step.get("conclusion") for step in native[0].get("steps", [])}
    for step in ("Verify and bind signed native candidate to its compiled source",
                 "Preserve signed candidate for explicit lib contract rotation"):
        if steps.get(step) != "success":
            raise SystemExit("Native signing verification or preservation failed")
    matches = list(Path(os.environ["CANDIDATE_INPUT_DIR"]).rglob("native-candidate.json"))
    if len(matches) != 1 or matches[0].is_symlink():
        raise SystemExit("Native candidate manifest missing or ambiguous")
    sha32, sha64 = verified_files(matches[0].parent, json.loads(matches[0].read_text(encoding="utf-8")), source, run_id, attempt)
    out = Path(os.environ["RUNNER_TEMP"]) / "kyron-native-receipt"
    out.mkdir(parents=True, exist_ok=True)
    payload = {"schema": 1, "source_sha": source, "sha32": sha32, "sha64": sha64,
               "producer_run_id": int(os.environ["GITHUB_RUN_ID"]),
               "producer_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]),
               "original_signed_candidate_run_id": int(run_id), "verified": True, "published": False}
    (out / "native-candidate-receipt.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print("[NATIVE/RECOVERY][VERIFIED] prior signed pair and hashes verified; NOT_PUBLISHED")

if __name__ == "__main__":
    main()
