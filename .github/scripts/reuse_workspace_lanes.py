"""Reuse compiler lanes when authenticated original inputs are unchanged.

Compilation and publication receipts are separate: a failed Doctor/publisher does
not invalidate a successful compiler lane. No receipt or source identity is edited.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import time
import zipfile

from release_policy import minimum_epoch
from workspace_lane_source import unchanged as scope_unchanged

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

REPO = "pvtkyron/pantry-core"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_ARCHIVE = 1024 * 1024 * 1024
COMMON = [".github/workflows/workspace-handoff.ps1", ".github/actions/private-capsule/"]
INPUTS = {
    "java": COMMON + [".github/workflows/workspace-java.yml"],
    "exe": COMMON + [".github/workflows/workspace-exe.yml", ".github/scripts/Invoke-HostedReleaseStep.ps1",
                     ".github/scripts/Restore-ApprovedNativeRuntime.ps1", ".github/scripts/Restore-FrozenBootstrap.ps1",
                     ".github/actions/pinned-toolchains/"],
}
INPUTS["delivery"] = sorted(set(INPUTS["java"] + INPUTS["exe"] + [
    ".github/workflows/workspace-native-approved.yml", ".github/workflows/workspace-prepare.yml",
    ".github/scripts/Seal-PreparedDelivery.ps1", ".github/scripts/release_policy.py",
    ".github/config/hosted-release-policy.json"]))


def recipe_fingerprint(tree, lane):
    if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
        raise ValueError("Complete build recipe tree required")
    rows = []
    for path in INPUTS[lane]:
        matches = [r for r in tree["tree"] if r.get("type") == "blob" and
                   (r.get("path", "").startswith(path) if path.endswith("/") else r.get("path") == path)]
        if not matches:
            raise ValueError("Required build recipe owner missing")
        rows += [(r["path"], r.get("mode"), r["sha"]) for r in matches]
    return hashlib.sha256(json.dumps(sorted(set(rows)), separators=(",", ":")).encode()).hexdigest()


def unpack_archive(archive_bytes, expected_digest, lane, source_sha, secret, runtime_channel="both", minimum_epoch=0, source_compatible=None):
    """Validate transport, HMAC and every inner file before accepting any reuse."""
    if not secret or not SHA.fullmatch(source_sha):
        raise ValueError("Reuse source/key missing")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_digest or ""):
        raise ValueError("Artifact transport digest missing")
    if not 1 <= len(archive_bytes) <= MAX_ARCHIVE or "sha256:" + hashlib.sha256(archive_bytes).hexdigest() != expected_digest:
        raise ValueError("Artifact transport digest mismatch")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as outer:
        entries = outer.infolist()
        files = [e for e in entries if not e.is_dir()]
        if len(entries) > 32 or len(files) != 1 or not re.fullmatch(r"kyron/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{28}\.bin", files[0].filename):
            raise ValueError("Encrypted lane inventory rejected")
        if files[0].file_size > MAX_ARCHIVE:
            raise ValueError("Encrypted lane too large")
        blob = outer.read(files[0])
    if len(blob) < 72 or blob[:8] != b"KYRONCI1" or (len(blob) - 56) % 16:
        raise ValueError("Lane envelope rejected")
    material = hashlib.sha512(("kyron-ci-handoff-v1\0" + secret).encode()).digest()
    if not hmac.compare_digest(hmac.digest(material[32:], blob[:-32], "sha256"), blob[-32:]):
        raise ValueError("Lane authentication rejected")
    decryptor = Cipher(algorithms.AES(material[:32]), modes.CBC(blob[8:24])).decryptor()
    padded = decryptor.update(blob[24:-32]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    payload = unpadder.update(padded) + unpadder.finalize()
    with zipfile.ZipFile(io.BytesIO(payload)) as inner:
        entries = inner.infolist()
        names = [e.filename for e in entries]
        file_names = [e.filename for e in entries if not e.is_dir()]
        if len(entries) > 8192 or len(names) != len(set(names)) or sum(e.file_size for e in entries) > MAX_ARCHIVE:
            raise ValueError("Lane payload inventory rejected")
        for entry in entries:
            name = entry.filename[:-1] if entry.is_dir() else entry.filename
            if (stat.S_ISLNK(entry.external_attr >> 16) or "\\" in name or
                    any(part in ("", ".", "..") for part in name.split("/")) or
                    (name != "handoff.json" and name != "source" and not name.startswith("source/")) or
                    (entry.is_dir() and (entry.file_size != 0 or name == "handoff.json"))):
                raise ValueError("Lane payload path rejected")
        manifest = json.loads(inner.read("handoff.json"))
        original=manifest.get("workspace_sha")
        if (manifest.get("schema"),manifest.get("lane"),manifest.get("pantry_sha"))!=(1,lane,original) or not isinstance(original,str) or not SHA.fullmatch(original):return False
        if original!=source_sha and (lane=="delivery" or source_compatible is None or not source_compatible(lane,original)):return False
        rows = manifest.get("files")
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("Lane file inventory missing")
        paths = [r.get("path") for r in rows]
        if len(paths) != len(set(paths)) or set(paths) != set(file_names) - {"handoff.json"}:
            raise ValueError("Lane payload differs from receipt")
        if not rows:
            if lane=="java":return False  # Old empty Java attestation is only a cache miss, never reusable.
            raise ValueError("Built lane cannot be empty")
        if lane == "java":
            root="source/Distribution/dist/"
            if set(file_names)-{"handoff.json"}!={root+"InputHost.dex",root+"InputHost.verified.json"}:
                raise ValueError("Java compiled handoff inventory rejected")
            receipt=json.loads(inner.read(root+"InputHost.verified.json"))
            dex=inner.read(root+"InputHost.dex")
            if (not isinstance(receipt,dict) or set(receipt)!={"schema","workspace_sha","dex_sha256","dex_bytes","profile","dex_source"} or
                    receipt.get("schema")!=1 or receipt.get("workspace_sha")!=original or receipt.get("profile")!="android-34-d8-34.0.0-jdk17-release" or
                    receipt.get("dex_source")!="dist/InputHost.dex" or type(receipt.get("dex_bytes")) is not int or
                    receipt["dex_bytes"]!=len(dex) or not 64<=len(dex)<=50*1024*1024 or
                    receipt.get("dex_sha256")!=hashlib.sha256(dex).hexdigest() or
                    not re.fullmatch(rb"dex\n[0-9]{3}\x00",dex[:8])):
                raise ValueError("Java compiled handoff content rejected")
        for row in rows:
            data = inner.read(row["path"])
            if type(row.get("size")) is not int or row["size"] != len(data) or row.get("sha256") != hashlib.sha256(data).hexdigest():
                raise ValueError("Lane file digest mismatch")
        if lane == "exe":
            root="source/Launcher/lib/x64/Release/local-machine-v1/"
            if root+"Launcher.exe" not in file_names or root+"Launcher.build.json" not in file_names:
                raise ValueError("Signed Launcher executable or metadata missing")
            meta=json.loads(inner.read(root+"Launcher.build.json"))
            epoch=meta.get("launch_epoch")
            if type(epoch) is not int or not 0<epoch<2**64:raise ValueError("Launcher epoch malformed")
            if meta.get("exe_sha256")!=hashlib.sha256(inner.read(root+"Launcher.exe")).hexdigest():
                raise ValueError("Signed Launcher manifest hash mismatch")
            if epoch<minimum_epoch:return False
        if lane == "delivery":
            runtime = json.loads(inner.read("source/Distribution/release/runtime-lane-v1.json"))
            metadata = json.loads(inner.read("source/Distribution/client/Launcher.build.json"))
            mode = "all" if runtime_channel == "both" else runtime_channel
            if runtime.get("mode") != mode:
                return False
            epoch = metadata.get("launch_epoch")
            if type(epoch) is not int or not 0 < epoch < 2**64:
                raise ValueError("Prepared Launcher epoch rejected")
            if epoch < minimum_epoch:
                return False
    return True


class ArtifactTransportUnavailable(Exception):
    """Only a transient, unverified cache ZIP transport failure; never a proof."""


class GitHub:
    def __init__(self):
        self.env = os.environ.copy()
        self.env["GH_TOKEN"] = os.environ.get("GH_TOKEN", "").strip(" \t\r\n\ufeff")
        if not self.env["GH_TOKEN"]:
            raise ValueError("Actions artifact credential missing")

    def bytes(self, path):
        archive = bool(re.fullmatch(r"actions/artifacts/[1-9][0-9]*/zip", path))
        attempts = 2 if archive else 3
        for attempt in range(attempts):
            try:
                result = subprocess.run(["gh", "api", f"repos/{REPO}/" + path], env=self.env,
                                        capture_output=True, timeout=130 if archive else 75)
            except subprocess.TimeoutExpired:
                transient = True
            else:
                if result.returncode == 0:
                    return result.stdout
                error = result.stderr[-2048:].decode("utf-8", "replace").lower()
                transient = any(reason in error for reason in (
                    "http 502", "http 503", "http 504", "tls handshake timeout",
                    "context deadline exceeded", "connection reset", "gateway timeout",
                    "bad gateway", "server error", "timeout", "temporarily unavailable"))
                if not transient:
                    raise ValueError("Authenticated Actions artifact read failed")
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
        if archive:
            raise ArtifactTransportUnavailable()
        raise ValueError("Authenticated Actions artifact read failed")

    def json(self, path):
        return json.loads(self.bytes(path))


def select_lanes(api, recipe_sha, source_sha, secret, current_run, include_launcher=True, runtime_channel="both", minimum_epoch=0, current_attempt=1, source_compatible=None, allow_delivery=True):
    if not SHA.fullmatch(recipe_sha) or not SHA.fullmatch(source_sha):
        raise ValueError("Immutable source pin required")
    trees = {recipe_sha: api.json(f"git/trees/{recipe_sha}?recursive=1")}
    wanted = (["delivery"] if allow_delivery else []) + ["java"] + (["exe"] if include_launcher else [])
    expected = {lane: recipe_fingerprint(trees[recipe_sha], lane) for lane in wanted}
    selected = {}
    runs = api.json("actions/runs?branch=main&per_page=50").get("workflow_runs", [])
    for run in runs:
        run_id, head = run.get("id"), run.get("head_sha", "")
        if (type(run_id) is not int or run_id <= 0 or not SHA.fullmatch(head) or
                run.get("head_branch") != "main" or run.get("path") not in (".github/workflows/patisserie.yml", ".github/workflows/launcher-publish.yml") or
                run.get("event") not in ("workflow_dispatch", "repository_dispatch", "schedule") or
                (run.get("repository") or {}).get("full_name") != REPO or
                (run.get("head_repository") or {}).get("full_name") != REPO):
            continue
        if head not in trees:
            trees[head] = api.json(f"git/trees/{head}?recursive=1")
        compatible = []
        for lane in wanted:
            if lane in selected:
                continue
            try:
                if recipe_fingerprint(trees[head], lane) == expected[lane]:
                    compatible.append(lane)
            except ValueError:
                continue  # Recipe predates this maintained owner.
        if not compatible:
            continue
        attempts = {}
        artifacts = api.json(f"actions/runs/{run_id}/artifacts?per_page=100").get("artifacts", [])
        for lane in compatible:
            suffix = {"java": "Compile Pantry Java + D8", "exe": "Compile signed Windows launcher",
                      "delivery": "Restore lanes + prepare private Pantry"}[lane]
            if lane == "delivery" and run.get("path") == ".github/workflows/launcher-publish.yml":
                suffix = "Compile signed Windows launcher"
            for artifact in artifacts:
                match = re.fullmatch(r"kyron-workspace-" + lane + "-" + str(run_id) + r"-([1-9][0-9]*)", artifact.get("name", ""))
                if not match or artifact.get("expired") is not False:
                    continue
                attempt = int(match[1])
                if run_id == current_run and attempt >= current_attempt:
                    continue
                if attempt not in attempts:
                    attempts[attempt] = api.json(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100").get("jobs", [])
                matching = []
                for job in attempts[attempt]:
                    if not job.get("name", "").endswith(" / " + suffix):
                        continue
                    verified_steps = {step.get("name") for step in job.get("steps", []) if step.get("conclusion") == "success"}
                    retained_compiler = lane == "exe" and {
                        "Compile and verify signed launcher lane", "Seal executable lane", "Upload encrypted executable lane"
                    }.issubset(verified_steps)
                    if job.get("conclusion") == "success" or retained_compiler:
                        matching.append(job)
                if not matching:
                    continue
                if lane == "delivery" and run.get("path") == ".github/workflows/launcher-publish.yml":
                    required = {"Seal prepared generated delivery for canonical publisher", "Upload encrypted prepared delivery"}
                    if not any(required.issubset({s.get("name") for s in j.get("steps", []) if s.get("conclusion") == "success"}) for j in matching):
                        continue
                if (type(artifact.get("id")) is not int or type(artifact.get("size_in_bytes")) is not int
                        or not 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE):
                    raise ValueError("Actions artifact identity rejected")
                try:
                    archive = api.bytes(f"actions/artifacts/{artifact['id']}/zip")
                except ArtifactTransportUnavailable:
                    print("[WORKSPACE/REUSE][CACHE_MISS] old artifact transport unavailable; no unverified output reused")
                    continue
                previous=[]
                def proof(chosen,original):
                    good=source_compatible is not None and source_compatible(chosen,original)
                    if good:previous.append(original)
                    return good
                try:
                    accepted=unpack_archive(archive,artifact.get("digest"),lane,source_sha,secret,runtime_channel,minimum_epoch,proof)
                except (ValueError,zipfile.BadZipFile,OSError):
                    # Previous artifacts are optional cache inputs. Never accept failed proof;
                    # compile a fresh signed lane instead of blocking the current release.
                    print("[WORKSPACE/REUSE][CACHE_MISS] invalid historical "+lane+" handoff; no bytes reused")
                    continue
                if accepted:
                    selected[lane]={"run_id":str(run_id),"attempt":match[1]}
                    if previous:selected[lane]["source_sha"]=previous[0]
                    if lane == "delivery":
                        return selected
                    break
        if all(lane in selected for lane in wanted):
            break
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe-sha", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--include-launcher", choices=("true", "false"), default="true")
    parser.add_argument("--runtime-channel", choices=("both", "release", "insider"), default="both")
    parser.add_argument("--minimum-epoch", type=int, default=0)
    args = parser.parse_args()
    try:
        if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != "refs/heads/main":
            raise ValueError("Canonical Actions owner required")
        args.minimum_epoch = minimum_epoch(args.minimum_epoch)
        if not 0 <= args.minimum_epoch < 2**64:
            raise ValueError("Launcher epoch floor rejected")
        api=GitHub()
        history=api.json("commits?sha=main&per_page=50")
        if not isinstance(history,list):raise ValueError("Authenticated publication history unavailable")
        markers=[re.search(r"(?m)^Pantry-Source: ([0-9a-f]{40})$",row.get("commit",{}).get("message","")) for row in history]
        marker=next((m for m in markers if m is not None),None)
        same_delivery=bool(marker and marker.group(1)==args.source_sha)
        def proof(lane,original):
            return scope_unchanged(os.environ.get("WORKSPACE_SOURCE_ROOT","source"),original,args.source_sha,lane)
        result=select_lanes(api,args.recipe_sha,args.source_sha,os.environ.get("KYRON_HANDOFF_SECRET",""),
                            int(os.environ["GITHUB_RUN_ID"]),args.include_launcher=="true",args.runtime_channel,args.minimum_epoch,
                            int(os.environ.get("GITHUB_RUN_ATTEMPT","1")),proof,same_delivery)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            for lane in ("delivery", "java", "exe"):
                for field in ("run_id", "attempt", "source_sha"):
                    output.write(f"{lane}_{field}={result.get(lane, {}).get(field, '')}\n")
        print("[WORKSPACE/REUSE][OK] " + " ".join(lane + "=" + str(lane in result).lower() for lane in ("delivery", "java", "exe")))
        print("[WORKSPACE/REUSE][INPUT-PROOF] cross_source_compilers="+str(sum(bool(result.get(x,{}).get("source_sha")) for x in ("java","exe"))))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        # Exception values from downloaded data or the CLI never enter logs.
        safe = {
            "Artifact transport digest missing": "transport-digest-missing",
            "Artifact transport digest mismatch": "transport-digest-mismatch",
            "Encrypted lane inventory rejected": "outer-inventory",
            "Lane envelope rejected": "envelope-format",
            "Lane authentication rejected": "authentication",
            "Lane payload inventory rejected": "payload-inventory",
            "Lane payload path rejected": "payload-path",
            "Lane file inventory missing": "manifest-inventory",
            "Lane payload differs from receipt": "manifest-mismatch",
            "Lane file digest mismatch": "file-digest",
            "Authenticated Actions artifact read failed": "artifact-read",
            "Complete build recipe tree required": "recipe-tree",
            "Required build recipe owner missing": "recipe-owner",
        }.get(str(error),type(error).__name__)
        print("::error::Workspace reuse proof rejected reason=" + safe + "; no compiler or publication receipt was advanced")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

