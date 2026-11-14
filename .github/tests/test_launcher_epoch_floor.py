"""Exercise post-publication epoch advancement without rewriting installed state."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
import advance_launcher_epoch_floor as owner
import release_policy

class EpochFloorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.image=self.root/"Launcher.exe";self.image.write_bytes(b"MZ"+b"verified-image"*6000)
        self.meta=self.root/"Launcher.build.json";self.doc={"schema":1,"product":"KyronLauncher","architecture":"x64",
            "launch_epoch":2608100600000259,"exe_sha256":hashlib.sha256(self.image.read_bytes()).hexdigest()}
        self.save();self.source="a"*40;self.revision="b"*40
        self.commit={"sha":self.revision,"parents":[],"message":"Pantry-Source: "+self.source+"\nHistory-Mode: root-only\n"}
        self.value=None;self.calls=[];self.conflict=False
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.meta.write_text(json.dumps(self.doc),encoding="utf-8")
    def request(self,method,path,body=None):
        self.calls.append((method,path,body))
        if "/git/commits/" in path:return copy.deepcopy(self.commit)
        if method=="GET":
            if self.value is None:raise owner.ApiError(404)
            return {"value":self.value}
        if self.conflict:
            self.conflict=False;self.value=str(self.doc["launch_epoch"]+2);raise owner.ApiError(409)
        self.value=body["value"]
    def advance(self):return owner.advance(self.meta,self.image,self.revision,self.source,self.request)
    def test_first_verified_publication_creates_next_floor(self):
        original=self.image.read_bytes()
        self.assertEqual(self.advance(),(self.doc["launch_epoch"]+1,True))
        self.assertEqual(self.image.read_bytes(),original)
        self.assertTrue(any(method=="POST" for method,_,_ in self.calls))
    def test_existing_lower_floor_advances_once_then_noop(self):
        self.value="1";self.assertTrue(self.advance()[1]);self.calls=[]
        self.assertFalse(self.advance()[1])
        self.assertFalse(any(method in ("POST","PATCH") for method,_,_ in self.calls))
    def test_higher_operator_floor_is_preserved(self):
        self.value=str(self.doc["launch_epoch"]+100)
        self.assertEqual(self.advance(),(int(self.value),False))
    def test_concurrent_higher_creation_is_preserved(self):
        self.conflict=True
        self.assertEqual(self.advance(),(self.doc["launch_epoch"]+2,False))
    def test_unverified_publication_cannot_change_any_variable(self):
        for field,value in (("sha","c"*40),("parents",[{"sha":"c"*40}]),("message","History-Mode: root-only")):
            original=copy.deepcopy(self.commit);self.commit[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.advance()
            self.commit=original
        self.assertFalse(any(method!="GET" for method,_,_ in self.calls))
    def test_corrupt_image_is_rejected_before_any_api_access(self):
        self.image.write_bytes(b"MZ"+b"corrupt"*12000)
        with self.assertRaises(ValueError):self.advance()
        self.assertEqual(self.calls,[])
    def test_bad_epoch_fields_are_rejected_before_any_api_access(self):
        original=dict(self.doc)
        for value in (0,-1,True,"2608100600000259",owner.MAX,owner.MAX+1):
            self.doc=original|{"launch_epoch":value};self.save()
            with self.subTest(value=value),self.assertRaises(ValueError):self.advance()
        self.assertEqual(self.calls,[])
    def test_malformed_existing_floor_is_never_overwritten(self):
        for value in ("0","-1","2.5","not-a-number",str(2**64)):
            self.value=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.advance()
        self.assertFalse(any(method!="GET" for method,_,_ in self.calls))
    def test_auth_failure_is_not_treated_as_a_missing_variable(self):
        def denied(method,path,body=None):
            if "/git/commits/" in path:return self.commit
            raise owner.ApiError(403)
        with self.assertRaises(owner.ApiError):owner.advance(self.meta,self.image,self.revision,self.source,denied)
    def test_invalid_hosted_context_is_rejected(self):
        with mock.patch.dict(os.environ,{"GITHUB_ACTIONS":"false"}),self.assertRaises(ValueError):owner.main()

class VerifiedPolicyTests(unittest.TestCase):
    def test_live_floor_cannot_be_lowered_by_an_older_manual_minimum(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"policy.json";path.write_text(json.dumps({"schema":1,"minimum_launch_epoch":152}))
            self.assertEqual(release_policy.minimum_epoch("259",path,verified="260"),260)
            self.assertEqual(release_policy.minimum_epoch("",path,verified="260"),260)
            self.assertEqual(release_policy.minimum_epoch("261",path,verified="260"),261)
            with self.assertRaises(ValueError):release_policy.minimum_epoch("151",path,verified="260")
            for value in ("-1","0","bad",str(2**64)):
                with self.subTest(value=value),self.assertRaises(ValueError):release_policy.minimum_epoch("",path,verified=value)

if __name__=="__main__":unittest.main(verbosity=2)
