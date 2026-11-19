#!/usr/bin/env python3
"""Select completed canonical Native evidence; cryptographic promotion remains independent."""
import io
import json
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

REPO = "pvtkyron/pantry-core"
PRODUCERS = {".github/workflows/component-lib.yml", ".github/workflows/patisserie.yml"}
SHA = re.compile(r"[0-9a-f]{40}")
NUMBER = re.compile(r"[1-9][0-9]*")

def producer(event, fresh):
    original = event.get("workflow_run") or {}
    for run in (original, fresh):
        if (run.get("repository", {}).get("full_name", REPO) != REPO
                or (run.get("head_repository") or {}).get("full_name") != REPO
                or run.get("head_branch") != "main" or run.get("path") not in PRODUCERS
                or run.get("status") != "completed" or run.get("conclusion") != "success"
                or not SHA.fullmatch(str(run.get("head_sha", "")))
                or not NUMBER.fullmatch(str(run.get("id", "")))
                or not NUMBER.fullmatch(str(run.get("run_attempt", "")))):
            raise ValueError("Canonical successful Native producer required")
    if event.get("repository", {}).get("full_name") != REPO or any(
            original.get(k) != fresh.get(k) for k in ("id", "run_attempt", "head_sha", "path")):
        raise ValueError("Producer changed since completion event")
    return fresh["id"], fresh["run_attempt"]

def signed_artifact(artifacts, run_id, attempt):
    name = f"kyron-signed-native-candidate-{run_id}-{attempt}"
    matches = [a for a in artifacts if a.get("name") == name and a.get("expired") is False]
    if not matches:
        return None
    if len(matches) != 1 or not NUMBER.fullmatch(str(matches[0].get("id", ""))):
        raise ValueError("Ambiguous signed candidate")
    return matches[0]

def document(wire, leaf):
    if not wire or len(wire) > 134217728:
        raise ValueError("Candidate archive size rejected")
    with zipfile.ZipFile(io.BytesIO(wire)) as archive:
        matches = [i for i in archive.infolist() if i.filename == leaf]
        if len(matches) != 1 or not 0 < matches[0].file_size <= 65536:
            raise ValueError("Candidate metadata missing or ambiguous")
        return json.loads(archive.read(matches[0]))

def source_pin(receipt, run_id, attempt, small):
    source = receipt.get("source_sha" if small else "source_workspace_sha")
    if receipt.get("schema") != 1 or not SHA.fullmatch(str(source or "")):
        raise ValueError("Original compiled source invalid")
    if small:
        valid = (receipt.get("producer_run_id") == run_id and receipt.get("producer_attempt") == attempt
                 and receipt.get("verified") is True and receipt.get("published") is False
                 and all(re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(k, ""))) for k in ("sha32", "sha64")))
    else:
        valid = (receipt.get("product") == "KyronSignedNativeCandidate"
                 and str(receipt.get("run_id")) == str(run_id)
                 and str(receipt.get("run_attempt")) == str(attempt))
    if not valid:
        raise ValueError("Original producer receipt mismatch")
    automatic = receipt.get("auto_promote", False)
    if not isinstance(automatic, bool):
        raise ValueError("Automatic promotion intent invalid")
    return source if automatic else None

def api(endpoint, raw=False):
    result = subprocess.run(["gh", "api", f"repos/{REPO}/{endpoint}"], capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError("GitHub candidate evidence unavailable")
    return result.stdout if raw else json.loads(result.stdout)

def requested_producer(event, fetch=api, pause=time.sleep):
    if os.environ.get("GITHUB_EVENT_NAME")=="workflow_run":
        run_id=(event.get("workflow_run") or {}).get("id")
        if not NUMBER.fullmatch(str(run_id or "")):
            raise ValueError("Producer id invalid")
        fresh=fetch(f"actions/runs/{run_id}")
        run_id,attempt=producer(event,fresh)
        return run_id,attempt,None
    inputs=event.get("inputs") or {}
    run_id,attempt,source=(str(inputs.get(k,"")) for k in ("signed_run_id","signed_attempt","source_sha"))
    if (os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
            or str(inputs.get("automatic","")).lower()!="true"
            or event.get("repository",{}).get("full_name")!=REPO
            or not NUMBER.fullmatch(run_id) or not NUMBER.fullmatch(attempt) or not SHA.fullmatch(source)):
        raise ValueError("Explicit automatic Release producer pin required")
    for check in range(15):
        fresh=fetch(f"actions/runs/{run_id}")
        if str(fresh.get("id"))!=run_id or str(fresh.get("run_attempt"))!=attempt:
            raise ValueError("Automatic producer attempt changed")
        if fresh.get("status")=="completed":
            producer({"repository":{"full_name":REPO},"workflow_run":fresh},fresh)
            return int(run_id),int(attempt),source
        if check<14:pause(10)
    print("[NATIVE/AUTO][WAIT] original producer still finishing; no pinning or publication")
    return None

def main():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO
            or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        raise SystemExit("Canonical automatic release context required")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    selected=requested_producer(event,api)
    if selected is None:return
    run_id,attempt,requested_source=selected
    artifacts = []
    for page in range(1, 6):
        data = api(f"actions/runs/{run_id}/artifacts?per_page=100&page={page}")
        artifacts.extend(data.get("artifacts", []))
        if len(artifacts) >= data.get("total_count", 0):
            break
    else:
        raise SystemExit("Candidate artifact inventory exceeds bounded review")
    signed = signed_artifact(artifacts, run_id, attempt)
    if signed is None:
        print("[NATIVE/AUTO][NOOP] no signed candidate; no pinning, build or upload requested")
        return
    tiny = [a for a in artifacts if re.fullmatch(r"kyron-native-receipt-[0-9a-f]{40}", a.get("name", ""))
            and a.get("expired") is False]
    if len(tiny) > 1:
        raise SystemExit("Ambiguous candidate receipt")
    chosen = tiny[0] if tiny else signed
    small = bool(tiny)
    leaf = "native-candidate-receipt.json" if small else "native-candidate.json"
    source = source_pin(document(api(f"actions/artifacts/{chosen['id']}/zip", raw=True), leaf), run_id, attempt, small)
    if source is None:
        print("[NATIVE/AUTO][NOOP] candidate retained for validation/manual use; publication was not requested")
        return
    if requested_source is not None and requested_source!=source:
        raise SystemExit("Selected candidate differs from requested original compiled source")
    if small and tiny[0]["name"] != "kyron-native-receipt-" + source:
        raise SystemExit("Receipt name differs from original source")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write(f"ready=true\nsource_sha={source}\nrun_id={run_id}\nattempt={attempt}\n")
    print(f"[NATIVE/AUTO][SELECTED] original_source={source} producer={run_id}/{attempt}; signature verification still required")

if __name__ == "__main__":
    main()
