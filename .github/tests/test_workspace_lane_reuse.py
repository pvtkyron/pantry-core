"""Exercise real encrypted output rejection and the Actions reuse transaction."""
import copy
import hashlib
import hmac
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile
import os
import subprocess
import tempfile
import yaml
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.github/scripts'))
spec=importlib.util.spec_from_file_location('reuse',ROOT/'.github/scripts/reuse_workspace_lanes.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SOURCE='a'*40;OLD='b'*40;CURRENT='c'*40;SECRET='fixture only'

def archive(lane='java',source=SOURCE,*,tamper=False,path='source/Launcher/lib/output.bin'):
    files={} if lane=='java' else {path:b'synthetic signed output'}
    if lane=='delivery':
        files['source/Distribution/release/runtime-lane-v1.json']=json.dumps({'schema':1,'mode':'all'}).encode()
        files['source/Distribution/client/Launcher.build.json']=json.dumps({'schema':1,'launch_epoch':31}).encode()
    manifest={'schema':1,'lane':lane,'workspace_sha':source,'pantry_sha':source,
              'files':[{'path':p,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()} for p,b in files.items()]}
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:
        if lane=='java':z.writestr('source/',b'')
        z.writestr('handoff.json',json.dumps(manifest))
        for p,b in files.items():z.writestr(p,b+'changed' .encode() if tamper else b)
    material=hashlib.sha512(('kyron-ci-handoff-v1\0'+SECRET).encode()).digest()
    padder=padding.PKCS7(128).padder();plain=padder.update(payload.getvalue())+padder.finalize()
    iv=bytes(range(16));e=Cipher(algorithms.AES(material[:32]),modes.CBC(iv)).encryptor()
    body=b'KYRONCI1'+iv+e.update(plain)+e.finalize();blob=body+hmac.digest(material[32:],body,'sha256')
    outer=io.BytesIO()
    with zipfile.ZipFile(outer,'w') as z:z.writestr('kyron/aa/bb/'+'1'*28+'.bin',blob)
    wire=outer.getvalue()
    return wire,'sha256:'+hashlib.sha256(wire).hexdigest()

def tree():
    paths={p for v in m.INPUTS.values() for p in v}
    return {'truncated':False,'tree':[{'path':p+'action.yml' if p.endswith('/') else p,
             'type':'blob','mode':'100644','sha':hashlib.sha1(p.encode()).hexdigest()} for p in paths]}

class EnvelopeTests(unittest.TestCase):
    def test_exact_encrypted_original_is_accepted(self):
        for lane in ('java','exe','delivery'):
            with self.subTest(lane=lane):self.assertTrue(m.unpack_archive(*archive(lane),lane,SOURCE,SECRET))
    def test_delivery_cannot_reuse_a_different_channel_or_older_epoch(self):
        wire,digest=archive('delivery')
        self.assertFalse(m.unpack_archive(wire,digest,'delivery',SOURCE,SECRET,'release'))
        self.assertFalse(m.unpack_archive(wire,digest,'delivery',SOURCE,SECRET,minimum_epoch=32))
        self.assertTrue(m.unpack_archive(wire,digest,'delivery',SOURCE,SECRET,minimum_epoch=31))
    def test_dotnet_empty_java_directory_is_valid_for_a_different_source(self):
        self.assertFalse(m.unpack_archive(*archive('java',source=OLD),'java',SOURCE,SECRET))
    def test_another_authenticated_source_is_a_miss(self):
        self.assertFalse(m.unpack_archive(*archive(source=OLD),'java',SOURCE,SECRET))
    def test_wrong_secret_and_bad_transport_fail(self):
        wire,digest=archive()
        for args in ((wire,digest,'java',SOURCE,'wrong'),(wire+'x'.encode(),digest,'java',SOURCE,SECRET)):
            with self.subTest(args=args[2:]):
                with self.assertRaises(ValueError):m.unpack_archive(*args)
    def test_authenticated_file_digest_drift_is_fatal(self):
        with self.assertRaisesRegex(ValueError,'digest mismatch'):m.unpack_archive(*archive('exe',tamper=True),'exe',SOURCE,SECRET)
    def test_authenticated_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'path rejected'):m.unpack_archive(*archive('exe',path='source/../leak'),'exe',SOURCE,SECRET)
    def test_unrelated_doctor_change_keeps_compiler_recipe(self):
        before=tree();after=copy.deepcopy(before)
        after['tree'].append({'path':'.github/workflows/doctor.yml','mode':'100644','type':'blob','sha':'f'*40})
        for lane in m.INPUTS:self.assertEqual(m.recipe_fingerprint(before,lane),m.recipe_fingerprint(after,lane))
    def test_changed_compiler_recipe_is_invalidated(self):
        before=tree();after=copy.deepcopy(before)
        next(r for r in after['tree'] if r['path']=='.github/workflows/workspace-exe.yml')['sha']='f'*40
        self.assertNotEqual(m.recipe_fingerprint(before,'exe'),m.recipe_fingerprint(after,'exe'))
        self.assertEqual(m.recipe_fingerprint(before,'java'),m.recipe_fingerprint(after,'java'))
    def test_incomplete_tree_is_rejected(self):
        for t in ({'truncated':True,'tree':[]},{'truncated':False,'tree':[]}):
            with self.assertRaises(ValueError):m.recipe_fingerprint(t,'exe')

