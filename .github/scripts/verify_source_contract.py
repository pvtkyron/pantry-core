"""Check the canonical source projection without exposing private generator output."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def assess(workspace: Path) -> tuple[str, str]:
    command = [
        sys.executable, str(workspace / "Distribution/tools/sync_consumer_contract.py"),
        "--config", str(workspace / "Distribution/SrcVersion.ini"),
        "--output", str(workspace / "Shared/pantry_contract.hpp"), "--check",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError:
        return "error", "canonical contract generator could not start"
    if result.returncode == 0:
        return "ready", ""
    detail = result.stdout + "\n" + result.stderr
    if result.returncode == 1 and any(
        line.startswith("[CONTRACT][E] stale generated consumer header:")
        for line in detail.splitlines()
    ):
        return "pending", "generated consumer header is awaiting synchronization"
    if "runtime/pantry mapping drift" in detail:
        return "error", "runtime and packing routes disagree"
    if "missing/invalid" in detail or "section missing" in detail:
        return "error", "required contract configuration is missing or invalid"
    return "error", "canonical contract generator rejected the pinned source"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    status, reason = assess(args.workspace.resolve())
    pending = status == "pending"
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"pending={str(pending).lower()}\n")
    if status == "error":
        print(f"::error title=Source contract::{reason}")
        return 1
    if pending:
        print(f"[SOURCES][CONTRACT][WAIT] {reason}; release build and publication remain skipped")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write("Source projection synchronization is pending. Release build and publication are skipped.\n")
    else:
        print("[SOURCES][CONTRACT][OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
