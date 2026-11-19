"""Run the actual checkpoint action: encrypt verified state without private Git writes."""
import importlib.util,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OWNER=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("route_state",ROOT/"scripts/pantry_route_state.py")
route=importlib.util.module_from_spec(spec);spec.loader.exec_module(route)

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="encrypted-route-action-")
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.source=self.root/"source";self.core=self.root/"shelf"
        for root in (self.source,self.core):
            root.mkdir();self.git(root,"init","-q","-b","main")
            self.git(root,"config","user.name","Fixture");self.git(root,"config","user.email","fixture@example.invalid")
        self.distribution=self.source/"Distribution";self.distribution.mkdir()
        self.ini=self.distribution/"SrcVersion.ini"
        self.ini.write_text("[runtime.contract]\nsource=input\n[launch.contract]\nmode=active\n")
        (self.source/".gitignore").write_text("/Distribution/release/\n")
        (self.source/"peer.txt").write_text("committed peer\n")
        self.git(self.source,"add",".");self.git(self.source,"commit","-qm","pinned input")
        self.sha=self.git(self.source,"rev-parse","HEAD")
        folder=self.distribution/"release";folder.mkdir()
        self.state=folder/"pantry-core-route-state.ini"
        self.plain=(f"; Pantry-Source: {self.sha}\n[runtime.contract]\nprivate-route=sensitive-fixture\n[launch.contract]\nmode=active\n").encode()
        self.state.write_bytes(self.plain)
        (self.core/"kyron").mkdir();(self.core/"kyron/packet.bin").write_bytes(b"signed publication fixture")
        self.git(self.core,"add",".");self.git(self.core,"commit","-qm",f"published\n\nPantry-Source: {self.sha}")
        self.tree=self.git(self.core,"rev-parse","HEAD:kyron")
        self.output=self.root/"outputs";self.output.write_text("")
        self.env=os.environ|{"PANTRY_ROUTE_SOURCE_ROOT":str(self.distribution),"PANTRY_ROUTE_SOURCE_SHA":self.sha,
                             "PANTRY_ROUTE_STATE_KEY":"synthetic-fixture-key","GITHUB_ACTION_PATH":str(OWNER),
                             "RUNNER_TEMP":str(self.root),"GITHUB_OUTPUT":str(self.output)}
    @staticmethod
    def git(root,*args):
        return subprocess.check_output(["git","-C",str(root),*args],text=True,stderr=subprocess.PIPE).strip()
    def invoke(self,**env):
        return subprocess.run(["bash",str(OWNER/"checkpoint.sh")],cwd=self.root,env=self.env|env,
                              capture_output=True,text=True,timeout=20)
    def assert_sealed(self,result):
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("[SEALED]",result.stdout)
        path=Path(self.output.read_text().strip().split("=",1)[1]);wire=path.read_bytes()
        self.assertNotIn(b"sensitive-fixture",wire)
        prior=os.environ.get("PANTRY_ROUTE_STATE_KEY")
        os.environ["PANTRY_ROUTE_STATE_KEY"]="synthetic-fixture-key"
        try:self.assertEqual(route.open_state(wire,self.sha,self.tree),self.plain)
        finally:
            if prior is None:os.environ.pop("PANTRY_ROUTE_STATE_KEY",None)
            else:os.environ["PANTRY_ROUTE_STATE_KEY"]=prior
        self.assertEqual(self.git(self.source,"rev-parse","HEAD"),self.sha)
        self.assertEqual(self.git(self.source,"ls-files","--","Distribution/release"),"")
    def test_seals_ignored_generated_state_without_committing(self):
        self.assert_sealed(self.invoke())
    def test_unreachable_remote_does_not_invalidate_successful_publication(self):
        self.git(self.source,"remote","add","origin","https://127.0.0.1:1/unreachable.git")
        self.assert_sealed(self.invoke())
    def test_preserves_foreign_index_and_worktree(self):
        peer=self.source/"peer.txt";peer.write_text("staged peer\n");self.git(self.source,"add","peer.txt")
        peer.write_text("unstaged peer\n");(self.source/"foreign.txt").write_text("untracked peer\n")
        before=self.git(self.source,"status","--porcelain")
        index=self.git(self.source,"diff","--cached");work=self.git(self.source,"diff")
        self.assert_sealed(self.invoke())
        self.assertEqual(self.git(self.source,"status","--porcelain"),before)
        self.assertEqual(self.git(self.source,"diff","--cached"),index)
        self.assertEqual(self.git(self.source,"diff"),work)
    def test_repeat_capture_keeps_source_and_state_identical(self):
        self.assert_sealed(self.invoke());self.output.write_text("")
        self.assert_sealed(self.invoke());self.assertEqual(self.state.read_bytes(),self.plain)
    def test_dirty_source_configuration_is_rejected_and_preserved(self):
        self.ini.write_text("foreign source edit\n")
        self.assertNotEqual(self.invoke().returncode,0)
        self.assertEqual(self.ini.read_text(),"foreign source edit\n")
        self.assertEqual(self.output.read_text(),"")
    def test_staged_source_configuration_is_rejected_and_preserved(self):
        self.ini.write_text("foreign staged config\n");self.git(self.source,"add","Distribution/SrcVersion.ini")
        before=self.git(self.source,"diff","--cached")
        self.assertNotEqual(self.invoke().returncode,0)
        self.assertEqual(self.git(self.source,"diff","--cached"),before)
    def test_missing_state_or_wrong_source_is_rejected(self):
        self.state.write_bytes(self.plain.replace(self.sha.encode(),b"a"*40))
        self.assertNotEqual(self.invoke().returncode,0)
        self.state.unlink();self.assertNotEqual(self.invoke().returncode,0)
    def test_changed_checkout_or_nested_distribution_git_is_rejected(self):
        self.assertNotEqual(self.invoke(PANTRY_ROUTE_SOURCE_SHA="a"*40).returncode,0)
        (self.distribution/".git").write_text("fixture nested checkout")
        self.assertNotEqual(self.invoke().returncode,0)
    def test_wrong_core_source_or_missing_encryption_key_is_rejected(self):
        self.git(self.core,"commit","--allow-empty","-qm","different\n\nPantry-Source: "+"b"*40)
        self.assertNotEqual(self.invoke().returncode,0)
        self.assertEqual(self.output.read_text(),"")
        self.assertNotEqual(self.invoke(PANTRY_ROUTE_STATE_KEY="").returncode,0)
    def test_redirected_release_folder_is_rejected(self):
        self.state.unlink();self.state.parent.rmdir()
        outside=self.root/"outside";outside.mkdir()
        self.state.parent.symlink_to(outside,target_is_directory=True)
        self.assertNotEqual(self.invoke().returncode,0)
        self.assertFalse(any(outside.iterdir()))

if __name__=="__main__":unittest.main()
