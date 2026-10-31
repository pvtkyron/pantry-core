"""Fingerprint canonical tracked compiler inputs without changing the Git index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

NATIVE_RECIPE = [
    '.github/workflows/workspace-lib.yml', '.github/workflows/workspace-handoff.ps1',
    '.github/actions/private-capsule', '.github/scripts/Invoke-HostedReleaseStep.ps1',
    '.github/scripts/workspace_input_key.py',
]

def git(root, *args, data=None):
    result=subprocess.run(['git','-C',str(root),*args],input=data,capture_output=True,timeout=60)
    if result.returncode:raise ValueError('Compiler input inspection failed')
    return result.stdout

def tree(root, revision, specs):
    if not isinstance(specs,list) or not specs or any(not isinstance(s,str) or not s or '\0' in s or '\n' in s for s in specs):
        raise ValueError('Canonical compiler pathspecs missing')
    empty=git(root,'hash-object','-w','-t','tree','--stdin',data=b'').decode().strip()
    selected=set(git(root,'diff-tree','--no-renames','-r','--name-only','-z','--no-commit-id',empty,revision,'--',*specs).split(b'\0'))
    rows=[]
    for record in git(root,'ls-tree','--full-tree','-r','-z',revision).split(b'\0'):
        if record:
            header,path=record.split(b'\t',1)
            if path in selected:rows.append((path,header))
    if not rows:raise ValueError('Compiler input tree is empty')
    digest=hashlib.sha256(b'kyron-compiler-input-tree-v1\0')
    for path,header in sorted(rows):digest.update(header+b'\t'+path+b'\0')
    return digest.hexdigest()

def fingerprint(workspace, recipe, specs):
    parts=[tree(workspace,'HEAD',specs),tree(recipe,'HEAD',NATIVE_RECIPE)]
    return hashlib.sha256(('kyron-native-input-key-v1\0'+'\0'.join(parts)).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True);p.add_argument('--recipe',required=True);p.add_argument('--specs-json',type=Path,required=True)
    a=p.parse_args()
    value=fingerprint(a.workspace,a.recipe,json.loads(a.specs_json.read_text(encoding='utf-8-sig')))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as out:out.write('inputs_sha256='+value+'\n')
    print('[COMPILER/INPUTS][OK] canonical Git content and public build recipe fingerprinted; index unchanged')
if __name__=='__main__':main()
