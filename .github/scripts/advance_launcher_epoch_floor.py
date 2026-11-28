#!/usr/bin/env python3
"""Advance only the hosted future-launch floor after a verified root publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

REPO="pvtkyron/pantry-core"
VARIABLE="KYRON_VERIFIED_MINIMUM_LAUNCH_EPOCH"
SHA40=re.compile(r"[0-9a-f]{40}\Z")
SHA64=re.compile(r"[0-9a-f]{64}\Z")
MAX=2**64-1

class ApiError(RuntimeError):
    def __init__(self,status):self.status=status;super().__init__("GitHub API status "+str(status))

def api(method,path,body=None):
    token=os.environ.get("GH_TOKEN","").strip(" \t\r\n\ufeff")
    if not token or not token.isascii() or any(ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError("canonical publication credential unavailable")
    wire=None if body is None else json.dumps(body,separators=(",",":")).encode()
    request=urllib.request.Request("https://api.github.com/"+path,data=wire,method=method,
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                 "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read(2*1024*1024+1)
        if len(data)>2*1024*1024:raise ValueError("publication response too large")
        return json.loads(data) if data else None
    except urllib.error.HTTPError as exc:raise ApiError(exc.code) from None

def positive(value):
    if not isinstance(value,str) or not re.fullmatch(r"[1-9][0-9]{0,19}",value):
        raise ValueError("verified epoch variable malformed")
    number=int(value)
    if number>MAX:raise ValueError("verified epoch variable overflow")
    return number

def advance(metadata,launcher,revision,source,request=api):
    if not SHA40.fullmatch(revision) or not SHA40.fullmatch(source):
        raise ValueError("immutable publication/source identity required")
    doc=json.loads(Path(metadata).read_text(encoding="utf-8-sig"))
    epoch=doc.get("launch_epoch")
    if (type(doc.get("schema")) is not int or doc.get("schema")!=1 or doc.get("product")!="KyronLauncher" or doc.get("architecture")!="x64"
            or type(epoch) is not int or not 0<epoch<MAX
            or not isinstance(doc.get("exe_sha256"),str) or not SHA64.fullmatch(doc["exe_sha256"])):
        raise ValueError("verified Launcher metadata rejected")
    image=Path(launcher)
    if image.is_symlink() or not image.is_file() or image.stat().st_size<65536:
        raise ValueError("verified Launcher image missing")
    digest=hashlib.sha256()
    with image.open("rb") as stream:
        if stream.read(2)!=b"MZ":raise ValueError("verified Launcher PE missing")
        stream.seek(0)
        for chunk in iter(lambda:stream.read(1048576),b""):digest.update(chunk)
    if digest.hexdigest()!=doc["exe_sha256"]:raise ValueError("published Launcher digest mismatch")
    commit=request("GET",f"repos/{REPO}/git/commits/{revision}")
    if (not isinstance(commit,dict) or commit.get("sha")!=revision or commit.get("parents")!=[]
            or ("Pantry-Source: "+source) not in str(commit.get("message","")).splitlines()
            or "History-Mode: root-only" not in str(commit.get("message","")).splitlines()):
        raise ValueError("verified root publication does not bind the source")
    endpoint=f"repos/{REPO}/actions/variables/{VARIABLE}"
    desired=epoch+1
    for _ in range(3):
        try:
            old=request("GET",endpoint)
            current=positive(old["value"])
            exists=True
        except ApiError as exc:
            if exc.status!=404:raise
            current=0;exists=False
        if current>=desired:return current,False
        try:
            request("PATCH" if exists else "POST",endpoint if exists else f"repos/{REPO}/actions/variables",
                    {"name":VARIABLE,"value":str(desired)})
        except ApiError as exc:
            if exc.status in (409,422):continue
            raise
        saved=positive(request("GET",endpoint)["value"])
        if saved>=desired:return saved,True
    raise ValueError("verified epoch floor did not persist")

def main():
    if (os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("GITHUB_REPOSITORY")!=REPO
            or os.environ.get("GITHUB_REF")!="refs/heads/main"):
        raise ValueError("canonical hosted publication context required")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata",required=True);parser.add_argument("--launcher",required=True)
    parser.add_argument("--revision",required=True);parser.add_argument("--source",required=True)
    args=parser.parse_args()
    floor,changed=advance(args.metadata,args.launcher,args.revision,args.source)
    print(f"[LAUNCH/EPOCH][{'ADVANCED' if changed else 'NOOP'}] verified future floor={floor}; installed state and signed binaries unchanged")
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except (ValueError,OSError,ApiError,KeyError,json.JSONDecodeError) as exc:
        print("[LAUNCH/EPOCH][BLOCKED] "+str(exc));raise SystemExit(1)
