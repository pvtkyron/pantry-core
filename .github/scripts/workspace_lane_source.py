"""Prove signed original compiler inputs are unchanged at the pinned Workspace HEAD."""
from __future__ import annotations
import argparse,ast,json,re,subprocess
from pathlib import Path
SHA=re.compile(r"[0-9a-f]{40}\Z")
POLICY=Path(__file__).resolve().parent.parent/"config/workspace-lane-inputs.json"
# The CDN publisher never participates in either Java preflight or signed EXE compilation.
# Its own publication and resource-integrity tests still run on every relevant release.
NON_COMPILER_PUBLISHER="Distribution/tools/kyron_pipeline.py"
def protected_paths(lane, workspace=None):
    policy=json.loads(POLICY.read_text(encoding="utf-8"))
    if policy.get("schema")!=1 or not isinstance(policy.get("lanes"),dict) or set(policy["lanes"])!={"java","exe"} or lane not in ("java","exe"):raise ValueError("Compiler lane input policy rejected")
    for scope in policy["lanes"].values():
        if (not isinstance(scope,list) or not 1<=len(scope)<=64 or len(set(scope))!=len(scope) or
            any(not isinstance(p,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",p) or any(x in (".","..") for x in p.split("/")) or p in ("etc","Distribution") for p in scope)):raise ValueError("Compiler lane input paths rejected")
    paths=policy["lanes"][lane]
    if lane=="exe" and workspace is not None:
        gate=Path(workspace)/"etc/devtools/KyronReleaseGate.py"
        if not gate.is_file() or gate.is_symlink():raise ValueError("Canonical Launcher compiler input inventory missing")
        syntax=ast.parse(gate.read_text(encoding="utf-8"))
        source_nodes=[n.value for n in syntax.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SOURCES" for t in n.targets)]
        if len(source_nodes)!=1:raise ValueError("Launcher gate source inventory ambiguous")
        required=ast.literal_eval(source_nodes[0])
        if (not isinstance(required,(tuple,list)) or not required or
            any(not isinstance(s,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*",s) or
                not any(s==p or s.startswith(p+"/") for p in paths) for s in required)):
            raise ValueError("Launcher gate input missing from signed reuse scope")
        if any(NON_COMPILER_PUBLISHER==s or NON_COMPILER_PUBLISHER.startswith(s+"/") for s in required):
            raise ValueError("Publisher now tracked by Launcher compiler; exclusion withdrawn")
    # An exact Git exclusion applies only to this known publisher file, not all tools.
    return [*paths,":(top,exclude)"+NON_COMPILER_PUBLISHER]
def git(root,*args,timeout=65):return subprocess.run(["git","-C",str(root),*args],capture_output=True,timeout=timeout)
def unchanged(workspace,original,current,lane):
    if not SHA.fullmatch(original) or not SHA.fullmatch(current):return False
    root=Path(workspace)
    try:paths=protected_paths(lane,root)
    except (OSError,ValueError,SyntaxError):return False
    head=git(root,"rev-parse","HEAD")
    if head.returncode or head.stdout.decode().strip().lower()!=current:return False
    if original==current:return True
    if git(root,"cat-file","-e",original+"^{commit}").returncode:
        if git(root,"fetch","--quiet","--no-tags","--filter=blob:none","origin",original,timeout=95).returncode:return False
    ancestor=git(root,"merge-base","--is-ancestor",original,current)
    if ancestor.returncode and git(root,"rev-parse","--is-shallow-repository").stdout.strip()==b"true":
        if git(root,"fetch","--quiet","--no-tags","--filter=blob:none","--deepen=256","origin","main",timeout=95).returncode:return False
        ancestor=git(root,"merge-base","--is-ancestor",original,current)
    if ancestor.returncode:return False
    return git(root,"diff","--quiet","--no-renames",original,current,"--",*paths).returncode==0
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("workspace","original","current"):p.add_argument("--"+name,required=True)
    p.add_argument("--lane",choices=("java","exe"),required=True);a=p.parse_args()
    try:okay=unchanged(a.workspace,a.original,a.current,a.lane)
    except (OSError,ValueError,subprocess.TimeoutExpired):okay=False
    if not okay:print("[WORKSPACE/INPUT-PARITY][REJECT] original compiler inputs not proved");return 2
    print("[WORKSPACE/INPUT-PARITY][OK] lane="+a.lane+" original="+a.original[:12]+" current="+a.current[:12]);return 0
if __name__=="__main__":raise SystemExit(main())
