import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]/'scripts/workspace_input_key.py'
s=importlib.util.spec_from_file_location('key',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class InputKeyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.git('init','-q','-b','main');self.git('config','user.name','fixture');self.git('config','user.email','fixture@example.invalid')
        for p,data in {'VeraInternal/src/a.cpp':'native','Launcher/ui.cs':'ui','etc/tool.lock':'compiler','Distribution/release/pantry-core-route-state.ini':'publisher'}.items():self.write(p,data)
        self.commit('initial')
        self.specs=['VeraInternal','etc',':(top,exclude)Distribution/release/pantry-core-route-state.ini']
    def git(self,*a):return subprocess.check_output(['git','-C',str(self.root),*a])
    def write(self,p,data):
        f=self.root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
    def commit(self,message):self.git('add','.');self.git('commit','-q','-m',message)
    def key(self):return m.tree(self.root,'HEAD',self.specs)
    def test_independent_launcher_and_checkpoint_changes_reuse_native_inputs(self):
        before=self.key();self.write('Launcher/ui.cs','new UI');self.write('Distribution/release/pantry-core-route-state.ini','new checkpoint');self.commit('independent')
        self.assertEqual(before,self.key())
    def test_actual_compiler_or_toolchain_change_invalidates_then_revert_recovers(self):
        before=self.key();self.write('VeraInternal/src/a.cpp','new native');self.commit('native')
        self.assertNotEqual(before,self.key());self.write('VeraInternal/src/a.cpp','native');self.commit('revert')
        self.assertEqual(before,self.key());self.write('etc/tool.lock','new compiler');self.commit('toolchain')
        self.assertNotEqual(before,self.key())
    def test_fingerprint_preserves_real_index_worktree_and_refs(self):
        index=self.root/'.git/index';before=index.read_bytes();refs=self.git('show-ref');status=self.git('status','--porcelain')
        self.key();self.assertEqual(before,index.read_bytes());self.assertEqual(refs,self.git('show-ref'));self.assertEqual(status,self.git('status','--porcelain'))
    def test_exclude_and_glob_are_interpreted_by_git(self):
        a=m.tree(self.root,'HEAD',['VeraInternal',':(exclude,glob)**/*.md'])
        self.write('VeraInternal/README.md','documentation');self.commit('docs')
        self.assertEqual(a,m.tree(self.root,'HEAD',['VeraInternal',':(exclude,glob)**/*.md']))
if __name__=='__main__':unittest.main(verbosity=2)
