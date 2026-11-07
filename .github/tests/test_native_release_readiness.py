"""Offline regression tests for native approval and candidate tag provenance."""
from pathlib import Path
import yaml
import importlib.util
import unittest
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_release_ready.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("native_release_ready", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class NativeReleaseReadinessTests(unittest.TestCase):
    def setUp(self):
        self.sha32 = "a" * 64
        self.sha64 = "b" * 64
        self.source = "c" * 40
        self.pins = MODULE.contract_pins(
            f"release_lib_sha256_32={self.sha32}\ninsider_lib_sha256_32={self.sha32}\n"
            f"release_lib_sha256_64={self.sha64}\ninsider_lib_sha256_64={self.sha64}\n")
        self.assets = [{"name": "runtime-lane-v1.json", "state": "uploaded", "size": 100}]
        for abi, digest in self.pins.items():
            for ext in ("so", "release.json", "so.kyron-finalized"):
                item = {"name": f"libkyron-{abi}.{ext}", "state": "uploaded", "size": 100}
                if ext == "so":
                    item["digest"] = "sha256:" + digest
                self.assets.append(item)

    def test_approved_requires_complete_exact_dual_abi(self):
        self.assertTrue(MODULE.approved([{"assets": self.assets}], self.pins))
        self.assertFalse(MODULE.approved([{"assets": self.assets[:-1]}], self.pins))
        self.assertFalse(MODULE.approved([{"assets": self.assets + self.assets[-1:]}], self.pins))

    def test_approved_pair_requires_the_actual_native_input_tree(self):
        with tempfile.TemporaryDirectory(prefix="native-approval-tree-") as raw:
            root=Path(raw)
            def git(*args):
                return subprocess.check_output(["git","-C",raw,*args],stderr=subprocess.DEVNULL,text=True).strip()
            git("init","-q");git("config","user.name","Fixture");git("config","user.email","fixture@example.invalid")
            (root/"Native.cpp").write_text("signed input\n")
            (root/"contract.ini").write_text("approved pins\n")
            git("add",".");git("commit","-qm","approved")
            original=git("rev-parse","HEAD")
            release={"assets":self.assets,"target_commitish":original}
            specs=["Native.cpp","contract.ini"]
            self.assertTrue(MODULE.source_approved([release],self.pins,root,specs))
            (root/"phone.txt").write_text("independent source\n")
            git("add",".");git("commit","-qm","phone only")
            self.assertTrue(MODULE.source_approved([release],self.pins,root,specs))
            (root/"Native.cpp").write_text("new native source\n")
            git("add",".");git("commit","-qm","native changed")
            self.assertFalse(MODULE.source_approved([release],self.pins,root,specs))
            # Approval targets the metadata commit, preserving original compiled identity.
            (root/"contract.ini").write_text("explicitly approved new pins\n")
            git("add",".");git("commit","-qm","approve new delivery")
            release["target_commitish"]=git("rev-parse","HEAD")
            self.assertTrue(MODULE.source_approved([release],self.pins,root,specs))
            (root/"Native.cpp").unlink()
            git("add","-A");git("commit","-qm","native removed")
            self.assertFalse(MODULE.source_approved([release],self.pins,root,specs))

    def test_candidate_is_not_publication_and_requires_exact_sha(self):
        message = (f"signed-native-candidate-v1 source={self.source} "
                   f"sha32={self.sha32} sha64={self.sha64} run=123 attempt=1; NOT_PUBLISHED")
        self.assertEqual(MODULE.parse_receipt(message, self.source), self.pins)
        for bad in (message.replace("NOT_PUBLISHED", "PUBLISHED"),
                    message.replace(self.sha32, "X" * 64),
                    message.replace(self.source, "e" * 40)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    MODULE.parse_receipt(bad, self.source)

    def test_credential_bom_is_trimmed_but_embedded_control_characters_fail(self):
        self.assertEqual(MODULE.clean_token("\ufeff   token-123\r\n"), "token-123")
        self.assertEqual(MODULE.clean_token("  \ufefftoken-123\ufeff\t"), "token-123")
        for candidate in ("token\ufeff123", "token\n123", "  "):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                MODULE.clean_token(candidate)

    def test_schedule_skips_heavy_crypto_regressions_but_still_scans(self):
        workflow = yaml.safe_load((SCRIPT.parent.parent / "workflows/source-watch.yml").read_text())
        tests = workflow["jobs"]["routing-tests"]["if"]
        scan = workflow["jobs"]["watch"]["if"]
        self.assertNotIn("github.event_name == 'schedule'", tests)
        self.assertIn("github.event_name == 'schedule'", scan)
        self.assertIn("always()", scan)

    def test_identical_compiler_inputs_reuse_original_candidate_without_relabelling(self):
        key="d"*64;original="e"*40
        item={"id":31,"name":"kyron-native-receipt-"+original,"expired":False,"created_at":"2026-10-30",
              "size_in_bytes":400,"workflow_run":{"id":123,"head_branch":"main","repository_id":1,"head_repository_id":1}}
        receipt={"schema":1,"source_sha":original,"inputs_sha256":key,"producer_run_id":123,
                 "verified":True,"published":False,"sha32":self.sha32,"sha64":self.sha64}
        def fetch(url,token):
            if "name=" in url:return {"artifacts":[]}
            if "/actions/artifacts?" in url:return {"artifacts":[item]}
            if "/jobs?" in url:return {"jobs":[{"name":"Record verified signed candidate (publication not implied)","conclusion":"success","steps":[
                {"name":"Register verified signed pair without asserting publication","conclusion":"success"},
                {"name":"Preserve small verified native candidate receipt","conclusion":"success"}]}]}
            return {"repository":{"full_name":"pvtkyron/pantry-core"},"head_branch":"main","status":"completed","path":".github/workflows/component-lib.yml"}
        def download(command,**kwargs):
            (Path(command[-1])/"native-candidate-receipt.json").write_text(json.dumps(receipt))
            return SimpleNamespace(returncode=0)
        with patch.object(MODULE,"fetch_json",side_effect=fetch),patch.object(MODULE.subprocess,"run",side_effect=download):
            self.assertEqual(MODULE.candidate_receipt("pvtkyron/pantry-core","fixture-token",self.source,key),self.pins)
            self.assertIsNone(MODULE.candidate_receipt("pvtkyron/pantry-core","fixture-token",self.source,"f"*64))
            receipt["source_sha"]=self.source
            with self.assertRaisesRegex(ValueError,"source, producer"):
                MODULE.candidate_receipt("pvtkyron/pantry-core","fixture-token",self.source,key)

    def test_transient_github_gateway_retries_but_authentication_stays_fatal(self):
        from io import BytesIO
        from urllib.error import HTTPError
        from unittest.mock import MagicMock
        reply=MagicMock();reply.__enter__.return_value=BytesIO(b'{"ok":true}')
        transient=HTTPError("https://api.github.com/fixture",502,"temporary",{},None)
        with patch.object(MODULE,"urlopen",side_effect=[transient,transient,reply]) as request,patch.object(MODULE.time,"sleep") as sleep:
            self.assertEqual(MODULE.fetch_json("https://api.github.com/fixture","synthetic"),{"ok":True})
            self.assertEqual(request.call_count,3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list],[1,2])
        denied=HTTPError("https://api.github.com/fixture",401,"denied",{},None)
        with patch.object(MODULE,"urlopen",side_effect=denied) as request,patch.object(MODULE.time,"sleep") as sleep:
            with self.assertRaises(HTTPError):MODULE.fetch_json("https://api.github.com/fixture","synthetic")
            self.assertEqual(request.call_count,1);sleep.assert_not_called()
        with patch.object(MODULE,"urlopen",side_effect=transient) as request,patch.object(MODULE.time,"sleep"):
            with self.assertRaises(HTTPError):MODULE.fetch_json("https://api.github.com/fixture","synthetic")
            self.assertEqual(request.call_count,5)

    def test_ambiguous_approval_pin_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.contract_pins("release_lib_sha256_32=" + self.sha32)

if __name__ == "__main__":
    unittest.main()
