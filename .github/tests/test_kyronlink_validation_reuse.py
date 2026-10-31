"""Authenticate original KyronLink proof and compare its actual protected Git trees."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('kyron_validation',SCRIPTS/'kyronlink_validation_status.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class KyronLinkProofReuse(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kyronlink-proof-');self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.workspace=root/'workspace';self.recipe=root/'recipe'
        for repo in (self.workspace,self.recipe):
            repo.mkdir();self.git(repo,'init','-q');self.git(repo,'config','user.name','Fixture');self.git(repo,'config','user.email','fixture@example.invalid')
        self.write(self.workspace,'KyronLink/Main.java','managed input\n')
        self.write(self.workspace,'VeraInternal/Native.cpp','native input\n')
        self.write(self.workspace,'Distribution/SrcVersion.ini','approved contract\n')
        self.write(self.workspace,'Shared/pantry_contract.hpp','generated metadata\n')
        self.write(self.workspace,'Launcher/Proxy.cs','coupled consumer\n')
        self.original=self.commit(self.workspace)
        self.write(self.recipe,M.VALIDATION_RECIPE[0],'name: actual Android validation\n')
        self.public=self.commit(self.recipe)
        self.receipt={'schema':1,'workspace_sha':self.original,'producer_run_id':123,'validated':True,'published':False}
        self.item={'id':31,'name':'kyronlink-validation-'+self.original,'expired':False,'created_at':'2026-10-30',
            'size_in_bytes':400,'workflow_run':{'id':123,'head_branch':'main','repository_id':1,'head_repository_id':1}}
    def git(self,root,*args):
        return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL,text=True).strip()
    def write(self,root,path,text):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    def commit(self,root):
        self.git(root,'add','-A');self.git(root,'commit','-qm','fixture input');return self.git(root,'rev-parse','HEAD')
    def fetch(self,url,token):
        if 'name=' in url:
            return {'artifacts':[self.item] if url.endswith(self.item['name']) else []}
        if '/actions/artifacts?' in url:return {'artifacts':[self.item]}
        if '/jobs?' in url:
            return {'jobs':[{'name':'Kyron Link Java, D8, Mundo and network behavior','conclusion':'success','steps':[
                {'name':n,'conclusion':'success'} for n in ('Run actual Android builds and network behavior without skips',
                'Prepare exact KyronLink source validation receipt','Preserve small KyronLink validation receipt')]}]}
        return {'repository':{'full_name':M.REPO},'head_branch':'main','status':'completed','conclusion':'success',
            'event':'repository_dispatch','path':M.VALIDATION_RECIPE[0],'head_sha':self.public}
    def download(self,command,**kwargs):
        self.assertEqual(command[-3],self.item['name'])
        (Path(command[-1])/'kyronlink-validation.json').write_text(json.dumps(self.receipt))
        return SimpleNamespace(returncode=0)
    def check(self):
        current=self.git(self.workspace,'rev-parse','HEAD')
        original_run=subprocess.run
        def dispatch(command,**kwargs):
            return self.download(command,**kwargs) if command[0]=='gh' else original_run(command,**kwargs)
        with patch.object(M,'get_json',side_effect=self.fetch),patch.object(M.subprocess,'run',side_effect=dispatch):
            return M.previously_validated(current,'synthetic-token',self.workspace,self.recipe)
    def test_exact_original_source_is_valid(self):self.assertTrue(self.check())
    def test_native_and_projection_changes_reuse_original_proof_without_relabelling(self):
        for path in ('VeraInternal/Native.cpp','Distribution/SrcVersion.ini','Shared/pantry_contract.hpp'):
            self.write(self.workspace,path,'changed independent Native input\n')
        current=self.commit(self.workspace)
        self.assertTrue(self.check());self.assertNotEqual(current,self.receipt['workspace_sha'])
        self.assertEqual(self.receipt['workspace_sha'],self.original)
    def test_android_launcher_toolchain_and_other_shared_changes_invalidate(self):
        for path in ('KyronLink/Main.java','Launcher/Proxy.cs','etc/toolchain.json','Shared/Other.hpp'):
            with self.subTest(path=path):
                self.write(self.workspace,path,'changed protected input\n');self.commit(self.workspace)
                self.assertFalse(self.check())
    def test_changed_validation_recipe_requires_new_validation(self):
        self.write(self.recipe,M.VALIDATION_RECIPE[0],'name: changed Android validation\n');self.commit(self.recipe)
        self.assertFalse(self.check())
    def test_receipt_source_is_not_relabelled_to_current_source(self):
        self.write(self.workspace,'VeraInternal/Native.cpp','new independent native\n');current=self.commit(self.workspace)
        self.receipt['workspace_sha']=current
        with self.assertRaisesRegex(ValueError,'content or source pin'):self.check()
    def test_foreign_artifact_owner_stays_fatal(self):
        self.item['workflow_run']['head_repository_id']=9
        with self.assertRaisesRegex(ValueError,'artifact identity'):self.check()

if __name__=='__main__':unittest.main(verbosity=2)
