"""Source Git fixtures: changed owners compile, independent owners reuse."""
import importlib.util,subprocess,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/"scripts/workspace_lane_source.py";S=importlib.util.spec_from_file_location("p",P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.git("init","-q","-b","main");self.git("config","user.name","fixture");self.git("config","user.email","fixture@example.invalid")
        for p in ("Distribution/lua/a.lua","Distribution/src/A.java","VeraInternal/a.cpp","Launcher/a.cpp","Shared/contract.hpp","etc/security/signing/signer.json","etc/publishing/Compose-PantryDeliveryProvenance.ps1"):self.write(p,p)
        self.write("etc/devtools/KyronReleaseGate.py","SOURCES=('Launcher','Shared','etc/devtools/KyronReleaseGate.py')\n")
        self.old=self.commit("original")
    def git(self,*a):return subprocess.check_output(["git","-C",str(self.root),*a],stderr=subprocess.DEVNULL).decode().strip()
    def write(self,p,s):
        f=self.root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)
    def commit(self,m):self.git("add","-A");self.git("commit","-qm",m);return self.git("rev-parse","HEAD")
    def check(self,p,java,exe):
        self.write(p,"updated");current=self.commit("change")
        self.assertEqual(M.unchanged(self.root,self.old,current,"java"),java)
        self.assertEqual(M.unchanged(self.root,self.old,current,"exe"),exe)
    def test_lua_only(self):self.check("Distribution/lua/a.lua",True,True)
    def test_native_only(self):self.check("VeraInternal/a.cpp",True,True)
    def test_launcher_only(self):self.check("Launcher/a.cpp",True,False)
    def test_java_changed(self):self.check("Distribution/src/A.java",False,False)
    def test_publisher_only(self):self.check("etc/publishing/Compose-PantryDeliveryProvenance.ps1",True,True)
    def test_signed_cdn_publisher_change_does_not_recompile_java_or_exe(self):
        self.check("Distribution/tools/kyron_pipeline.py",True,True)
    def test_other_runtime_tool_changes_still_invalidate_compiler_proofs(self):
        self.check("Distribution/tools/sync_consumer_contract.py",False,False)
    def test_publisher_exclusion_is_exact(self):
        for lane in ("java","exe"):
            paths=M.protected_paths(lane,self.root)
            self.assertIn("Distribution/tools",paths)
            self.assertIn(":(top,exclude)Distribution/tools/kyron_pipeline.py",paths)
            self.assertNotIn(":(top,exclude)Distribution/tools",paths)
    def test_launcher_gate_cannot_enroll_an_excluded_publisher_path(self):
        self.write("etc/devtools/KyronReleaseGate.py","SOURCES=('Launcher','Distribution/tools','etc/devtools/KyronReleaseGate.py')\n")
        now=self.commit("gate claims publisher as compiler input")
        self.assertFalse(M.unchanged(self.root,now,now,"exe"))
    def test_signer_or_shared_changed(self):
        for p in ("Shared/contract.hpp","etc/security/signing/signer.json"):
            with self.subTest(p=p):self.check(p,False,False)
    def test_deletion_rejected(self):
        (self.root/"Launcher/a.cpp").unlink();now=self.commit("deleted");self.assertFalse(M.unchanged(self.root,self.old,now,"exe"))
    def test_forged_or_missing_source(self):
        self.assertFalse(M.unchanged(self.root,"0"*40,self.old,"java"));self.assertFalse(M.unchanged(self.root,self.old,"f"*40,"exe"))
    def test_launcher_compiler_gate_and_toolchain_changes_are_not_reusable(self):
        for path in ("etc/devtools/KyronReleaseGate.py","etc/devtools/ToolchainEnv.cmd",
                     "etc/publishing/Initialize-LocalPantrySigner.ps1","etc/publishing/Assert-FrozenBootstrap.ps1",".gitattributes"):
            with self.subTest(path=path):self.check(path,True,False)
    def test_launcher_new_gate_source_is_fail_closed_without_policy_expansion(self):
        self.write("etc/devtools/KyronReleaseGate.py","SOURCES=('Launcher','new/hidden-build-input')\n")
        now=self.commit("new-gate-owner")
        self.assertFalse(M.unchanged(self.root,now,now,"exe"))
        self.assertTrue(M.unchanged(self.root,now,now,"java"))
    def test_divergent_branch_rejected(self):
        self.git("checkout","-qb","other",self.old);self.write("Distribution/lua/a.lua","branch");other=self.commit("branch")
        self.git("checkout","-q","main");self.write("Distribution/lua/a.lua","current");now=self.commit("current")
        self.assertFalse(M.unchanged(self.root,other,now,"java"))
if __name__=="__main__":unittest.main()
