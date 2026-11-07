"""Restore authenticated generated delivery outputs into a pinned source checkout."""
import argparse
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import zipfile

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

LIMIT = 1024 * 1024 * 1024
FIXED = {
    "client/Launcher.exe", "client/Launcher.build.json", "client/Kyron.release-set.json",
    "client/Bootstrap.exe", "client/Bootstrap.release.json",
    "release/bootstrap-v10.marker", "release/bootstrap-delivery-v1.json",
    "release/launcher-lane-v1.json", "release/runtime-lane-v1.json",
    "release/delivery-provenance-v1.json",
    *(f"lib/{name}" for name in ("libkyron.so", "libkyron64.so", "libkyroni.so", "libkyroni64.so")),
    *(f"release/native-attestations/{abi}/{name}" for abi in ("armeabi-v7a", "arm64-v8a")
      for name in ("libkyron.release.json", "libkyron.so.kyron-finalized")),
}

def allowed(path):
    prefix = "source/Distribution/"
    if not isinstance(path, str) or not path.startswith(prefix):
        return False
    logical = path[len(prefix):]
    parts = PurePosixPath(logical).parts
    if not logical or "\\" in logical or "//" in logical or any(p in ("", ".", "..") for p in logical.split("/")):
        return False
    return logical in FIXED or bool(re.fullmatch(
        r"client/(?:runtime/[0-9a-f]{32}/[A-Za-z0-9._/-]+|tools/(?:commanders|android|xray)/[A-Za-z0-9._/-]+)", logical
    ))

def restore(blob_path, source, expected_sha, secret):
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha) or not secret:
        raise ValueError("delivery identity/key unavailable")
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != expected_sha:
        raise ValueError("delivery source checkout differs from pin")
    if not 72 <= blob_path.stat().st_size <= LIMIT:
        raise ValueError("delivery envelope size rejected")
    blob = blob_path.read_bytes()
    if blob[:8] != b"KYRONCI1" or (len(blob) - 56) % 16:
        raise ValueError("delivery envelope rejected")
    material = hashlib.sha512(("kyron-ci-handoff-v1\0" + secret).encode()).digest()
    if not hmac.compare_digest(hmac.digest(material[32:], blob[:-32], "sha256"), blob[-32:]):
        raise ValueError("delivery authentication failed")
    decryptor = Cipher(algorithms.AES(material[:32]), modes.CBC(blob[8:24])).decryptor()
    padded = decryptor.update(blob[24:-32]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    with zipfile.ZipFile(io.BytesIO(plain)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 512 or len(names) != len(set(names)) or sum(e.file_size for e in entries) > LIMIT:
            raise ValueError("delivery archive inventory rejected")
        for entry in entries:
            if entry.is_dir() or (entry.filename != "handoff.json" and not allowed(entry.filename)):
                raise ValueError("delivery archive path rejected")
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or entry.file_size > 100 * 1024 * 1024:
                raise ValueError("delivery archive entry rejected")
        manifest = json.loads(archive.read("handoff.json"))
        if (manifest.get("schema"), manifest.get("lane"), manifest.get("workspace_sha"), manifest.get("pantry_sha")) != (1, "delivery", expected_sha, expected_sha):
            raise ValueError("delivery provenance differs from source pin")
        rows = manifest.get("files")
        if not isinstance(rows, list) or not rows or len(rows) > 511:
            raise ValueError("delivery file inventory missing")
        paths = [row.get("path") for row in rows]
        if any(not allowed(path) for path in paths) or len(paths) != len(set(paths)) or set(paths) != set(names) - {"handoff.json"}:
            raise ValueError("delivery file inventory differs from archive")
        source = source.resolve()
        for row in rows:
            relative = row["path"][len("source/"):]
            destination = source.joinpath(*PurePosixPath(relative).parts)
            if not destination.resolve().is_relative_to(source):
                raise ValueError("delivery destination escaped source checkout")
            if subprocess.run(["git", "-C", str(source), "check-ignore", "--quiet", "--", relative]).returncode != 0:
                raise ValueError("delivery may restore only ignored generated outputs")
            data = archive.read(row["path"])
            if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("delivery file digest mismatch")
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("delivery destination contains different data")
        for row in rows:
            destination = source.joinpath(*PurePosixPath(row["path"][len("source/"):]).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                with archive.open(row["path"]) as stream, destination.open("xb") as output:
                    shutil.copyfileobj(stream, output)
    print("[HOSTED/DELIVERY][RESTORED] authenticated generated outputs; original lane receipts retained")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    restore(args.input, args.source, args.source_sha, os.environ.get("KYRON_HANDOFF_SECRET", ""))

if __name__ == "__main__":
    main()