class FakeAPI:
    def __init__(self,*,lane='delivery',source=SOURCE,job='success',expired=False,changed=False,event='workflow_dispatch',fork=False):
        self.lane=lane;self.job=job;self.expired=expired;self.changed=changed;self.downloads=0
        self.wire,self.digest=archive(lane,source)
        self.run={'id':17,'head_sha':OLD,'head_branch':'main','path':'.github/workflows/patisserie.yml',
                  'event':event,'conclusion':'failure','repository':{'full_name':m.REPO},
                  'head_repository':{'full_name':'fixture/fork' if fork else m.REPO}}
    def json(self,path):
        if path.startswith('git/trees/'):
            t=tree()
            if self.changed and OLD in path:
                for row in t['tree']:row['sha']='f'*40
            return t
        if path.startswith('actions/runs?'):return {'workflow_runs':[self.run]}
        if path.endswith('/jobs?per_page=100'):
            suffix={'java':'Compile Pantry Java + D8','exe':'Compile signed Windows launcher','delivery':'Restore lanes + prepare private Pantry'}[self.lane]
            return {'jobs':[{'name':'Workspace / '+suffix,'conclusion':self.job}]}
        if path.endswith('/artifacts?per_page=100'):
            return {'artifacts':[{'id':31,'name':f'kyron-workspace-{self.lane}-17-2','expired':self.expired,'size_in_bytes':len(self.wire),'digest':self.digest}]}
        raise AssertionError(path)
    def bytes(self,path):
        self.downloads+=1;return self.wire

class TransactionTests(unittest.TestCase):
    def test_failed_doctor_does_not_discard_successful_prepare(self):
        result=m.select_lanes(FakeAPI(),CURRENT,SOURCE,SECRET,20)
        self.assertEqual(result,{'delivery':{'run_id':'17','attempt':'2'}})
    def test_failed_prepare_can_reuse_just_successful_compiler(self):
        self.assertEqual(m.select_lanes(FakeAPI(lane='exe'),CURRENT,SOURCE,SECRET,20),{'exe':{'run_id':'17','attempt':'2'}})
    def test_failed_cancelled_or_expired_lane_is_never_accepted(self):
        for kwargs in ({'job':'failure'},{'job':'cancelled'},{'expired':True},{'changed':True},{'source':'d'*40},{'fork':True},{'event':'pull_request'}):
            with self.subTest(kwargs=kwargs):self.assertEqual(m.select_lanes(FakeAPI(**kwargs),CURRENT,SOURCE,SECRET,20),{})
    def test_rerun_reuses_a_completed_original_attempt(self):
        api=FakeAPI()
        self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,17,current_attempt=3),{'delivery':{'run_id':'17','attempt':'2'}})
    def test_direct_launcher_preparation_is_reused_with_actual_seal_and_upload_evidence(self):
        api=FakeAPI();api.run['path']='.github/workflows/launcher-publish.yml'
        old=api.json
        def json_api(path):
            if path.endswith('/jobs?per_page=100'):
                return {'jobs':[{'name':'Launcher / Compile signed Windows launcher','conclusion':'success','steps':[
                    {'name':'Seal prepared generated delivery for canonical publisher','conclusion':'success'},
                    {'name':'Upload encrypted prepared delivery','conclusion':'success'}]}]}
            return old(path)
        api.json=json_api
        self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,20),{'delivery':{'run_id':'17','attempt':'2'}})
        api.json=lambda path: {'jobs':[{'name':'Launcher / Compile signed Windows launcher','conclusion':'success','steps':[]}]} if path.endswith('/jobs?per_page=100') else old(path)
        self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,20),{})
    def test_failed_publication_keeps_independently_verified_compiler_outputs(self):
        api=FakeAPI(lane='exe',job='failure');old=api.json
        complete=['Compile and verify signed launcher lane','Seal executable lane','Upload encrypted executable lane']
        api.json=lambda path: {'jobs':[{'name':'Launcher / Compile signed Windows launcher','conclusion':'failure','steps':[{'name':n,'conclusion':'success'} for n in complete]}]} if path.endswith('/jobs?per_page=100') else old(path)
        self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,20),{'exe':{'run_id':'17','attempt':'2'}})
        api.json=lambda path: {'jobs':[{'name':'Launcher / Compile signed Windows launcher','conclusion':'failure','steps':[{'name':n,'conclusion':'success'} for n in complete[1:]]}]} if path.endswith('/jobs?per_page=100') else old(path)
        self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,20),{})
    def test_cannot_reuse_current_running_transaction(self):
        api=FakeAPI();self.assertEqual(m.select_lanes(api,CURRENT,SOURCE,SECRET,17),{});self.assertEqual(api.downloads,0)

