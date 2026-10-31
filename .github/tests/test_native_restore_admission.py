"""Run actual PowerShell CheckOnly admission against real disposable Git trees."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
PWSH=shutil.which('pwsh')
GIT=shutil.which('git')

@unittest.skipUnless(PWSH and GIT and os.name=='posix','Linux hosted PowerShell and Git required')
class NativeRestoreAdmission(unittest.TestCase):
    def test_unchanged_ready_changed_wait_and_approved_transition(self):
        with tempfile.TemporaryDirectory(prefix='native-restore-admission-') as raw:
            case=Path(raw);source=case/'source';source.mkdir();binroot=case/'bin';binroot.mkdir()
            def git(*args):return subprocess.check_output([GIT,'-C',str(source),*args],text=True,stderr=subprocess.DEVNULL).strip()
            git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            git('remote','add','origin','https://github.com/pvtkyron/Workspace')
            (source/'Distribution').mkdir();(source/'etc/build').mkdir(parents=True)
            pins={'32':'a'*64,'64':'b'*64}
            (source/'Distribution/SrcVersion.ini').write_text(''.join(f'{channel}_lib_sha256_{bits}={digest}\n' for bits,digest in pins.items() for channel in ('release','insider')))
            (source/'etc/build/workspace-common.ps1').write_text("function Get-WorkspaceNativeReleasePathspecs { return @('Native.cpp','Distribution/SrcVersion.ini','etc/build/workspace-common.ps1') }\n")
            (source/'Native.cpp').write_text('approved native input\n');git('add','.');git('commit','-qm','approved')
            target=git('rev-parse','HEAD')
            assets=[{'name':'runtime-lane-v1.json','state':'uploaded','size':100}]
            for bits,abi in (('32','armeabi-v7a'),('64','arm64-v8a')):
                for suffix in ('so','release.json','so.kyron-finalized'):
                    assets.append({'name':f'libkyron-{abi}.{suffix}','state':'uploaded','size':100,'digest':'sha256:'+pins[bits]})
            catalog=case/'catalog.json'
            wrapper=binroot/'git'
            wrapper.write_text('#!/usr/bin/env python3\nimport os,sys\na=sys.argv[1:]\nif "fetch" in a: sys.exit(0)\nif "http.https://github.com/.extraheader" in a:\n print("AUTHORIZATION: basic '+base64.b64encode(b'fixture:synthetic-only').decode()+'");sys.exit(0)\nos.execv('+repr(GIT)+',['+repr(GIT)+']+a)\n');wrapper.chmod(0o755)
            worker=case/'worker.ps1'
            worker.write_text('''param([string]$Owner,[string]$Source,[string]$Catalog)
$ErrorActionPreference='Stop'
$global:fixtureReleaseCatalog=@(Get-Content -LiteralPath $Catalog -Raw|ConvertFrom-Json)
function Invoke-RestMethod { return ,$global:fixtureReleaseCatalog }
& $Owner -SourceRoot $Source -ExpectedRepository 'pvtkyron/Workspace' -CheckOnly
if(!$?){throw 'Actual CheckOnly owner failed'}
# Match GitHub Actions' PowerShell epilogue, including native exit status.
if(Test-Path variable:LASTEXITCODE){exit $LASTEXITCODE}
''')
            def check(pending):
                catalog.write_text(json.dumps([{'target_commitish':target,'assets':assets}]))
                output=case/'output';output.write_text('')
                env=os.environ|{'PATH':str(binroot)+os.pathsep+os.environ['PATH'],'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'pvtkyron/pantry-core','GITHUB_REF':'refs/heads/main','GITHUB_OUTPUT':str(output),'RUNNER_TEMP':raw}
                result=subprocess.run([PWSH,'-NoLogo','-NoProfile','-NonInteractive','-File',str(worker),str(ROOT/'.github/scripts/Restore-ApprovedNativeRuntime.ps1'),str(source),str(catalog)],env=env,capture_output=True,text=True,timeout=45)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(output.read_text().strip(),'pending='+str(pending).lower())
                self.assertIn('[WAIT]' if pending else '[READY]',result.stdout)
            document=yaml.safe_load((ROOT/'.github/workflows/source-pin-component.yml').read_text())
            checkout=next(step['with'] for step in document['jobs']['pin']['steps']
                          if step.get('with',{}).get('path')=='workspace')
            git('sparse-checkout','init','--no-cone')
            sparse=source/'.git/info/sparse-checkout';sparse.write_text(checkout['sparse-checkout'])
            git('read-tree','-mu','HEAD')
            check(False)
            git('sparse-checkout','disable')
            (source/'phone.txt').write_text('independent\n');git('add','.');git('commit','-qm','independent');check(False)
            (source/'Native.cpp').write_text('changed native input\n');git('add','.');git('commit','-qm','native changed');check(True)
            target=git('rev-parse','HEAD');check(False)

if __name__=='__main__':unittest.main(verbosity=2)
