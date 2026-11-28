"""Exercise step-only supersession with real Git ancestry; never cancel successful siblings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = Path(os.environ.get('KYRON_HOSTED_STEP_SCRIPT', ROOT / '.github/scripts/Invoke-HostedReleaseStep.ps1'))


class HostedSupersessionTests(unittest.TestCase):
    def setUp(self):
        self.pwsh = os.environ.get('KYRON_TEST_PWSH') or shutil.which('pwsh')
        self.assertTrue(self.pwsh, 'PowerShell is required for the hosted step fixtures')
        self.temporary = tempfile.TemporaryDirectory(prefix='kyron-hosted-step-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/pvtkyron/Workspace.git')
        self.git('commit', '-q', '--allow-empty', '-m', 'fixture source')
        self.source_sha = self.git('rev-parse', 'HEAD')
        self.main_sha = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'), '-p', self.source_sha, '-m', 'new source')
        self.output = self.root / 'output'
        self.requests = []
        self.api_status = 202
        self.run_metadata = {'id': 123, 'run_attempt': 2, 'head_sha': 'a' * 40}
        self.jobs = []
        case = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                case.requests.append(('GET',self.path))
                payload = {'total_count': len(case.jobs), 'jobs': case.jobs} if '/jobs?' in self.path else case.run_metadata
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
                case.requests.append((self.path, self.headers.get('Authorization'), body))
                self.send_response(case.api_status)
                self.end_headers()
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.env = os.environ | {
            'RUNNER_TEMP': str(self.root), 'GITHUB_ACTIONS': 'true',
            'GITHUB_REPOSITORY': 'pvtkyron/pantry-core', 'GITHUB_REF': 'refs/heads/main',
            'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_JOB': 'exe',
            'GITHUB_SHA': 'a' * 40, 'GITHUB_TOKEN': 'synthetic-fixture-token',
            'GITHUB_OUTPUT': str(self.output),
            'GITHUB_API_URL': f'http://127.0.0.1:{self.server.server_port}',
            'TEST_SOURCE_SHA': self.source_sha, 'TEST_MAIN_SHA': self.main_sha,
        }
        self.producer = self.root / 'producer.ps1'
        self.producer.write_text('''$ErrorActionPreference='Stop'
if($env:TEST_MODE-eq'success'){[IO.File]::AppendAllText($env:GITHUB_OUTPUT,"result=verified`n");exit 0}
if($env:TEST_MODE-eq'compiler'){throw 'fixture compiler failure'}
if($env:TEST_MODE-eq'exit'){exit 17}
if($env:TEST_MODE-eq'text'){throw '[KYRON][RELEASE/SYNC][BLOCKED] Workspace HEAD differs from GitHub main'}
$record=[ordered]@{schema=1;kind='workspace-source-superseded';run_id=$env:GITHUB_RUN_ID;run_attempt=$env:GITHUB_RUN_ATTEMPT;job_id=$env:GITHUB_JOB;workflow_repository=$env:GITHUB_REPOSITORY;workflow_sha=$env:GITHUB_SHA;source_sha=$env:TEST_SOURCE_SHA;main_sha=$env:TEST_MAIN_SHA;scope='Launcher'}
if($env:TEST_FIELD){$record[$env:TEST_FIELD]=$env:TEST_VALUE}
$payload=if($env:TEST_MODE-eq'malformed'){'{invalid'}else{$record|ConvertTo-Json -Compress}
[IO.File]::WriteAllText($env:KYRON_HOSTED_SUPERSESSION_RECORD,$payload)
throw 'outer build wrapper failed'
''', encoding='utf-8')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args], text=True).strip()

    def run_step(self, mode, **env):
        self.output.write_text('')
        return subprocess.run([self.pwsh, '-NoLogo', '-NoProfile', '-NonInteractive', '-File', str(WRAPPER),
                               '-Script', str(self.producer), '-SourceRoot', str(self.source)],
                              cwd=self.root, env=self.env | {'TEST_MODE': mode} | env,
                              text=True, capture_output=True, timeout=20)

    def test_success_preserves_outputs_without_cancelling(self):
        result = self.run_step('success')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), 'result=verified\n')
        self.assertEqual(self.requests, [])

    def test_real_failures_and_matching_error_text_remain_failures(self):
        for mode in ('compiler', 'exit', 'text'):
            with self.subTest(mode=mode):
                result = self.run_step(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('superseded=true', self.output.read_text())
        self.assertEqual(self.requests, [])

    def test_attested_supersession_skips_only_this_step_and_retains_verified_outputs(self):
        proof=self.root/'successful-sibling.enc';proof.write_bytes(b'verified-original-artifact')
        result = self.run_step('superseded')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.output.read_text(), 'superseded=true\n')
        self.assertIn('[HOSTED/SOURCE][SKIP]', result.stdout)
        self.assertNotIn('::error', result.stdout + result.stderr)
        self.assertEqual(proof.read_bytes(),b'verified-original-artifact')
        self.assertEqual(self.git('rev-parse','HEAD'),self.source_sha)
        self.assertEqual(list(self.root.glob('kyron-source-supersession-*.json')), [])

    def test_supersession_survives_a_nested_powershell_failure(self):
        child = self.producer
        self.producer = self.root / 'nested.ps1'
        self.producer.write_text('& $env:TEST_PWSH -NoLogo -NoProfile -File $env:TEST_CHILD\nif($LASTEXITCODE){throw "nested build failed"}\n')
        result = self.run_step('superseded', TEST_PWSH=self.pwsh, TEST_CHILD=str(child))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.output.read_text(), 'superseded=true\n')

    def test_malformed_or_foreign_records_never_cancel(self):
        result = self.run_step('malformed')
        self.assertNotEqual(result.returncode, 0)
        for field, value in (('schema', '2'), ('kind', 'compiler-error'), ('run_id', '124'),
                             ('run_attempt', '1'), ('job_id', 'other'),
                             ('workflow_repository', 'other/repository'), ('workflow_sha', 'b' * 40),
                             ('source_sha', 'b' * 40), ('main_sha', self.source_sha), ('scope', 'arbitrary')):
            with self.subTest(field=field):
                result = self.run_step('superseded', TEST_FIELD=field, TEST_VALUE=value)
                self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])

    def test_rewritten_history_and_foreign_origin_never_cancel(self):
        unrelated = self.git('commit-tree', self.git('rev-parse', 'HEAD^{tree}'), '-m', 'rewritten root')
        result = self.run_step('superseded', TEST_MAIN_SHA=unrelated)
        self.assertNotEqual(result.returncode, 0)
        self.git('remote', 'set-url', 'origin', 'https://github.com/other/repository.git')
        result = self.run_step('superseded')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])

    def test_supersession_needs_no_api_token_or_reachable_api(self):
        result=self.run_step('superseded',GITHUB_TOKEN='',GITHUB_API_URL='http://127.0.0.1:1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.output.read_text(),'superseded=true\n')
        self.assertEqual(self.requests,[])

    def test_successful_or_failed_siblings_are_never_modified(self):
        for conclusion in ('success','failure','timed_out','action_required'):
            with self.subTest(conclusion=conclusion):
                self.jobs=[{'id':456,'conclusion':conclusion}]
                before=json.dumps(self.jobs)
                result=self.run_step('superseded')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.dumps(self.jobs),before)
                self.assertEqual(self.requests,[])
                self.assertEqual(self.output.read_text(),'superseded=true\n')

    def test_newer_attempt_is_never_looked_up_or_cancelled(self):
        self.run_metadata['run_attempt']=3
        result=self.run_step('superseded')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.requests,[])


class SupersededPublicationTests(unittest.TestCase):
    @staticmethod
    def evaluate(expression,context):
        import re
        value=expression.strip().removeprefix('${{').removesuffix('}}').strip()
        value=value.replace('always()','True').replace('cancelled()','False')
        value=re.sub(r'\b(?:needs|github|inputs)\.[A-Za-z0-9_.]+',
                     lambda match:repr(context.get(match[0],'')),value)
        value=value.replace('&&',' and ').replace('||',' or ')
        value=re.sub(r'!(?!=)',' not ',value)
        value=re.sub(r'\btrue\b','True',value);value=re.sub(r'\bfalse\b','False',value)
        value=value.replace("'True'","'true'").replace("'False'","'false'")
        return bool(eval(value,{'__builtins__':{}},{}))

    def test_completed_builds_remain_green_and_superseded_publication_skips(self):
        import yaml
        root=Path(os.environ.get('KYRON_WORKFLOW_ROOT',ROOT))
        checks=(
            ('patisserie.yml','publish','workspace'),
            ('launcher-publish.yml','publish','launcher'),
        )
        for file,job,owner in checks:
            expression=yaml.safe_load((root/'.github/workflows'/file).read_text())['jobs'][job]['if']
            context={'github.event_name':'workflow_dispatch','github.repository':'pvtkyron/pantry-core',
                     'github.ref':'refs/heads/main','inputs.request':'',
                     f'needs.{owner}.result':'success',f'needs.{owner}.outputs.delivery_pending':'false',
                     f'needs.{owner}.outputs.superseded':'false'}
            if file=='patisserie.yml':
                context.update({'needs.doctor.result':'success','needs.workspace.outputs.delivery_capsule':'verified-delivery-capsule'})
            with self.subTest(file=file,state='verified'):
                self.assertTrue(self.evaluate(expression,context))
            context[f'needs.{owner}.outputs.superseded']='true'
            with self.subTest(file=file,state='superseded'):
                self.assertFalse(self.evaluate(expression,context))
            context[f'needs.{owner}.outputs.superseded']='false'
            context[f'needs.{owner}.result']='failure'
            with self.subTest(file=file,state='actual failure'):
                self.assertFalse(self.evaluate(expression,context))

    def test_runtime_smoke_resolves_manual_source_and_reuses_authenticated_callers(self):
        import yaml
        root=Path(os.environ.get('KYRON_WORKFLOW_ROOT',ROOT))
        doc=yaml.safe_load((root/'.github/workflows/headless.yml').read_text())
        self.assertIs(doc['on']['workflow_call']['inputs']['capsule']['required'],True)
        self.assertIs(doc['on']['workflow_dispatch']['inputs']['capsule']['required'],False)
        self.assertEqual(doc['jobs']['test']['needs'],'sources')
        context={'github.event_name':'workflow_dispatch','github.workflow':'Pantry Runtime Smoke',
                 'github.repository':'pvtkyron/pantry-core','github.ref':'refs/heads/main','inputs.capsule':''}
        self.assertTrue(self.evaluate(doc['jobs']['sources']['if'],context))
        context['github.workflow']='Component · Launcher'
        self.assertFalse(self.evaluate(doc['jobs']['sources']['if'],context))
        for result,expected in (('success',True),('skipped',True),('failure',False)):
            self.assertEqual(self.evaluate(doc['jobs']['test']['if'],context|{'needs.sources.result':result}),expected)
        caller=yaml.safe_load((root/'.github/workflows/launcher-publish.yml').read_text())['jobs']['headless']
        context={'needs.publish.result':'success','needs.launcher.outputs.superseded':'false'}
        self.assertTrue(self.evaluate(caller['if'],context))
        context['needs.launcher.outputs.superseded']='true'
        self.assertFalse(self.evaluate(caller['if'],context))

if __name__ == '__main__':
    unittest.main()
