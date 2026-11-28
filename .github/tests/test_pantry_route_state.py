"""Exercise the actual encrypted route checkpoint, artifact admission and cold restore."""
from __future__ import annotations
import importlib.util,io,os,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("route_state",ROOT/"scripts/pantry_route_state.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SOURCE="a"*40;TREE="b"*40
STATE=(f"; Pantry-Source: {SOURCE}\n[runtime.contract]\nprivate-route=value\n[launch.contract]\nmode=active\n").encode()

def zipped(wire,name="route-state.enc"):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w") as z:z.writestr(name,wire)
    return out.getvalue()

def artifact():
    return {"id":21,"name":"kyron-route-state-"+SOURCE,"expired":False,"workflow_run":{"id":31}}

def run():
    return {"id":31,"repository":{"full_name":m.REPO},"head_repository":{"full_name":m.REPO},
            "head_branch":"main","path":".github/workflows/pantry-mirror.yml",
            "event":"workflow_dispatch","status":"completed","conclusion":"success"}

class RouteState(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"PANTRY_ROUTE_STATE_KEY":"fixture-secret","GITHUB_OUTPUT":""})
        self.env.start()
    def tearDown(self):self.env.stop()
    def test_authenticated_round_trip_is_confidential_and_randomized(self):
        a=m.seal(STATE,SOURCE,TREE);b=m.seal(STATE,SOURCE,TREE)
        self.assertNotEqual(a,b);self.assertNotIn(b"private-route=value",a)
        self.assertEqual(m.open_state(a,SOURCE,TREE),STATE)
    def test_tamper_wrong_key_source_and_tree_rejected(self):
        a=m.seal(STATE,SOURCE,TREE)
        for i in (0,len(m.MAGIC),len(a)-1):
            bad=bytearray(a);bad[i]^=1
            with self.subTest(i=i),self.assertRaises(Exception):m.open_state(bytes(bad),SOURCE,TREE)
        with patch.dict(os.environ,{"PANTRY_ROUTE_STATE_KEY":"wrong"}),self.assertRaises(Exception):
            m.open_state(a,SOURCE,TREE)
        for source,tree in (("c"*40,TREE),(SOURCE,"d"*40)):
            with self.assertRaises(ValueError):m.open_state(a,source,tree)
    def test_missing_key_and_false_source_header_rejected(self):
        with patch.dict(os.environ,{"PANTRY_ROUTE_STATE_KEY":""}),self.assertRaises(ValueError):
            m.seal(STATE,SOURCE,TREE)
        with self.assertRaises(ValueError):m.seal(STATE,"c"*40,TREE)
    def test_only_completed_canonical_main_publishers_admitted(self):
        m.admit(artifact(),run(),SOURCE)
        mutations={"head_branch":"feature","path":".github/workflows/patisserie.yml",
                   "event":"pull_request","status":"in_progress","conclusion":"failure",
                   "head_repository":{"full_name":"fork/pantry-core"}}
        for field,value in mutations.items():
            r=run();r[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):m.admit(artifact(),r,SOURCE)
        a=artifact();a["workflow_run"]={"id":999}
        with self.assertRaises(ValueError):m.admit(a,run(),SOURCE)
        a=artifact();a["expired"]=True
        with self.assertRaises(ValueError):m.admit(a,run(),SOURCE)
    def test_archive_rejects_extra_and_redirected_members(self):
        wire=m.seal(STATE,SOURCE,TREE)
        self.assertEqual(m.archive(zipped(wire)),wire)
        with self.assertRaises(ValueError):m.archive(zipped(wire,"../route-state.enc"))
        out=io.BytesIO()
        with zipfile.ZipFile(out,"w") as z:
            z.writestr("route-state.enc",wire);z.writestr("extra",b"x")
        with self.assertRaises(ValueError):m.archive(out.getvalue())
    def test_cold_restore_and_idempotence_preserve_other_files(self):
        wire=m.seal(STATE,SOURCE,TREE)
        def api(path,binary=False):
            if path.startswith("actions/artifacts?"):return {"artifacts":[artifact()]}
            if path=="actions/runs/31":return run()
            if path=="actions/artifacts/21/zip":return zipped(wire)
            raise AssertionError(path)
        with tempfile.TemporaryDirectory() as tmp,patch.object(m,"api",side_effect=api),patch.object(m,"core_identity",return_value=TREE):
            root=Path(tmp);other=root/"foreign.txt";other.write_bytes(b"untouched")
            self.assertTrue(m.restore(root,SOURCE,root));self.assertTrue(m.restore(root,SOURCE,root))
            self.assertEqual((root/"release/pantry-core-route-state.ini").read_bytes(),STATE)
            self.assertEqual(other.read_bytes(),b"untouched")
    def test_missing_or_failed_baseline_requests_full_without_writing(self):
        for failed in (False,True):
            def api(path,binary=False):
                if path.startswith("actions/artifacts?"):return {"artifacts":[artifact()] if failed else []}
                if path=="actions/runs/31":
                    r=run();r["conclusion"]="failure";return r
                raise AssertionError("failed producer archive must not be downloaded")
            with tempfile.TemporaryDirectory() as tmp,patch.object(m,"api",side_effect=api),patch.object(m,"core_identity",return_value=TREE):
                root=Path(tmp);self.assertFalse(m.restore(root,SOURCE,root))
                self.assertFalse((root/"release").exists())
    def test_existing_different_state_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"release").mkdir();p=root/"release/pantry-core-route-state.ini";p.write_bytes(b"foreign")
            with self.assertRaises(ValueError):m.write_state(root,STATE)
            self.assertEqual(p.read_bytes(),b"foreign")
    @unittest.skipUnless(hasattr(os,"symlink"),"symlinks unavailable")
    def test_redirected_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/"outside";outside.mkdir();source=root/"source";source.mkdir()
            try:(source/"release").symlink_to(outside,target_is_directory=True)
            except OSError:self.skipTest("symlinks require OS privileges")
            with self.assertRaises(ValueError):m.write_state(source,STATE)
            self.assertFalse((outside/"pantry-core-route-state.ini").exists())
    def test_capture_keeps_real_ignored_generated_state_out_of_git(self):
        def git(root,*args):
            return subprocess.check_output(["git","-C",str(root),*args],stderr=subprocess.PIPE).decode().strip()
        def init(root):
            root.mkdir();git(root,"init","-b","main")
            git(root,"config","user.name","fixture");git(root,"config","user.email","fixture@example.invalid")
            git(root,"config","commit.gpgsign","false");git(root,"config","core.hooksPath",str(root/"empty-hooks"))
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);workspace=home/"source";core=home/"core";init(workspace);init(core)
            distribution=workspace/"Distribution";distribution.mkdir()
            (workspace/".gitignore").write_text("/Distribution/release/\n")
            (distribution/"SrcVersion.ini").write_text("[runtime.contract]\n[launch.contract]\n")
            git(workspace,"add",".");git(workspace,"commit","-m","source");source=git(workspace,"rev-parse","HEAD")
            (distribution/"release").mkdir();state=STATE.replace(SOURCE.encode(),source.encode())
            (distribution/"release/pantry-core-route-state.ini").write_bytes(state)
            (core/"kyron").mkdir();(core/"kyron/object.bin").write_bytes(b"signed-fixture")
            git(core,"add",".");git(core,"commit","-m",f"published\n\nPantry-Source: {source}")
            (core/"control.txt").write_text("new recipe, same published runtime")
            git(core,"add","control.txt");git(core,"commit","-m","control only")
            with self.assertRaises(ValueError):m.core_identity(core,"c"*40)
            destination=home/"route-state.enc"
            m.capture(distribution,source,core,destination)
            tree=git(core,"rev-parse","HEAD:kyron")
            self.assertEqual(m.open_state(destination.read_bytes(),source,tree),state)
            self.assertEqual(git(workspace,"status","--porcelain"),"")
            self.assertEqual(git(workspace,"ls-files","--","Distribution/release"),"")
            self.assertEqual(git(workspace,"rev-parse","HEAD"),source)

if __name__=="__main__":unittest.main()
