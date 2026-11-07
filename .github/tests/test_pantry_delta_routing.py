#!/usr/bin/env python3
"""Execute the workflow's real preflight with local Git fixtures and a fake GitHub reader."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import yaml

REPO = Path(__file__).resolve().parents[2]
delta = yaml.safe_load((REPO / '.github/workflows/pantry-delta.yml').read_text())
mirror = yaml.safe_load((REPO / '.github/workflows/pantry-mirror.yml').read_text())
preflight = next(step['run'] for step in delta['jobs']['publish']['steps']
                 if step.get('id') == 'delta')
prepare = next(step['run'] for step in delta['jobs']['publish']['steps']
               if step.get('name') == 'Prepare and publish only Pantry delta')

assert 'concurrency' not in delta
assert delta['jobs']['publish']['concurrency']['group'] == mirror['concurrency']['group']
assert delta['jobs']['full']['needs'] == 'publish'
assert "needs.publish.result == 'success'" in delta['jobs']['full']['if']
assert 'workflow_call' in mirror.get('on', mirror.get(True))
assert 'gh workflow run' not in preflight + prepare
fallback = delta['jobs']['full']['steps'][0]['run']
readiness = next(step['run'] for step in mirror['jobs']['detect']['steps'] if step.get('id') == 'prepared')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


with tempfile.TemporaryDirectory(prefix='kyron-delta-routing-') as temporary:
    base = Path(temporary)
    scenarios = [
        ('missing_baseline', 'missing', 'client', 'missing', 'full'),
        ('unrelated_history', 'valid', 'client', 'unrelated', 'full'),
        ('unavailable_baseline', 'valid', 'client', 'unavailable', 'full'),
        ('missing_route_state', 'missing', 'client', 'baseline', 'full'),
        ('stale_route_state', 'stale', 'client', 'baseline', 'full'),
        ('valid_state_client_delta', 'valid', 'client', 'baseline', 'delta'),
        ('contract_change', 'valid', 'contract', 'baseline', 'full'),
        ('removed_content', 'valid', 'removed', 'baseline', 'full'),
        ('renamed_content', 'valid', 'renamed', 'baseline', 'full'),
        ('control_only', 'valid', 'control', 'baseline', 'noop'),
        ('already_published', 'missing', 'client', 'target', 'noop'),
        ('valid_state_lua_delta', 'valid', 'lua', 'baseline', 'delta'),
        ('valid_state_membership_delta', 'valid', 'membership', 'baseline', 'delta'),
    ]
    for name, state, change, publication, expected in scenarios:
        case = base / name
        source = case / 'source'
        distribution = source / 'Distribution'
        source.mkdir(parents=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(source)], check=True)
        git(source, 'config', 'user.name', 'fixture')
        git(source, 'config', 'user.email', 'fixture@example.invalid')
        ini = '[runtime.contract]\nindex_record=kyron/aa/bb/' + '1' * 28 + '.bin\n'
        write(distribution / 'SrcVersion.ini', ini)
        write(distribution / 'tests/test_packet_codec.py', '"""Packet codec sparse-checkout fixture."""\n')
        write(distribution / 'client/old.bin', 'unchanged fixture content\n')
        write(distribution / 'lua/fixture.lua', 'return 1\n')
        git(source, 'add', '--', '.')
        git(source, 'commit', '-q', '-m', 'fixture baseline')
        baseline = git(source, 'rev-parse', 'HEAD')
        if state != 'missing':
            pin = baseline if state == 'valid' else 'b' * 40
            write(distribution / 'release/pantry-core-route-state.ini', '; Pantry-Source: ' + pin + '\n' + ini)
        if change == 'client':
            write(distribution / 'client/new.bin', 'new fixture content\n')
        elif change == 'membership':
            write(distribution / 'enrollment/membership.json.gz', 'membership fixture')
            write(distribution / 'enrollment/receipt.json', '{}\n')
        elif change == 'contract':
            write(distribution / 'SrcVersion.ini', ini + 'new_field=fixture\n')
        elif change == 'removed':
            (distribution / 'client/old.bin').unlink()
        elif change == 'renamed':
            (distribution / 'client/old.bin').rename(distribution / 'client/renamed.bin')
        elif change == 'control':
            write(distribution / 'release/fixture.json', '{}\n')
        elif change == 'lua':
            write(distribution / 'lua/fixture.lua', 'return 2\n')
        git(source, 'add', '--', '.')
        git(source, 'commit', '-q', '-m', 'fixture target')
        target = git(source, 'rev-parse', 'HEAD')
        git(source, 'config', 'core.sparseCheckout', 'true')
        published = '' if publication == 'missing' else target if publication == 'target' else baseline
        if publication == 'unrelated':
            published = git(source, 'commit-tree', git(source, 'rev-parse', 'HEAD^{tree}'),
                            '-m', 'retired unrelated publication root')
        elif publication == 'unavailable':
            published = 'a' * 40
        bindir = case / 'bin'
        bindir.mkdir()
        fake = bindir / 'gh'
        fake.write_text('#!/usr/bin/env python3\n'
                        'import os,sys\n'
                        'assert sys.argv[1] == "api", "unexpected GitHub write"\n'
                        'assert os.environ["GH_TOKEN"] == "synthetic-test-token", "unexpected GitHub credential"\n'
                        'print(os.environ["FIXTURE_PUBLISHED"])\n')
        fake.chmod(0o755)
        script = case / 'preflight.sh'
        script.write_text(preflight)
        runner_temp = case / 'runner-temp'
        runner_temp.mkdir()
        output = case / 'outputs'
        output.touch()
        env = os.environ | {'GH_TOKEN': 'synthetic-test-token',
                            'PATH': str(bindir) + ':' + os.environ['PATH'],
                            'FIXTURE_PUBLISHED': published, 'GITHUB_REPOSITORY': 'fixture/pantry-core',
                            'RUNNER_TEMP': str(runner_temp), 'GITHUB_OUTPUT': str(output)}
        result = subprocess.run(['bash', str(script)], cwd=case, env=env,
                                text=True, capture_output=True, timeout=20)
        assert result.returncode == 0, (name, result.stdout, result.stderr)
        outputs = dict(line.split('=', 1) for line in output.read_text().splitlines())
        assert outputs['target'] == target, (name, outputs)
        sparse = source / '.git/info/sparse-checkout'
        if expected == 'full':
            assert outputs['full_required'] == 'true', (name, outputs)
            assert outputs['needs_publish'] == 'false'
            assert not sparse.exists(), 'fallback must not stage partial source'
            assert not (runner_temp / 'pantry-changed.list').exists() or change in ('contract', 'removed', 'renamed')
        elif expected == 'delta':
            assert outputs['needs_publish'] == 'true'
            assert outputs.get('full_required') != 'true'
            assert sparse.exists()
            packet_preflight = distribution / 'tests/test_packet_codec.py'
            assert packet_preflight.is_file(), (name, 'packet codec preflight missing after sparse checkout')
            assert packet_preflight.read_text() == '"""Packet codec sparse-checkout fixture."""\n'
            if change == 'lua':
                assert outputs['needs_lua'] == 'true'
                assert '/Distribution/lua/' in sparse.read_text()
        else:
            assert outputs['needs_publish'] == 'false'
            assert outputs.get('full_required') != 'true'
            assert not sparse.exists()
        print(json.dumps({'scenario': name, 'result': expected, 'exact_target': True, 'passed': True}))

    # Execute the actual fallback: source-only changes request preparation,
    # rather than a mirror with an absent encrypted producer.
    bindir = base / 'dispatch-bin'
    bindir.mkdir()
    fake = bindir / 'gh'
    fake.write_text('#!/usr/bin/env python3\n'
                    'import json,os,sys\n'
                    'assert sys.argv[1:] == ["api","--method","POST","repos/fixture/pantry-core/dispatches","--input","-"]\n'
                    'assert os.environ["GH_TOKEN"] == "synthetic-test-token"\n'
                    'from pathlib import Path\n'
                    'Path(os.environ["FIXTURE_DISPATCH"]).write_text(json.dumps(json.load(sys.stdin)))\n')
    fake.chmod(0o755)
    dispatch_file = base / 'dispatch.json'
    fallback_script = base / 'full.sh'
    fallback_script.write_text(fallback)
    env = os.environ | {'PATH': str(bindir) + ':' + os.environ['PATH'],
                        'GH_TOKEN': 'synthetic-test-token', 'GITHUB_REPOSITORY': 'fixture/pantry-core',
                        'WORKSPACE_SHA': 'c' * 40, 'FIXTURE_DISPATCH': str(dispatch_file)}
    invoked = subprocess.run(['bash', str(fallback_script)], env=env, text=True, capture_output=True)
    assert invoked.returncode == 0, (invoked.stdout, invoked.stderr)
    assert json.loads(dispatch_file.read_text()) == {
        'event_type': 'workspace-release', 'client_payload': {'workspace_sha': 'c' * 40, 'manual_refresh': True}}
    dispatch_file.unlink()
    rejected = subprocess.run(['bash', str(fallback_script)], env=env | {'WORKSPACE_SHA': 'main'},
                              text=True, capture_output=True)
    assert rejected.returncode != 0 and not dispatch_file.exists()
    print(json.dumps({'scenario': 'full_fallback_requests_exact_source_preparation', 'passed': True}))

    # Missing prepared inputs are pending; malformed identities remain failures.
    ready_script = base / 'delivery-readiness.sh'
    ready_script.write_text(readiness)
    for name, run, attempt, needed, pending in (
            ('missing_producer', '', '', 'true', 'true'),
            ('valid_producer', '12345', '2', 'true', 'false'),
            ('already_published', '', '', 'false', 'false'),
            ('already_published_invalid_producer', '0', '1', 'false', None),
            ('partial_producer', '12345', '', 'true', None),
            ('partial_attempt', '', '1', 'true', None),
            ('invalid_run', '0', '1', 'true', None),
            ('invalid_attempt', '12345', 'main', 'true', None)):
        output = base / (name + '.output')
        summary = base / (name + '.summary')
        env = os.environ | {'DELIVERY_RUN_ID': run, 'DELIVERY_RUN_ATTEMPT': attempt, 'NEEDS_PUBLISH': needed,
                            'GITHUB_OUTPUT': str(output), 'GITHUB_STEP_SUMMARY': str(summary)}
        result = subprocess.run(['bash', str(ready_script)], env=env, capture_output=True, text=True)
        if pending is None:
            assert result.returncode != 0 and not output.exists(), (name, result.stdout, result.stderr)
        else:
            assert result.returncode == 0 and output.read_text().strip() == 'pending=' + pending
            if pending == 'true':
                assert '[WAIT]' in result.stdout and 'pending' in summary.read_text()
        print(json.dumps({'scenario': name, 'passed': True}))

    # The actual producer step must fail directly on an unexpected signed-index defect.
    producer = base / 'strict-producer.sh'
    producer.write_text('python() { echo "[CONTENT][INDEX/GATE] signed index missing 1 required route(s): fixture" >&2; return 17; }\n' +
                        prepare.replace('${{ steps.delta.outputs.target }}', 'a' * 40))
    env = os.environ | {'GH_TOKEN': 'synthetic-test-token',
                        'RUNNER_TEMP': str(base), 'GITHUB_RUN_ATTEMPT': '1'}
    rejected = subprocess.run(['bash', str(producer)], env=env, capture_output=True, text=True)
    assert rejected.returncode == 17, (rejected.returncode, rejected.stdout, rejected.stderr)
    print(json.dumps({'scenario': 'unexpected_signed_index_failure', 'exit_code': 17, 'passed': True}))
    print('workflow_call_and_serialization_contract=passed')
