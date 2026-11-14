#!/usr/bin/env python3
"""Keep generated route state encrypted in Core artifacts, never in Workspace Git."""
from __future__ import annotations
import argparse,hashlib,io,json,os,re,subprocess,sys,zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO="pvtkyron/pantry-core"
MAGIC=b"KYRON-ROUTE-STATE-V1\0"
LIMIT=1024*1024
HEX=re.compile(r"[0-9a-f]{40}")
PRODUCERS={".github/workflows/pantry-mirror.yml",".github/workflows/pantry-delta.yml"}

def require(ok,message):
    if not ok:raise ValueError(message)

def key():
    secret=os.environ.get("PANTRY_ROUTE_STATE_KEY","")
    require(bool(secret.strip()),"route state encryption key unavailable")
    return hashlib.sha256(MAGIC+secret.encode()).digest()

def output(**values):
    target=os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target,"a",encoding="utf-8") as stream:
            for name,value in values.items():print(f"{name}={value}",file=stream)

def git(root,*args):
    p=subprocess.run(["git","-C",str(root),*args],capture_output=True,check=True)
    return p.stdout.decode().strip()

def api(path,binary=False):
    p=subprocess.run(["gh","api",f"repos/{REPO}/{path}"],capture_output=True,check=True)
    require(len(p.stdout)<=4*LIMIT,"route state response oversized")
    return p.stdout if binary else json.loads(p.stdout)

def source_bytes(state,source):
    require(HEX.fullmatch(source) is not None,"route state source rejected")
    require(0<len(state)<=LIMIT,"route state size rejected")
    text=state.decode("utf-8")
    require(text.startswith("; Pantry-Source: "+source+"\n"),"route state source pin rejected")
    require("[runtime.contract]" in text and "[launch.contract]" in text,"route state contract incomplete")
    return text

def core_identity(core,source):
    require(HEX.fullmatch(source) is not None,"published source rejected")
    pins=re.findall(r"^Pantry-Source: ([0-9a-f]{40})$",git(core,"log","-50","--format=%B","HEAD"),re.M)
    require(bool(pins) and pins[0]==source,"route state does not match published Core source")
    tree=git(core,"rev-parse","HEAD:kyron")
    require(HEX.fullmatch(tree) is not None,"published Kyron tree rejected")
    return tree

def seal(state,source,tree):
    text=source_bytes(state,source)
    require(HEX.fullmatch(tree) is not None,"route state tree rejected")
    plain=json.dumps({"schema":1,"repository":REPO,"source":source,"kyron_tree":tree,"state":text},
                     separators=(",",":")).encode()
    nonce=os.urandom(12)
    return MAGIC+nonce+AESGCM(key()).encrypt(nonce,plain,MAGIC)

def open_state(wire,source,tree):
    require(len(wire)<=2*LIMIT and wire.startswith(MAGIC),"route state envelope rejected")
    start=len(MAGIC)
    plain=AESGCM(key()).decrypt(wire[start:start+12],wire[start+12:],MAGIC)
    doc=json.loads(plain)
    require(doc.get("schema")==1 and doc.get("repository")==REPO and doc.get("source")==source
            and doc.get("kyron_tree")==tree,"route state publication binding rejected")
    state=doc["state"].encode()
    source_bytes(state,source)
    return state

def admit(artifact,run,source):
    require(artifact.get("name")=="kyron-route-state-"+source and artifact.get("expired") is False,
            "route state artifact identity rejected")
    require(run.get("id")==artifact.get("workflow_run",{}).get("id") and
            run.get("repository",{}).get("full_name")==REPO and
            run.get("head_repository",{}).get("full_name")==REPO and
            run.get("head_branch")=="main" and run.get("path") in PRODUCERS and
            run.get("event") in ("workflow_dispatch","repository_dispatch") and
            run.get("status")=="completed" and run.get("conclusion")=="success",
            "route state producer rejected")

def archive(wire):
    require(len(wire)<=2*LIMIT,"route state archive oversized")
    with zipfile.ZipFile(io.BytesIO(wire)) as z:
        members=z.infolist()
        require(len(members)==1 and members[0].filename=="route-state.enc" and
                members[0].file_size<=2*LIMIT and not members[0].is_dir(),
                "route state archive members rejected")
        return z.read(members[0])

def write_state(root,state):
    root=root.resolve(strict=True)
    folder=root/"release";target=folder/"pantry-core-route-state.ini"
    require(not folder.is_symlink() and not target.is_symlink(),"route state destination redirected")
    require(target.resolve().is_relative_to(root),"route state destination escaped source")
    if target.exists():
        require(target.read_bytes()==state,"existing different route state preserved")
        return
    folder.mkdir(exist_ok=True)
    # Exclusive creation preserves a concurrent writer and every other source file.
    with target.open("xb") as stream:stream.write(state)

def capture(root,source,core,destination):
    root=root.resolve(strict=True)
    require(git(root,"rev-parse","HEAD")==source,"route state Workspace source moved")
    require(root.name=="Distribution" and root.parent==Path(git(root,"rev-parse","--show-toplevel")).resolve(),
            "route state requires integrated Distribution")
    state=root/"release/pantry-core-route-state.ini"
    require(not state.is_symlink() and state.resolve().is_relative_to(root),"route state source redirected")
    tree=core_identity(core,source)
    wire=seal(state.read_bytes(),source,tree)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(wire)
    output(sealed_path=str(destination.resolve()))
    print("[PANTRY/ROUTE-STATE][SEALED] generated state retained without a Workspace commit")

def restore(root,source,core):
    tree=core_identity(core,source)
    name="kyron-route-state-"+source
    result=api("actions/artifacts?name="+name+"&per_page=100")
    artifacts=sorted((a for a in result.get("artifacts",[]) if a.get("name")==name and not a.get("expired")),
                     key=lambda a:a["id"],reverse=True)
    for artifact in artifacts:
        run=api("actions/runs/"+str(artifact["workflow_run"]["id"]))
        # Failed or unfinished producers never supply the next publication's baseline.
        if run.get("status")!="completed" or run.get("conclusion")!="success":continue
        admit(artifact,run,source)
        state=open_state(archive(api("actions/artifacts/"+str(artifact["id"])+"/zip",True)),source,tree)
        write_state(root,state)
        output(ready="true",full_required="false")
        print("[PANTRY/ROUTE-STATE][RESTORED] exact published source and Kyron tree authenticated")
        return True
    output(ready="false",full_required="true")
    print("[PANTRY/ROUTE-STATE][WAIT] no completed encrypted baseline; one canonical full preparation required")
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("capture","restore"))
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--core-root",type=Path,default=Path("shelf"))
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    if a.mode=="capture":
        require(a.output is not None,"sealed route state output required")
        capture(a.source_root,a.source_sha,a.core_root,a.output)
    else:restore(a.source_root,a.source_sha,a.core_root)
if __name__=="__main__":
    try:main()
    except Exception:
        # The plaintext contract and encryption credential never enter public logs.
        print("::error::Authenticated route state checkpoint rejected",file=sys.stderr)
        sys.exit(1)
