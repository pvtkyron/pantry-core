#!/usr/bin/env python3
"""Source-bound read-only proof of completed KyronLink Android validation."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = "pvtkyron/pantry-core"

# Keep every test/toolchain/Launcher input protected. Only the independent
# Native owner and its two contract projection files may reuse this proof.
VALIDATION_INPUTS = ['.', ':(top,exclude)VeraInternal/**',
                     ':(top,exclude)Distribution/SrcVersion.ini',
                     ':(top,exclude)Shared/pantry_contract.hpp']
VALIDATION_RECIPE = ['.github/workflows/workspace-powershell-regression.yml']

def get_json(url, token):
    from native_release_ready import fetch_json
    return fetch_json(url, token)

def same_validation_inputs(workspace, original, current):
    from workspace_input_key import tree
    check=subprocess.run(['git','-C',str(workspace),'merge-base','--is-ancestor',original,current],capture_output=True,timeout=60)
    if check.returncode==1:return False
    if check.returncode:raise ValueError('KyronLink original validation ancestry unavailable')
    return tree(workspace,original,VALIDATION_INPUTS)==tree(workspace,current,VALIDATION_INPUTS)

def previously_validated(sha, token, workspace=None, recipe=None):
    name = "kyronlink-validation-" + sha
    prefix = f"https://api.github.com/repos/{REPO}"
    listing = get_json(prefix + "/actions/artifacts?per_page=100&name=" + name, token)
    candidates=list(listing.get("artifacts", []))
    if workspace and recipe:
        seen={item.get('id') for item in candidates}
        for page in range(1,4):
            rows=get_json(prefix+f'/actions/artifacts?per_page=100&page={page}',token).get('artifacts',[])
            candidates.extend(row for row in rows if row.get('id') not in seen and
                re.fullmatch(r'kyronlink-validation-[0-9a-f]{40}',row.get('name','')))
            seen.update(row.get('id') for row in rows)
            if len(rows)<100:break
    for artifact in sorted(candidates, key=lambda x: x.get("created_at", ""), reverse=True):
        original_name=artifact.get('name','')
        if not re.fullmatch(r'kyronlink-validation-[0-9a-f]{40}',original_name) or artifact.get("expired") is not False:
            continue
        original=original_name[len('kyronlink-validation-'):]
        if original!=sha and not (workspace and recipe):continue
        info = artifact.get("workflow_run") or {}
        run_id = info.get("id")
        if (not isinstance(run_id, int) or run_id <= 0 or info.get("head_branch") != "main"
                or info.get("repository_id") != info.get("head_repository_id")
                or not isinstance(artifact.get("size_in_bytes"), int)
                or not 0 < artifact["size_in_bytes"] <= 8192):
            raise ValueError("KyronLink validation artifact identity rejected")
        run = get_json(prefix + f"/actions/runs/{run_id}", token)
        if ((run.get("repository") or {}).get("full_name") != REPO or run.get("head_branch") != "main"
                or run.get("status") != "completed" or run.get("conclusion") != "success"
                or run.get("event") != "repository_dispatch"
                or run.get("path") != ".github/workflows/workspace-powershell-regression.yml"):
            continue
        if recipe:
            from workspace_input_key import tree
            public_source=run.get('head_sha','')
            if not re.fullmatch(r'[0-9a-f]{40}',public_source):
                raise ValueError('KyronLink validation recipe source rejected')
            if tree(recipe,public_source,VALIDATION_RECIPE)!=tree(recipe,'HEAD',VALIDATION_RECIPE):continue
        if original!=sha and not same_validation_inputs(workspace,original,sha):continue
        jobs = get_json(prefix + f"/actions/runs/{run_id}/jobs?per_page=100", token).get("jobs", [])
        android = [j for j in jobs if j.get("name") == "Kyron Link Java, D8, Mundo and network behavior"
                   and j.get("conclusion") == "success"]
        if len(android) != 1:
            continue
        steps = {s.get("name"): s.get("conclusion") for s in android[0].get("steps", [])}
        if any(steps.get(n) != "success" for n in (
                "Run actual Android builds and network behavior without skips",
                "Prepare exact KyronLink source validation receipt",
                "Preserve small KyronLink validation receipt")):
            continue
        with tempfile.TemporaryDirectory(prefix="kyronlink-validation-") as scratch:
            env = os.environ.copy()
            env["GH_TOKEN"] = token
            result = subprocess.run(
                ["gh", "run", "download", str(run_id), "-R", REPO, "-n", original_name, "-D", scratch],
                env=env, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise ValueError("KyronLink validation receipt download rejected")
            files = list(Path(scratch).rglob("*"))
            if len(files) != 1 or files[0].name != "kyronlink-validation.json" or not files[0].is_file():
                raise ValueError("KyronLink receipt archive inventory rejected")
            receipt = json.loads(files[0].read_text(encoding="utf-8"))
            if (receipt.get("schema") != 1 or receipt.get("workspace_sha") != original
                    or receipt.get("producer_run_id") != run_id or receipt.get("validated") is not True
                    or receipt.get("published") is not False):
                raise ValueError("KyronLink receipt content or source pin rejected")
            if original!=sha:
                print(f'[KYRONLINK/VALIDATION][REUSED] original_source={original} current_source={sha}; protected input trees and recipe unchanged; original receipt retained')
            return True
    return False

def main():
    token = os.environ.get("GH_TOKEN", "").strip(" \t\r\n\ufeff")
    sha = os.environ.get("WORKSPACE_SHA", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or not re.fullmatch("[0-9a-f]{40}", sha) or not token or not token.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in token)):
        raise SystemExit("KyronLink authenticated receipt lookup rejected")
    checked = previously_validated(sha, token, os.environ.get("KYRONLINK_WORKSPACE_ROOT"), os.environ.get("KYRONLINK_RECIPE_ROOT"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"validated={str(checked).lower()}\n")
    print(f"[KYRONLINK/VALIDATION][{'NOOP' if checked else 'REQUIRED'}] source={sha} previous_verified={str(checked).lower()}")

if __name__ == "__main__":
    main()
