"""Fail-closed evidence check for a sealed, nonempty Java/D8 compiler handoff."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from workspace_lane_source import unchanged
SHA=re.compile(r"[0-9a-f]{40}\Z")
PROFILE="android-34-d8-34.0.0-jdk17-release"
DEX="Distribution/dist/InputHost.dex"
RECEIPT="Distribution/dist/InputHost.verified.json"
FIELDS={"schema","workspace_sha","dex_sha256","dex_bytes","profile","dex_source"}
def verify(source:Path,current:str,required:bool=False)->str|None:
    root=Path(source).resolve()
    if not SHA.fullmatch(current):raise ValueError("Current Workspace compiler source invalid")
    head=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],capture_output=True,text=True,timeout=25)
    if head.returncode or head.stdout.strip().lower()!=current:raise ValueError("Pinned Workspace source differs from Java compiler verification")
    dex,receipt=root/DEX,root/RECEIPT
    if not dex.exists() and not receipt.exists():
        if required:raise ValueError("Required Java DEX compiler handoff missing")
        return None
    if dex.is_symlink() or receipt.is_symlink() or not dex.is_file() or not receipt.is_file():raise ValueError("Java handoff missing, unpaired or redirected")
    try:record=json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError,UnicodeError,ValueError) as error:raise ValueError("Java handoff receipt malformed") from error
    if not isinstance(record,dict) or set(record)!=FIELDS:raise ValueError("Java compiler handoff inventory invalid")
    original=record.get("workspace_sha","")
    if (record.get("schema")!=1 or not isinstance(original,str) or not SHA.fullmatch(original) or
            record.get("profile")!=PROFILE or record.get("dex_source")!="dist/InputHost.dex" or
            type(record.get("dex_bytes")) is not int or not 64<=record["dex_bytes"]<=50*1024*1024 or
            not isinstance(record.get("dex_sha256"),str) or not re.fullmatch(r"[0-9a-f]{64}",record["dex_sha256"])):
        raise ValueError("Java compiler handoff source/profile/size invalid")
    if dex.stat().st_size!=record["dex_bytes"]:raise ValueError("Java DEX handoff length differs")
    with dex.open("rb") as stream:
        magic=stream.read(8)
        if not re.fullmatch(rb"dex\n[0-9]{3}\x00",magic):raise ValueError("Java DEX handoff header rejected")
        sha=hashlib.sha256();sha.update(magic)
        for block in iter(lambda:stream.read(1024*1024),b""):sha.update(block)
    if sha.hexdigest()!=record["dex_sha256"]:raise ValueError("Java DEX compiler digest differs")
    if not unchanged(root,original,current,"java"):raise ValueError("Original Java compiler source was changed or unverifiable")
    return record["dex_sha256"]
def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--current",required=True)
    p.add_argument("--require",action="store_true")
    p.add_argument("--github-env",type=Path)
    p.add_argument("--github-output",type=Path)
    a=p.parse_args()
    try:digest=verify(a.source,a.current,a.require)
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print("[JAVA/COMPILER-PROOF][REJECT] "+str(error));return 2
    if a.github_env:
        with a.github_env.open("a",encoding="utf-8") as env:
            env.write("KYRON_VERIFIED_PRECOMPILED_DEX="+("1" if digest else "0")+"\n")
            if digest:env.write("KYRON_VERIFIED_DEX_SHA256="+digest+"\n")
    if a.github_output:
        with a.github_output.open("a",encoding="utf-8") as output:
            output.write("reuse="+("true" if digest else "false")+"\n")
    print("[JAVA/COMPILER-PROOF]["+("PASS" if digest else "FALLBACK")+"] compiled_dex="+("authenticated" if digest else "unavailable; publisher must compile"))
    return 0
if __name__=="__main__":raise SystemExit(main())
