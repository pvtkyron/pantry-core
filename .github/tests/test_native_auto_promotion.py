#!/usr/bin/env python3
"""Exercise candidate evidence, immutable source admission and publication intent."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
import select_native_candidate as select
import approve_native_release as approval
import recover_native_candidate as recovery

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.run={"id":123,"run_attempt":2,"head_sha":"a"*40,"head_repository":{"full_name":select.REPO},
            "head_branch":"main","path":".github/workflows/component-lib.yml","status":"completed","conclusion":"success"}
        self.event={"repository":{"full_name":select.REPO},"workflow_run":copy.deepcopy(self.run)}
        self.receipt={"schema":1,"source_sha":"b"*40,"sha32":"c"*64,"sha64":"d"*64,
            "producer_run_id":123,"producer_attempt":2,"verified":True,"published":False,"auto_promote":True}
    def test_completion_is_bound_to_exact_attempt_and_repository(self):
        self.assertEqual(select.producer(self.event,self.run),(123,2))
        for field,value in (("run_attempt",3),("head_sha","d"*40),("conclusion","failure"),
                ("head_repository",{"full_name":"fork/pantry-core"}),("path",".github/workflows/other.yml")):
            changed=copy.deepcopy(self.run);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):select.producer(self.event,changed)
    def test_only_unique_live_signed_candidate_is_selected(self):
        artifact={"id":23,"name":"kyron-signed-native-candidate-123-2","expired":False}
        self.assertIsNone(select.signed_artifact([],123,2))
        self.assertIsNone(select.signed_artifact([artifact|{"expired":True}],123,2))
        self.assertEqual(select.signed_artifact([artifact],123,2),artifact)
        with self.assertRaises(ValueError):select.signed_artifact([artifact,artifact],123,2)
    def test_validation_only_and_legacy_candidates_never_automatically_publish(self):
        self.assertEqual(select.source_pin(self.receipt,123,2,True),"b"*40)
        for flag in (False,None):
            receipt=dict(self.receipt)
            if flag is None:receipt.pop("auto_promote")
            else:receipt["auto_promote"]=flag
            self.assertIsNone(select.source_pin(receipt,123,2,True))
        for field,value in (("source_sha","main"),("producer_attempt",1),("published",True),("auto_promote","true")):
            with self.subTest(field=field),self.assertRaises(ValueError):
                select.source_pin(self.receipt|{field:value},123,2,True)
    def test_archive_metadata_must_be_unique_and_bounded(self):
        def archive(entries):
            wire=io.BytesIO()
            with zipfile.ZipFile(wire,"w") as out:
                for key,value in entries:out.writestr(key,value)
            return wire.getvalue()
        wire=archive([("native-candidate-receipt.json",json.dumps(self.receipt))])
        self.assertEqual(select.document(wire,"native-candidate-receipt.json"),self.receipt)
        for entries in ([("../native-candidate-receipt.json","{}")],
                [("native-candidate-receipt.json","x"*65537)]):
            with self.assertRaises(ValueError):
                select.document(archive(entries),"native-candidate-receipt.json")
    def test_selector_without_signed_artifact_emits_no_release_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/"event.json";event.write_text(json.dumps(self.event),encoding="utf-8")
            output=Path(tmp)/"out"
            env={"GITHUB_REPOSITORY":select.REPO,"GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_run",
                "GITHUB_EVENT_PATH":str(event),"GITHUB_OUTPUT":str(output)}
            with mock.patch.dict(os.environ,env),mock.patch.object(select,"api",side_effect=[self.run,{"total_count":0,"artifacts":[]}]):
                select.main()
            self.assertFalse(output.exists())
    def test_selected_receipt_exports_only_immutable_original_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/"event.json";event.write_text(json.dumps(self.event),encoding="utf-8")
            output=Path(tmp)/"out";wire=io.BytesIO()
            with zipfile.ZipFile(wire,"w") as archive:
                archive.writestr("native-candidate-receipt.json",json.dumps(self.receipt))
            artifacts=[{"id":23,"name":"kyron-signed-native-candidate-123-2","expired":False},
                {"id":24,"name":"kyron-native-receipt-"+"b"*40,"expired":False}]
            env={"GITHUB_REPOSITORY":select.REPO,"GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_run",
                "GITHUB_EVENT_PATH":str(event),"GITHUB_OUTPUT":str(output)}
            with mock.patch.dict(os.environ,env),mock.patch.object(select,"api",
                    side_effect=[self.run,{"total_count":2,"artifacts":artifacts},wire.getvalue()]):
                select.main()
            self.assertEqual(output.read_text(encoding="utf-8"),"ready=true\nsource_sha="+"b"*40+"\nrun_id=123\nattempt=2\n")
    def test_manual_candidate_without_small_receipt_preserves_validation_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            event=Path(tmp)/"event.json";event.write_text(json.dumps(self.event),encoding="utf-8")
            output=Path(tmp)/"out";wire=io.BytesIO()
            doc={"schema":1,"product":"KyronSignedNativeCandidate","source_workspace_sha":"b"*40,
                "run_id":"123","run_attempt":"2","auto_promote":False}
            with zipfile.ZipFile(wire,"w") as archive:archive.writestr("native-candidate.json",json.dumps(doc))
            artifact={"id":23,"name":"kyron-signed-native-candidate-123-2","expired":False}
            env={"GITHUB_REPOSITORY":select.REPO,"GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_run",
                "GITHUB_EVENT_PATH":str(event),"GITHUB_OUTPUT":str(output)}
            with mock.patch.dict(os.environ,env),mock.patch.object(select,"api",
                    side_effect=[self.run,{"total_count":1,"artifacts":[artifact]},wire.getvalue()]):
                select.main()
            self.assertFalse(output.exists())
    def test_automatic_approval_cannot_change_the_original_producer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"event.json";path.write_text(json.dumps({"inputs":{"automatic":"true","source_sha":"b"*40,"signed_run_id":"123","signed_attempt":"2"}}),encoding="utf-8")
            env={"GITHUB_REPOSITORY":select.REPO,"GITHUB_REF":"refs/heads/main","GITHUB_EVENT_NAME":"workflow_dispatch",
                "GITHUB_EVENT_PATH":str(path),"CANDIDATE_RUN_ID":"123","CANDIDATE_ATTEMPT":"2","CANDIDATE_SOURCE_SHA":"b"*40,"AUTOMATIC_NATIVE_PROMOTION":"true"}
            with mock.patch.dict(os.environ,env):
                approval.approval_context()
                os.environ["CANDIDATE_RUN_ID"]="124"
                with self.assertRaises(SystemExit):approval.approval_context()
    def test_direct_producer_request_waits_for_final_completion(self):
        event={"repository":{"full_name":select.REPO},"inputs":{"automatic":"true","source_sha":"b"*40,
            "signed_run_id":"123","signed_attempt":"2"}}
        with mock.patch.dict(os.environ,{"GITHUB_EVENT_NAME":"workflow_dispatch"}):
            fetch=mock.Mock(side_effect=[self.run|{"status":"in_progress","conclusion":None},self.run])
            pause=mock.Mock()
            self.assertEqual(select.requested_producer(event,fetch,pause),(123,2,"b"*40))
            pause.assert_called_once_with(10)
            for inputs in ({"automatic":"false"},{"signed_attempt":"3"},{"source_sha":"main"}):
                changed=copy.deepcopy(event);changed["inputs"].update(inputs)
                with self.subTest(inputs=inputs),self.assertRaises(ValueError):
                    select.requested_producer(changed,mock.Mock(return_value=self.run),mock.Mock())
    def test_pending_producer_never_exports_release_authority(self):
        event={"repository":{"full_name":select.REPO},"inputs":{"automatic":"true","source_sha":"b"*40,
            "signed_run_id":"123","signed_attempt":"2"}}
        with mock.patch.dict(os.environ,{"GITHUB_EVENT_NAME":"workflow_dispatch"}):
            fetch=mock.Mock(return_value=self.run|{"status":"in_progress","conclusion":None})
            self.assertIsNone(select.requested_producer(event,fetch,mock.Mock()))
            self.assertEqual(fetch.call_count,15)
    def test_all_six_original_signed_files_are_hash_verified(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);files={}
            for abi in ("armeabi-v7a","arm64-v8a"):
                for leaf in approval.LEAVES:
                    path=root/abi/leaf;path.parent.mkdir(exist_ok=True);path.write_bytes((abi+leaf).encode())
                    files[f"{abi}/{leaf}"]={"size":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
            doc={"schema":1,"product":"KyronSignedNativeCandidate","source_workspace_sha":"b"*40,
                "run_id":"123","run_attempt":"2","files":files}
            (root/"native-candidate.json").write_text(json.dumps(doc),encoding="utf-8")
            recovery.verified_files(root,doc,"b"*40,"123","2")
            (root/"arm64-v8a/libkyron.so").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):recovery.verified_files(root,doc,"b"*40,"123","2")


class SamePairDeliveryTests(unittest.TestCase):
    def setUp(self):
        import hashlib,types
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source="b"*40;self.current="a"*40;self.original="[fixture]\nunchanged=true\n"
        config=self.root/"Distribution/SrcVersion.ini";config.parent.mkdir(parents=True);config.write_text(self.original,encoding="utf-8")
        self.contract={"generation":4,"minimum_launcher_build":1,"minimum_content_revision":5,"release_channel":"current","insider_channel":"current"}
        self.pair={};self.signed={}
        for bits,abi,_,_ in approval.ABIS:
            folder=self.root/"VeraInternal/lib"/abi;folder.mkdir(parents=True)
            for leaf in approval.LEAVES:
                path=folder/leaf;path.write_bytes((abi+"/"+leaf+"/immutable-original").encode());self.signed[str(path)]=path.read_bytes()
            self.pair[bits]=approval.hashfile(folder/"libkyron.so")
        self.catalog=[];self.commands=[];self.remote=self.current+"\trefs/heads/main"
        self.lib=types.SimpleNamespace(ini=lambda _: {},need=lambda *_:"synthetic-route",
            plan=mock.Mock(return_value={"changed":[],"source":self.original}))
        self.patches=[mock.patch.object(approval,"ROOT",self.root),
            mock.patch.object(approval,"metadata",return_value=self.contract),
            mock.patch.object(approval,"fetch_signed_baseline",return_value=({},5,"c"*40)),
            mock.patch.object(approval,"run",side_effect=self.run_command),
            mock.patch.dict(sys.modules,{"lib_contract_rotation":self.lib,
                "opaque_paths":types.SimpleNamespace(opaque_path=lambda *_:"opaque")}),
            mock.patch.dict(os.environ,{"SOURCE_TOKEN":"synthetic-fixture-token"})]
        for patch in self.patches:patch.start()
    def tearDown(self):
        for patch in reversed(self.patches):patch.stop()
        self.tmp.cleanup()
    def run_command(self,*args,**kwargs):
        self.commands.append(tuple(map(str,args)))
        if args[0]=="gh":return json.dumps(self.catalog)
        if args[-2:]==("rev-parse","HEAD"):return self.current
        if "ls-remote" in args:return self.remote
        raise AssertionError("unexpected mutation/compilation: "+repr(args))
    def existing(self):
        approval.manifest(self.source,self.pair)
        assets=[{"name":"runtime-lane-v1.json","state":"uploaded",
            "size":(self.root/"Distribution/release/runtime-lane-v1.json").stat().st_size,
            "digest":"sha256:"+approval.hashfile(self.root/"Distribution/release/runtime-lane-v1.json")}]
        for _,abi,_,_ in approval.ABIS:
            for leaf in approval.LEAVES:
                path=self.root/"VeraInternal/lib"/abi/leaf
                assets.append({"name":leaf.replace("libkyron","libkyron-"+abi),"state":"uploaded",
                    "size":path.stat().st_size,"digest":"sha256:"+approval.hashfile(path)})
        return {"draft":True,"name":"Kyron local signed delivery "+self.current[:12],
            "target_commitish":self.current,"assets":assets}
    def test_identical_elf_completes_missing_source_receipt_without_rotation(self):
        self.assertEqual(approval.rotate(self.source,self.pair),self.current)
        self.assertEqual((self.root/"Distribution/SrcVersion.ini").read_text(),self.original)
        for path,data in self.signed.items():self.assertEqual(Path(path).read_bytes(),data)
        receipt=json.loads((self.root/"Distribution/release/runtime-lane-v1.json").read_text())
        self.assertEqual(receipt["source_workspace_sha"],self.source)
        self.assertNotEqual(receipt["source_workspace_sha"],self.current)
        self.assertEqual(len(receipt["runtime"]),4)
    def test_complete_matching_source_delivery_remains_noop(self):
        self.catalog=[self.existing()]
        self.assertIsNone(approval.rotate(self.source,self.pair))
    def test_other_source_delivery_does_not_authorize_current_head(self):
        record=self.existing();record["target_commitish"]="d"*40;self.catalog=[record]
        self.assertEqual(approval.rotate(self.source,self.pair),self.current)
    def test_partial_source_delivery_completes_only_verified_receipt(self):
        record=self.existing();record["assets"].pop();self.catalog=[record]
        self.assertEqual(approval.rotate(self.source,self.pair),self.current)
    def test_conflicting_or_duplicate_native_assets_are_rejected(self):
        for field,value in (("digest","sha256:"+"0"*64),("size",1),("state","new")):
            record=self.existing();record["assets"][0][field]=value;self.catalog=[record]
            with self.subTest(field=field),self.assertRaises(SystemExit):approval.rotate(self.source,self.pair)
        record=self.existing();record["assets"].append(dict(record["assets"][0]));self.catalog=[record]
        with self.assertRaises(SystemExit):approval.rotate(self.source,self.pair)
    def test_duplicate_drafts_cannot_select_an_arbitrary_source_receipt(self):
        record=self.existing();self.catalog=[record,copy.deepcopy(record)]
        with self.assertRaises(SystemExit):approval.rotate(self.source,self.pair)
    def test_main_advance_never_publishes_or_relabels_verified_bytes(self):
        self.remote="d"*40+"\trefs/heads/main"
        with self.assertRaises(approval.Superseded):approval.rotate(self.source,self.pair)
        self.assertFalse(any(args[0]=="gh" for args in self.commands))
    def test_source_contract_mismatch_fails_before_receipt_creation(self):
        self.lib.plan.return_value={"changed":[],"source":"different"}
        with self.assertRaises(SystemExit):approval.rotate(self.source,self.pair)
        self.assertFalse((self.root/"Distribution/release/runtime-lane-v1.json").exists())


class AdmissionTests(unittest.TestCase):
    def git(self,*args):
        return subprocess.check_output(["git","-C",str(self.root),*args],stderr=subprocess.DEVNULL,text=True).strip()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/"source";self.root.mkdir()
        self.git("init","-b","main");self.git("config","user.name","fixture")
        self.git("config","user.email","fixture@example.invalid");self.git("config","core.autocrlf","false")
        for rel in ("VeraInternal/jni/native.cpp","Distribution/SrcVersion.ini","Shared/pantry_contract.hpp"):
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("original\n",encoding="utf-8")
        self.git("add",".");self.git("commit","-m","fixture");self.source=self.git("rev-parse","HEAD")
        remote=Path(self.tmp.name)/"origin.git"
        subprocess.check_call(["git","init","--bare",str(remote)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.git("remote","add","origin",str(remote));self.git("push","origin","main")
        self.patches=[mock.patch.object(approval,"ROOT",self.root),mock.patch.object(approval,"approval_context")]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def commit(self,paths):
        for rel in paths:
            path=self.root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text("changed\n",encoding="utf-8")
        self.git("add",".");self.git("commit","-m","fixture change");self.git("push","origin","main")
        return self.git("rev-parse","HEAD")
    def test_exact_original_source_is_admitted(self):
        self.assertEqual(approval.assert_clean(self.source),(self.source,False))
    def test_only_exact_dual_contract_delta_is_preapproved(self):
        head=self.commit(["Distribution/SrcVersion.ini","Shared/pantry_contract.hpp"])
        self.assertEqual(approval.assert_clean(self.source),(head,True))
    def test_dirty_inputs_are_never_automatically_approved(self):
        (self.root/"VeraInternal/jni/native.cpp").write_text("dirty")
        with self.assertRaises(SystemExit):approval.assert_clean(self.source)
    def test_changed_native_inputs_require_new_build(self):
        self.commit(["VeraInternal/jni/native.cpp"])
        real=subprocess.run
        def check(args,**kwargs):
            if args[0]=="pwsh":return subprocess.CompletedProcess(args,3)
            return real(args,**kwargs)
        with mock.patch.object(subprocess,"run",side_effect=check):
            with self.assertRaises(approval.Superseded):approval.assert_clean(self.source)

if __name__=="__main__":unittest.main(verbosity=2)
