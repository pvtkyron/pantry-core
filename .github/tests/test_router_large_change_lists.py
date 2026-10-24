"""Run the real scheduled router scripts with large Git changes and fake GitHub I/O."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
BASE, NEXT = 'a' * 40, 'b' * 40


@unittest.skipUnless(shutil.which('bash') and shutil.which('jq'), 'bash and jq required')
class LargeChangeRoutingTests(unittest.TestCase):
    def execute_router(self, workflow, step_name, paths, mode, *, diff_failure="", partial="", expected_exit=99):
        variable = 'KYRON_SOURCE_WATCH' if workflow == 'source-watch.yml' else 'KYRON_PANTRY_WATCH'
        path = Path(os.environ.get(variable, ROOT / '.github/workflows' / workflow))
        doc = yaml.safe_load(path.read_text())
        step = next(s for job in doc['jobs'].values() for s in job.get('steps', [])
                    if s.get('name') == step_name)
        with tempfile.TemporaryDirectory(prefix='kyron-router-large-') as temporary:
            case = Path(temporary)
            bindir = case / 'bin'
            bindir.mkdir()
            changed = case / 'changed'
            changed.write_text('\n'.join(paths) + '\n')
            events = case / 'events'
            events.touch()
            fake_git = '''#!/usr/bin/env python3
import os, pathlib, sys
args=sys.argv[1:]; root=''
if args[:1]==['-C']: root=args[1]; args=args[2:]
if args[0]=='fetch':
    exact=args[-2:]==[os.environ['FIXTURE_BASE'],os.environ['FIXTURE_NEXT']]
    if exact:
        if os.environ['FIXTURE_DIFF_FAILURE']=='fetch': raise SystemExit(128)
        pathlib.Path(os.environ['FIXTURE_REFRESHED']).touch()
    sys.exit(0)
if args[0]=='cat-file': sys.exit(0)
if args[0]=='rev-parse':
    if 'refs/remotes/origin/main' in args:
        switched=pathlib.Path(os.environ['FIXTURE_POLLED']).exists()
        print(os.environ['FIXTURE_NEXT'] if root=='source/Distribution' or root=='workspace' and switched else os.environ['FIXTURE_BASE'])
    else: print('c'*40)
    sys.exit(0)
if args[0]=='diff':
    if '--relative=Distribution' not in args:
        failure=os.environ['FIXTURE_DIFF_FAILURE']
        refreshed=pathlib.Path(os.environ['FIXTURE_REFRESHED']).exists()
        if failure and (failure=='permanent' or not refreshed):
            print(os.environ['FIXTURE_PARTIAL'],end='')
            print('fatal: fixture comparison objects unavailable',file=sys.stderr)
            raise SystemExit(128)
        print(pathlib.Path(os.environ['FIXTURE_CHANGED']).read_text(),end='')
    sys.exit(0)
raise SystemExit('unexpected Git request '+repr(args))
'''
            fake_gh = '''#!/usr/bin/env python3
import json, os, sys
if sys.argv[1:2]==['api'] and '--method' in sys.argv:
    with open(os.environ['FIXTURE_EVENTS'],'a') as f: f.write(json.dumps(json.load(sys.stdin))+'\\n')
elif sys.argv[1:2]==['api']: print(os.environ['FIXTURE_BASE'])
else: raise SystemExit('unexpected GitHub request')
'''
            fake_sleep = '''#!/usr/bin/env python3
import os, pathlib
p=pathlib.Path(os.environ['FIXTURE_POLLED'])
if os.environ['FIXTURE_MODE']=='workspace' and not p.exists(): p.touch(); raise SystemExit(0)
raise SystemExit(99)
'''
            for name, source in [('git', fake_git), ('gh', fake_gh), ('sleep', fake_sleep)]:
                command = bindir / name
                command.write_text(source)
                command.chmod(0o755)
            classifier = case / 'recipe/.github/scripts/classify_workspace_change.sh'
            classifier.parent.mkdir(parents=True)
            shutil.copyfile(Path(os.environ.get('KYRON_ROUTER_CLASSIFIER', ROOT / '.github/scripts/classify_workspace_change.sh')), classifier)
            script = case / 'router.sh'
            script.write_text(step['run'])
            env = os.environ | {
                'PATH': str(bindir) + ':' + os.environ['PATH'], 'POLL_SECONDS': '0',
                'GITHUB_REPOSITORY': 'fixture/pantry-core', 'FIXTURE_MODE': mode,
                'FIXTURE_BASE': BASE, 'FIXTURE_NEXT': NEXT,
                'FIXTURE_CHANGED': str(changed), 'FIXTURE_EVENTS': str(events),
                'FIXTURE_POLLED': str(case / 'polled'),
                'FIXTURE_DIFF_FAILURE': diff_failure, 'FIXTURE_PARTIAL': partial,
                'FIXTURE_REFRESHED': str(case / 'refreshed'),
            }
            result = subprocess.run(['bash', '-e', '-o', 'pipefail', str(script)],
                                    cwd=case, env=env, capture_output=True, text=True, timeout=20)
            # Fake sleep ends the watch only after its complete first routing cycle.
            self.assertEqual(result.returncode, expected_exit, result.stderr + result.stdout[-2500:])
            self.assertNotIn('Broken pipe', result.stderr)
            self.assertLess(len(result.stdout.splitlines()), 100, 'log output must stay bounded')
            if diff_failure and diff_failure != 'fetch':
                self.assertTrue((case / 'refreshed').exists(), 'Comparison recovery must fetch both exact source revisions')
            return [json.loads(line) for line in events.read_text().splitlines()]

    def test_missing_diff_objects_are_refreshed_before_kyronlink_dispatch(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['KyronLink/jni/src/io/kyron/link/DnsWire.java'], 'workspace',
                                     diff_failure='recoverable')
        self.assertEqual([e['event_type'] for e in events], ['component-kyronlink'])
        self.assertEqual(events[0]['client_payload']['workspace_sha'], NEXT)

    def test_failed_partial_diff_is_discarded_before_atomic_route(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['Launcher/jni/Main.cpp', 'VeraInternal/jni/Native.cpp'], 'workspace',
                                     diff_failure='recoverable', partial='Launcher/jni/partial.cpp\n')
        self.assertEqual([e['event_type'] for e in events], ['workspace-release'])

    def test_permanent_diff_failure_cannot_dispatch_partial_changes(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['Launcher/jni/Main.cpp'], 'workspace', diff_failure='permanent',
                                     partial='Launcher/jni/partial.cpp\n', expected_exit=1)
        self.assertEqual(events, [])

    def test_failed_exact_revision_refresh_cannot_dispatch(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['KyronLink/jni/src/io/kyron/link/DnsWire.java'], 'workspace',
                                     diff_failure='fetch', expected_exit=1)
        self.assertEqual(events, [])

    def test_pantry_routes_files_after_log_limit(self):
        paths = [f'client/fixture-{i:06}.bin' for i in range(12000)] + ['lua/late.lua']
        events = self.execute_router('pantry-watch.yml', 'Watch Pantry SHA continuously', paths, 'pantry')
        self.assertEqual([e['event_type'] for e in events], ['component-lua', 'pantry-delta'])
        self.assertTrue(all(e['client_payload']['pantry_sha'] == NEXT for e in events))

    def test_pantry_java_only_routes_to_dex(self):
        events = self.execute_router('pantry-watch.yml', 'Watch Pantry SHA continuously',
                                     ['src/io/kyron/Host.java'], 'pantry')
        self.assertEqual([e['event_type'] for e in events], ['component-dex'])
        self.assertTrue(all(e['client_payload']['pantry_sha'] == NEXT for e in events))

    def test_kyronlink_change_dispatches_exact_workspace_revision(self):
        paths = [f'notes/fixture-{i:06}.md' for i in range(12000)] + ['KyronLink/jni/src/io/kyron/link/DnsWire.java']
        events = self.execute_router('source-watch.yml', 'Route component changes', paths, 'workspace')
        self.assertEqual([e['event_type'] for e in events], ['component-kyronlink'])
        self.assertEqual(events[0]['client_payload'], {'source_router': True, 'workspace_sha': NEXT})

    def test_kyronlink_and_launcher_keep_both_independent_routes(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['KyronLink/build.ps1', 'Launcher/jni/Main.cpp'], 'workspace')
        self.assertEqual([e['event_type'] for e in events], ['component-kyronlink', 'component-launcher'])
        self.assertEqual(events[0]['client_payload']['workspace_sha'], NEXT)
        self.assertEqual(events[1]['client_payload'], {'source_router': True})

    def test_kyronlink_docs_dispatch_no_builds(self):
        events = self.execute_router('source-watch.yml', 'Route component changes',
                                     ['KyronLink/README.md'], 'workspace')
        self.assertEqual(events, [])

    def test_workspace_classifies_entire_large_change(self):
        paths = [f'Launcher/jni/fixture-{i:06}.cpp' for i in range(12000)]
        events = self.execute_router('source-watch.yml', 'Route component changes', paths, 'workspace')
        self.assertEqual([e['event_type'] for e in events], ['component-launcher'])

    def test_late_second_component_keeps_atomic_release(self):
        paths = [f'Launcher/jni/fixture-{i:06}.cpp' for i in range(12000)] + ['VeraInternal/jni/late.cpp']
        events = self.execute_router('source-watch.yml', 'Route component changes', paths, 'workspace')
        self.assertEqual([e['event_type'] for e in events], ['workspace-release'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
