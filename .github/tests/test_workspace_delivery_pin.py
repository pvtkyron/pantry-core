"""Exercise the real Pantry pin step on shallow authenticated-source Git fixtures."""
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

@unittest.skipUnless(PWSH and GIT,'PowerShell and Git are required')
class WorkspaceDeliveryPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow=yaml.safe_load((ROOT/'.github/workflows/workspace-prepare.yml').read_text(encoding='utf-8'))
        cls.program=next(s['run'] for s in workflow['jobs']['prepare']['steps'] if s.get('name')=='Pin private Pantry delivery')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='kyron-delivery-pin-')
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.writer=self.root/'writer'
        self.repo=self.root/'source'
        self.remote=self.root/'remote.git'
        self.writer.mkdir();self.repo.mkdir()
        subprocess.run([GIT,'init','--bare','-q','-b','main',str(self.remote)],check=True)
        subprocess.run([GIT,'init','-q','-b','main',str(self.writer)],check=True)
        self.git(self.writer,'config','user.name','Fixture')
        self.git(self.writer,'config','user.email','fixture@example.invalid')
        (self.writer/'Distribution').mkdir()
        (self.writer/'Distribution'/'SrcVersion.ini').write_text('fixture=1\n')
        self.git(self.writer,'add','.')
        self.git(self.writer,'commit','-qm','source')
        self.base=self.git(self.writer,'rev-parse','HEAD')
        self.git(self.writer,'remote','add','origin',self.remote.as_uri())
        self.git(self.writer,'push','-q','origin','main')
        self.git(self.repo,'init','-q')
        self.git(self.repo,'remote','add','origin',self.remote.as_uri())
        self.git(self.repo,'fetch','-q','--depth=1','origin',self.base)
        self.git(self.repo,'checkout','-q','-B','main','FETCH_HEAD')
        self.output=self.root/'output'

    @staticmethod
    def git(repo,*args):
        return subprocess.check_output([GIT,'-C',str(repo),*args],text=True,stderr=subprocess.DEVNULL).strip()

    def run_pin(self,sha=None,ok=True):
        self.output.write_text('')
        env=os.environ|{'GITHUB_OUTPUT':str(self.output),'PROMOTED_PANTRY_SHA':sha or self.base,'GIT_TERMINAL_PROMPT':'0'}
        result=subprocess.run([PWSH,'-NoLogo','-NoProfile','-NonInteractive','-Command',self.program],cwd=self.root,env=env,capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode==0,ok,result.stdout+result.stderr)
        self.assertEqual(self.output.read_text(),f'ref={sha or self.base}\n' if ok else '')
        return result

    def test_exact_remote_main_with_missing_tracking_ref(self):
        self.git(self.repo,'config','--unset-all','remote.origin.fetch')
        subprocess.run([GIT,'-C',str(self.repo),'update-ref','-d','refs/remotes/origin/main'],check=False)
        self.run_pin()
        self.assertEqual(self.git(self.repo,'rev-parse','HEAD'),self.base)

    def test_remote_descendant_preserves_original_source(self):
        (self.writer/'Distribution'/'new.txt').write_text('later\n')
        self.git(self.writer,'add','.')
        self.git(self.writer,'commit','-qm','descendant')
        self.git(self.writer,'push','-q','origin','main')
        self.run_pin()
        self.assertEqual(self.git(self.repo,'rev-parse','HEAD'),self.base)

    def test_unrelated_remote_main_is_rejected(self):
        self.git(self.writer,'checkout','-q','--orphan','unrelated')
        (self.writer/'Distribution'/'SrcVersion.ini').write_text('unrelated\n')
        self.git(self.writer,'add','-A')
        self.git(self.writer,'commit','-qm','unrelated root')
        self.git(self.writer,'push','-q','--force','origin','HEAD:main')
        self.run_pin(ok=False)

    def test_modified_local_pin_is_rejected(self):
        self.run_pin('f'*40,ok=False)

    def test_missing_remote_main_is_rejected(self):
        self.git(self.repo,'remote','set-url','origin',(self.root/'missing.git').as_uri())
        self.run_pin(ok=False)

if __name__=='__main__':unittest.main(verbosity=2)
