#!/usr/bin/env python3
"""Approve an original signed Native pair against the live signed index, then publish draft assets."""
import hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path("source").resolve()
ABIS=(("32","armeabi-v7a","libkyron","libkyroni"),("64","arm64-v8a","libkyron64","libkyroni64"))
LEAVES=("libkyron.so","libkyron.release.json","libkyron.so.kyron-finalized")
SHA40=re.compile(r"[0-9a-f]{40}\Z");SHA64=re.compile(r"[0-9a-f]{64}\Z")

def refuse(why):raise SystemExit("[NATIVE/APPROVE][BLOCKED] "+why)
def run(*args,env=None,visible=False):
    p=subprocess.run([str(a) for a in args],env=env,text=True,capture_output=not visible,timeout=180,check=False)
    if p.returncode:refuse(f"required command failed: {args[0]} rc={p.returncode}")
    return (p.stdout or "").strip()
def hashfile(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
    return h.hexdigest()
def verify_stage(source,receipt):
    if receipt.get("source_sha")!=source or receipt.get("verified") is not True or receipt.get("published") is not False:refuse("original signed receipt source/status invalid")
    digests={"32":receipt.get("sha32"),"64":receipt.get("sha64")}
    if not all(isinstance(v,str) and SHA64.fullmatch(v) for v in digests.values()):refuse("original signed digest invalid")
    for bits,abi,_,_ in ABIS:
        folder=ROOT/"VeraInternal/lib"/abi
        folder.mkdir(parents=True,exist_ok=True)
        for name in LEAVES:
            inp=Path("handoff/native")/abi/name
            dest=folder/name
            if not inp.is_file() or inp.is_symlink() or inp.stat().st_size==0:refuse("signed candidate input missing")
            if dest.exists() and (not dest.is_file() or hashfile(dest)!=hashfile(inp)):refuse("candidate destination differs")
            if not dest.exists():shutil.copyfile(inp,dest)
            if hashfile(dest)!=hashfile(inp):refuse("candidate changed in staging")
        if hashfile(folder/"libkyron.so")!=digests[bits]:refuse("candidate digest/provenance mismatch")
    return digests
def metadata(text,sha_pair):
    sys.path.insert(0,str(ROOT/"etc/publishing"))
    import lib_contract_rotation as lib
    config=lib.ini(text);loader=next((x for x in config if x.startswith("loader=")),None)
    if not loader:refuse("loader channels missing")
    for bits,_,_,_ in ABIS:
        for channel in ("release","insider"):
            if lib.need(config,"runtime.contract",f"{channel}_lib_sha256_{bits}")!=sha_pair[bits]:
                refuse("source contract differs from verified original pair")
    return {
        "generation":lib.num(lib.need(config,"client.policy","contract_generation")),
        "minimum_launcher_build":lib.num(lib.need(config,"client.policy","minimum_launcher_build")),
        "minimum_content_revision":lib.num(lib.need(config,"runtime.contract","minimum_content_revision")),
        "release_channel":lib.need(config,loader,"release_channel"),
        "insider_channel":lib.need(config,loader,"insider_channel")}
def assert_clean(source):
    if not SHA40.fullmatch(source) or os.environ.get("GITHUB_REPOSITORY")!="pvtkyron/pantry-core" or os.environ.get("GITHUB_REF")!="refs/heads/main" or os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch":refuse("canonical manual hosted source not selected")
    head=run("git","-C",ROOT,"rev-parse","HEAD")
    remote=run("git","-C",ROOT,"ls-remote","origin","refs/heads/main")
    if not remote.startswith(head+"\t"):refuse("Workspace source moved during Native approval")
    if run("git","-C",ROOT,"diff","--name-only","HEAD") or run("git","-C",ROOT,"diff","--cached","--name-only"):refuse("tracked source not clean")
    if head!=source:
        run("git","-C",ROOT,"merge-base","--is-ancestor",source,head)
        changes=set(run("git","-C",ROOT,"diff","--name-only",source,head).splitlines())
        if changes!={"Distribution/SrcVersion.ini","Shared/pantry_contract.hpp"}:
            refuse("Changed Workspace source is not strictly the preapproved two-file Native contract")
    return head
def rotate(source,pair):
    sys.path.insert(0,str(ROOT/"etc/publishing"));sys.path.insert(0,str(ROOT/"Distribution/tools"))
    import lib_contract_rotation as lib,opaque_paths
    config=ROOT/"Distribution/SrcVersion.ini";old=config.read_text(encoding="utf-8")
    current=run("git","-C",ROOT,"rev-parse","HEAD")
    preapproved=current!=source
    public=ROOT/"etc/security/signing/material/pantry-local-active/v1/content_public.pem"
    os.environ["KYRON_ROUTE_KEY_HEX"]=lib.need(lib.ini(old),"kyron.route","key_hex")
    try:
        signed,prev,core=lib.fetch_current_signed_baseline(old,ROOT,public,ROOT/"Distribution/tools",opaque_paths.opaque_path)
        revision=max(prev+1,int(time.time()*1000))
        plan=lib.plan(old,signed,pair,revision,prev,opaque_paths.opaque_path)
        if len(plan["changed"])!=4:refuse("all four native channel/ABI identities must rotate")
        print(f"[NATIVE/APPROVE][SIGNED-PLAN] core={core} revision={prev}->{revision} lanes=4 preapproved={preapproved}")
        if preapproved:
            if plan["source"]!=old:refuse("Preapproved dual-ABI metadata differs from independently authenticated rotation plan")
        else:
            run(sys.executable,ROOT/"etc/publishing/lib_contract_rotation.py","--workspace",ROOT,
                "--candidate-root",ROOT/"VeraInternal/lib","--online-current","--revision",revision,"--apply",visible=True)
    finally:os.environ.pop("KYRON_ROUTE_KEY_HEX",None)
    new=config.read_text(encoding="utf-8")
    if new!=plan["source"]:refuse("applied contract differs from independently signed plan")
    run(sys.executable,ROOT/"Distribution/tools/sync_consumer_contract.py","--config",config,
        "--output",ROOT/"Shared/pantry_contract.hpp","--check",visible=True)
    header=(ROOT/"Shared/pantry_contract.hpp").read_text(encoding="utf-8")
    if "This canonical contract is public metadata" not in header or "PANTRY_KYRON_ROUTE_KEY_CIPHER_BYTES" in header or lib.need(lib.ini(old),"kyron.route","key_hex") in header:
        refuse("generated public consumer contract leaks private routing material")
    metadata(new,pair)
    expected={"Distribution/SrcVersion.ini","Shared/pantry_contract.hpp"}
    if preapproved:
        if run("git","-C",ROOT,"diff","--name-only","HEAD"):refuse("Preapproved Workspace files changed during verification")
        if not run("git","-C",ROOT,"ls-remote","origin","refs/heads/main").startswith(current+"\t"):
            refuse("Already approved contract lost its original Workspace/main identity")
        print(f"[NATIVE/APPROVE][PRESERVED] verified preapproved Workspace source={current}, original compiled source={source}")
        return current
    if set(run("git","-C",ROOT,"diff","--name-only","HEAD").splitlines())!=expected:refuse("unexpected source modifications")
    run("git","-C",ROOT,"diff","--check")
    if not run("git","-C",ROOT,"ls-remote","origin","refs/heads/main").startswith(source+"\t"):refuse("Workspace main moved during approval")
    run("git","-C",ROOT,"config","user.name","kyron-native-approval")
    run("git","-C",ROOT,"config","user.email","117467541+pvtkyron@users.noreply.github.com")
    run("git","-C",ROOT,"add","--",*sorted(expected))
    run("git","-C",ROOT,"commit","-m",f"release(native): approve original signed ABI pair from {source[:12]}")
    approved=run("git","-C",ROOT,"rev-parse","HEAD")
    if not SHA40.fullmatch(approved) or approved==source:refuse("approval source commit invalid")
    run("git","-C",ROOT,"push","origin","HEAD:refs/heads/main",visible=True)
    if not run("git","-C",ROOT,"ls-remote","origin","refs/heads/main").startswith(approved+"\t"):refuse("approved main commit not visible")
    return approved
def manifest(source,pair):
    contract=metadata((ROOT/"Distribution/SrcVersion.ini").read_text(encoding="utf-8"),pair)
    runtime={}
    for bits,abi,release,insider in ABIS:
        src=ROOT/"VeraInternal/lib"/abi
        for stem,channel in ((release,"release"),(insider,"insider")):
            alias=stem+"-"+pair[bits][:24]+".so"
            runtime[alias]={"abi":abi,"channel":contract[channel+"_channel"],"sha256":pair[bits]}
            dest=ROOT/"Distribution/lib"/(stem+".so")
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and (not dest.is_file() or hashfile(dest)!=pair[bits]):refuse("existing Distribution ELF differs")
            if not dest.exists():shutil.copyfile(src/"libkyron.so",dest)
            if hashfile(dest)!=pair[bits]:refuse("staged ELF hash mismatch")
        for leaf in LEAVES[1:]:
            dest=ROOT/"Distribution/release/native-attestations"/abi/leaf
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and (not dest.is_file() or hashfile(dest)!=hashfile(src/leaf)):refuse("staged signed metadata differs")
            if not dest.exists():shutil.copyfile(src/leaf,dest)
    record={"schema":1,"workspace_sha":source,"source_workspace_sha":source,"mode":"all",
            "runtime":runtime,"contract":contract,"lib_policy":"current-release"}
    dst=ROOT/"Distribution/release/runtime-lane-v1.json"
    dst.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(record,separators=(",",":"),ensure_ascii=True)+"\n"
    if dst.exists() and dst.read_text(encoding="utf-8-sig")!=data:refuse("runtime delivery receipt already differs")
    if not dst.exists():dst.write_text(data,encoding="utf-8",newline="\n")
    if len(runtime)!=4:refuse("four signed runtime aliases required")
def publish(approved,pair):
    token=os.environ.get("SOURCE_TOKEN","").strip(" \r\n\t\ufeff")
    if not token or not token.isascii() or any(ord(x)<33 or ord(x)>126 for x in token):refuse("Workspace release credential rejected")
    env=os.environ.copy();env["GH_TOKEN"]=token
    run("pwsh","-NoLogo","-NoProfile","-NonInteractive","-File",
        ROOT/"etc/publishing/Publish-WorkspaceReleaseAssets.ps1","-Component","Lib",env=env,visible=True)
    releases=json.loads(run("gh","api","repos/pvtkyron/Workspace/releases?per_page=100",env=env))
    exact=[r for r in releases if r.get("draft") is True and
           r.get("name")=="Kyron local signed delivery "+approved[:12] and r.get("target_commitish")==approved]
    if len(exact)!=1:refuse("approved draft release identity invalid")
    assets={a.get("name"):a for a in exact[0].get("assets",[])}
    required={"runtime-lane-v1.json"}
    for bits,abi,_,_ in ABIS:
        required.update({"libkyron-"+abi+".so","libkyron-"+abi+".release.json","libkyron-"+abi+".so.kyron-finalized"})
        if assets.get("libkyron-"+abi+".so",{}).get("digest")!="sha256:"+pair[bits]:refuse("uploaded approved ELF hash mismatch")
    if not required.issubset(assets):refuse("draft release missing native signed assets")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as out:
            out.write(f"approved_workspace_sha={approved}\nrelease_id={exact[0]['id']}\n")
    print(f"[NATIVE/APPROVE][READY] source={approved} original_signed={os.environ['CANDIDATE_SOURCE_SHA']} release_id={exact[0]['id']} assets=7 draft=true")
def main():
    source=os.environ.get("CANDIDATE_SOURCE_SHA","")
    producer=os.environ.get("CANDIDATE_RUN_ID","")
    if not SHA40.fullmatch(source) or not re.fullmatch(r"[1-9][0-9]*",producer):refuse("input source/run pin invalid")
    assert_clean(source)
    receipt_path=Path(os.environ["RUNNER_TEMP"])/"kyron-native-receipt/native-candidate-receipt.json"
    if not receipt_path.is_file():refuse("signed original candidate proof not found")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("original_signed_candidate_run_id")!=int(producer):refuse("original signed run not bound")
    pair=verify_stage(source,receipt)
    host=ROOT/"VeraInternal/lib/host/AndroidReleaseHost.exe"
    if not host.is_file():refuse("canonical verifier not built")
    env=os.environ.copy();env["KYRON_CANONICAL_SIGNER_META"]=str(ROOT/"etc/security/signing/canonical-signer.json")
    run(host,"verify","--root",ROOT/"VeraInternal/lib","--abis","armeabi-v7a,arm64-v8a","--require-finalized",env=env,visible=True)
    approved=rotate(source,pair)
    manifest(source,pair)
    publish(approved,pair)
if __name__=="__main__":main()
