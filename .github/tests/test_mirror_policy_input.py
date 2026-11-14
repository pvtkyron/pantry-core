"""Execute the actual mirror materializer against cold, stale and corrupt inputs."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import yaml

WORKFLOW=Path(__file__).resolve().parents[1]/"workflows/pantry-mirror.yml"
DOCUMENT=yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
STEPS=[step for job in DOCUMENT["jobs"].values() for step in job.get("steps",[])
       if step.get("name")=="Materialize pinned Windows ADB runtime and launch-plane marker"]
if len(STEPS)!=1:raise RuntimeError("Canonical mirror materializer missing")
PROGRAM=STEPS[0]["run"].split("<<'PY'\n",1)[1].rsplit("\nPY",1)[0]
DIGEST="712a18f980ceb74b8d6965ca113f9581a6b868e1ed83216326da54dd26a6ef5e"
RECORD="policy/launcher-disabled-"+DIGEST[:24]+".blk"

class MirrorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="mirror-policy-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/"source/Distribution";self.source.mkdir(parents=True)
        self.marker=self.source/"client/launch-plane-only.marker"
        self.config=self.source/"SrcVersion.ini"
        self.config.write_text("[runtime.contract]\nclient_source=client/launch-plane-only.marker\nclient_record="+RECORD+"\n",encoding="utf-8")
        self.archive=self.root/"adb.zip"
        with zipfile.ZipFile(self.archive,"w") as out:
            for name in ("adb.exe","AdbWinApi.dll","AdbWinUsbApi.dll"):
                out.writestr("platform-tools/"+name,b"MZ-synthetic-pinned-sdk-fixture")
    def invoke(self):
        return subprocess.run([sys.executable,"-c",PROGRAM,str(self.archive)],cwd=self.root,
            capture_output=True,text=True,timeout=15)
    def assert_canonical(self):
        result=self.invoke()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.marker.stat().st_size,247)
        self.assertEqual(hashlib.sha256(self.marker.read_bytes()).hexdigest(),DIGEST)
    def test_cold_snapshot_materializes_actual_nonempty_policy(self):
        self.assert_canonical()
        for name in ("adb.exe","AdbWinApi.dll","AdbWinUsbApi.dll"):
            self.assertTrue((self.source/"client/tools/android"/name).read_bytes().startswith(b"MZ"))
    def test_zero_byte_generated_placeholder_is_upgraded_to_pinned_policy(self):
        self.marker.parent.mkdir();self.marker.touch()
        self.assert_canonical()
    def test_repeated_materialization_preserves_original_policy_bytes(self):
        self.assert_canonical();before=self.marker.read_bytes();self.assert_canonical()
        self.assertEqual(self.marker.read_bytes(),before)
    def test_wrong_nonempty_policy_is_preserved_and_rejected(self):
        self.marker.parent.mkdir();self.marker.write_bytes(b"unapproved-policy")
        self.assertNotEqual(self.invoke().returncode,0)
        self.assertEqual(self.marker.read_bytes(),b"unapproved-policy")
    def test_wrong_source_contract_cannot_receive_a_policy(self):
        self.config.write_text("[runtime.contract]\nclient_source=client/launch-plane-only.marker\nclient_record=policy/unapproved.blk\n",encoding="utf-8")
        self.assertNotEqual(self.invoke().returncode,0);self.assertFalse(self.marker.exists())
    def test_symlink_cannot_redirect_generated_policy(self):
        outside=self.root/"outside";outside.write_bytes(b"preserve")
        self.marker.parent.mkdir();self.marker.symlink_to(outside)
        self.assertNotEqual(self.invoke().returncode,0);self.assertEqual(outside.read_bytes(),b"preserve")

if __name__=="__main__":unittest.main(verbosity=2)