class MirrorContinuationTests(unittest.TestCase):
    def test_actual_mirror_accepts_successful_cached_delivery_upload_only(self):
        graph=yaml.safe_load((ROOT/'.github/workflows/project-workspace.yml').read_text())
        mirror=yaml.safe_load((ROOT/'.github/workflows/pantry-mirror.yml').read_text())
        verifier=next(step['run'] for step in mirror['jobs']['publish']['steps'] if step.get('name')=='Verify prepared delivery producer')
        steps=[{'name':step['name'],'conclusion':'success'} for step in graph['jobs']['carry']['steps']]
        with tempfile.TemporaryDirectory(prefix='mirror-cache-continuation-') as raw:
            root=Path(raw);binary=root/'bin';binary.mkdir()
            gh=binary/'gh'
            gh.write_text("#!/usr/bin/env python3\nimport json,os,subprocess,sys\nfrom pathlib import Path\n"
                "data=json.loads(Path(os.environ['FIXTURE_JOBS']).read_text()) if '/jobs?' in sys.argv[2] else "
                "{'repository':{'full_name':'pvtkyron/pantry-core'},'head_repository':{'full_name':'pvtkyron/pantry-core'},'head_branch':'main','run_attempt':2,'event':'repository_dispatch','path':'.github/workflows/patisserie.yml'}\n"
                "if '--jq' in sys.argv:\n r=subprocess.run(['jq','-r',sys.argv[sys.argv.index('--jq')+1]],input=json.dumps(data),text=True,capture_output=True);sys.stdout.write(r.stdout);raise SystemExit(r.returncode)\n"
                "print(json.dumps(data))\n")
            gh.chmod(0o755);script=root/'verify.sh';script.write_text(verifier)
            jobs=root/'jobs.json'
            for conclusion,provided,accepted in [('success',steps,True),('failure',steps,False),
                    ('success',[{'name':'Forward exact encrypted bytes to this publisher','conclusion':'success'}],False)]:
                jobs.write_text(json.dumps({'jobs':[{'conclusion':conclusion,'steps':provided}]}))
                result=subprocess.run(['bash',str(script)],capture_output=True,text=True,env=os.environ|{
                    'PATH':str(binary)+':'+os.environ['PATH'],'GH_TOKEN':'synthetic-not-a-credential',
                    'DELIVERY_RUN_ID':'123','DELIVERY_RUN_ATTEMPT':'2','GITHUB_REPOSITORY':'pvtkyron/pantry-core','FIXTURE_JOBS':str(jobs)})
                self.assertEqual(result.returncode==0,accepted,result.stderr)
                self.assertNotIn('synthetic-not-a-credential',result.stdout+result.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
