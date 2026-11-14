"""Read-only authenticated DEX carry: same-source, Lua-only, and fail-closed corruption."""
import hashlib,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
import verify_precompiled_dex as m
class JavaCarry(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.git("init","-qb","main")
        self.git("config","user.name","Fixture");self.git("config","user.email","fixture@example.invalid")
        self.write("Distribution/src/Hello.java","class Hello {}")
        self.write("Distribution/tools/encrypt_assets.py","original")
        self.write("Distribution/lua/frame.lua","old")
        self.original=self.commit("baseline")
        self.dex=self.root/m.DEX;self.receipt=self.root/m.RECEIPT
        data=b"dex\n035\x00"+b"\x00"*88
        self.dex.parent.mkdir(parents=True,exist_ok=True);self.dex.write_bytes(data)
        self.record={"schema":1,"workspace_sha":self.original,"dex_sha256":hashlib.sha256(data).hexdigest(),"dex_bytes":len(data),"profile":m.PROFILE,"dex_source":"dist/InputHost.dex"}
        self.save()
    def git(self,*args):return subprocess.check_output(["git","-C",str(self.root),*args],stderr=subprocess.DEVNULL).decode().strip()
    def write(self,path,content):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
    def commit(self,comment):self.git("add","-A");self.git("commit","-qm",comment);return self.git("rev-parse","HEAD")
    def save(self):self.receipt.write_text(json.dumps(self.record))
    def test_same_source_valid(self):self.assertEqual(m.verify(self.root,self.original,True),self.record["dex_sha256"])
    def test_lua_changed_compiler_unchanged(self):
        self.write("Distribution/lua/frame.lua","updated");now=self.commit("lua only")
        self.assertEqual(m.verify(self.root,now,True),self.record["dex_sha256"])
    def test_changed_java_compiler_rejected(self):
        self.write("Distribution/src/Hello.java","different");now=self.commit("new java")
        with self.assertRaisesRegex(ValueError,"Java compiler source"):m.verify(self.root,now,True)
    def test_missing_pair_forbidden(self):
        self.receipt.unlink()
        with self.assertRaisesRegex(ValueError,"missing, unpaired"):m.verify(self.root,self.original,True)
        self.dex.unlink()
        self.assertIsNone(m.verify(self.root,self.original,False))
        with self.assertRaisesRegex(ValueError,"missing"):m.verify(self.root,self.original,True)
    def test_modified_bytes_fail(self):
        self.dex.write_bytes(self.dex.read_bytes()+b"bad")
        with self.assertRaisesRegex(ValueError,"length"):m.verify(self.root,self.original,True)
    def test_forged_receipt_rejected(self):
        for key,bad in (("workspace_sha","f"*40),("dex_sha256","a"*64),("profile","unapproved"),("dex_bytes",123),("schema",2)):
            with self.subTest(key=key):
                old=self.record[key];self.record[key]=bad;self.save()
                with self.assertRaises(ValueError):m.verify(self.root,self.original,True)
                self.record[key]=old;self.save()
    def test_invalid_dex_magic_rejected(self):
        data=b"bad\n035\x00"+b"\x00"*88
        self.dex.write_bytes(data);self.record["dex_sha256"]=hashlib.sha256(data).hexdigest();self.save()
        with self.assertRaisesRegex(ValueError,"header"):m.verify(self.root,self.original,True)
    def test_wrong_current_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,"source differs"):m.verify(self.root,"f"*40,True)
if __name__=="__main__":unittest.main()
