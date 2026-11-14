import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/'scripts/release_policy.py'
spec=importlib.util.spec_from_file_location('policy',FILE);policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)

class ReleasePolicyTests(unittest.TestCase):
    def test_verified_floor_is_used_without_inventing_device_state(self):
        expected=json.loads(policy.POLICY.read_text())['minimum_launch_epoch']
        self.assertEqual(policy.minimum_epoch(),expected)
        self.assertEqual(policy.minimum_epoch('0'),expected)
        self.assertEqual(policy.minimum_epoch(str(expected+1)),expected+1)
        for value in (str(expected-1),'bad','-1',str(2**64),'01'):
            with self.subTest(value=value),self.assertRaises(ValueError):policy.minimum_epoch(value)
    def test_malformed_policy_cannot_disable_rollback_protection(self):
        with tempfile.TemporaryDirectory() as raw:
            path=Path(raw)/'policy.json'
            for value in ({},{'schema':1,'minimum_launch_epoch':0},{'schema':1,'minimum_launch_epoch':True},{'schema':2,'minimum_launch_epoch':123}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):policy.minimum_epoch(policy=path)
if __name__=='__main__':unittest.main(verbosity=2)
