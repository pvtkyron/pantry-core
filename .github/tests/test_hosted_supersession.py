"""Exercise hosted step outcomes with real Git ancestry and a loopback GitHub API."""
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

    def test_attested_supersession_cancels_only_the_current_run(self):
        result = self.run_step('superseded')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requests, [('/repos/pvtkyron/pantry-core/actions/runs/123/cancel',
                                         'Bearer synthetic-fixture-token', b'{}')])
        self.assertEqual(self.output.read_text(), 'superseded=true\n')
        self.assertIn('[HOSTED/SOURCE][SKIP]', result.stdout)
        self.assertNotIn('::error', result.stdout + result.stderr)
        self.assertEqual(list(self.root.glob('kyron-source-supersession-*.json')), [])

    def test_supersession_survives_a_nested_powershell_failure(self):
        child = self.producer
        self.producer = self.root / 'nested.ps1'
        self.producer.write_text('& $env:TEST_PWSH -NoLogo -NoProfile -File $env:TEST_CHILD\nif($LASTEXITCODE){throw "nested build failed"}\n')
        result = self.run_step('superseded', TEST_PWSH=self.pwsh, TEST_CHILD=str(child))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.requests), 1)
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

    def test_rejected_cancellation_stays_failed_and_blocks_continuation(self):
        self.api_status = 403
        result = self.run_step('superseded')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), 'superseded=true\n')
        self.assertNotIn('[HOSTED/SOURCE][SKIP]', result.stdout)
        self.assertEqual(len(self.requests), 1)

    def test_a_real_sibling_failure_is_not_hidden_by_cancellation(self):
        for conclusion in ('failure', 'timed_out', 'action_required'):
            with self.subTest(conclusion=conclusion):
                self.jobs = [{'id': 456, 'conclusion': conclusion}]
                result = self.run_step('superseded')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.output.read_text(), 'superseded=true\n')
        self.assertEqual(self.requests, [])

    def test_a_newer_run_attempt_cannot_be_cancelled(self):
        self.run_metadata['run_attempt'] = 3
        result = self.run_step('superseded')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])


class ReusableWorkflowPermissionTests(unittest.TestCase):
    def test_cancellation_permission_reaches_every_reusable_caller(self):
        import yaml
        root = Path(os.environ.get('KYRON_WORKFLOW_ROOT', ROOT))
        documents = {path.name: yaml.safe_load(path.read_text(encoding='utf-8-sig'))
                     for path in (root / '.github/workflows').glob('*.yml')}
        overlays = os.environ.get('KYRON_WORKFLOW_CANDIDATES')
        if overlays:
            for path, item in json.loads(Path(overlays).read_text(encoding='utf-8-sig')).items():
                documents[Path(path).name] = yaml.safe_load(item['content'])
        self.assertTrue(documents, 'Maintained workflows must be available')

        def requires_cancellation(name, seen=()):
            self.assertNotIn(name, seen, 'Reusable workflow cycle')
            for job in documents[name]['jobs'].values():
                if any('Invoke-HostedReleaseStep.ps1' in step.get('shell', '') for step in job.get('steps', [])):
                    return True
                uses = job.get('uses', '')
                if uses.startswith('./.github/workflows/') and requires_cancellation(Path(uses).name, seen + (name,)):
                    return True
            return False

        checked = 0
        for name, document in documents.items():
            for job_id, job in document['jobs'].items():
                uses = job.get('uses', '')
                wraps = any('Invoke-HostedReleaseStep.ps1' in step.get('shell', '') for step in job.get('steps', []))
                calls = uses.startswith('./.github/workflows/') and requires_cancellation(Path(uses).name)
                if not (wraps or calls):
                    continue
                permission = job.get('permissions', document.get('permissions', {}))
                with self.subTest(workflow=name, job=job_id):
                    self.assertTrue(permission == 'write-all' or isinstance(permission, dict) and permission.get('actions') == 'write',
                                    'Quiet cancellation requires actions:write at every reusable call boundary')
                checked += 1
        self.assertGreater(checked, 3)


if __name__ == '__main__':
    unittest.main()
