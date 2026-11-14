"""Exercise Pantry Core dispatch requests through a real local HTTP server."""
import importlib.util
import json
import sys
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('dispatch_request', Path(__file__).parents[1] / 'scripts/dispatch_automation_request.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AutomationRequests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        records = self.requests
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                records.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(204)
                self.end_headers()
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def send(self, request='refresh', payload=None, repository='pvtkyron/pantry-core'):
        return module.dispatch({'client_payload': {'request': request, 'payload': payload or {}}}, repository,
                               'synthetic-test-token', f'http://127.0.0.1:{self.server.server_port}')

    def test_default_request_uses_core_full_release(self):
        self.send()
        self.assertEqual(self.requests, [('/repos/pvtkyron/pantry-core/dispatches', {'event_type': 'workspace-release', 'client_payload': {}})])

    def test_exact_component_source_is_preserved(self):
        payload = {'workspace_sha': 'a' * 40, 'source_router': True}
        self.send('component-kyronlink', payload)
        self.assertEqual(self.requests[0][1], {'event_type': 'component-kyronlink', 'client_payload': payload})

    def test_exact_mirror_revision_uses_core_workflow(self):
        self.send('mirror', {'pantry_sha': 'b' * 40})
        self.assertEqual(self.requests, [('/repos/pvtkyron/pantry-core/actions/workflows/pantry-mirror.yml/dispatches', {'ref': 'main', 'inputs': {'pantry_sha': 'b' * 40}})])

    def test_mirror_preserves_authenticated_delivery_producer(self):
        payload = {'pantry_sha': 'b' * 40, 'delivery_run_id': '12345', 'delivery_run_attempt': '2'}
        self.send('mirror', payload)
        self.assertEqual(self.requests[-1][1]['inputs'], payload)
        self.send('workflow', {'workflow': 'pantry-mirror.yml', 'inputs': payload})
        self.assertEqual(self.requests[-1][1]['inputs'], payload)

    def test_malformed_or_partial_mirror_producer_makes_no_request(self):
        for values in ({'delivery_run_id': '12345'}, {'delivery_run_attempt': '1'},
                       {'delivery_run_id': '0', 'delivery_run_attempt': '1'},
                       {'delivery_run_id': '12345', 'delivery_run_attempt': 'main'},
                       {'delivery_run_id': 12345, 'delivery_run_attempt': '1'}):
            for operation in ('mirror', 'workflow'):
                payload = values if operation == 'mirror' else {'workflow': 'pantry-mirror.yml', 'inputs': values}
                with self.subTest(operation=operation, values=values), self.assertRaises(ValueError):
                    self.send(operation, payload)
        self.assertEqual(self.requests, [])

    def test_all_named_core_entries_reach_their_maintained_owner(self):
        from public_workflow_request import ROUTES
        for name, route in ROUTES.items():
            with self.subTest(workflow=name):
                values = {key: spec.get('default', 'fixture-capsule')
                          for key, spec in route['inputs'].items()
                          if 'default' in spec or spec.get('required')}
                self.send('workflow', {'workflow': name, 'inputs': values})
                path, body = self.requests[-1]
                expected = 'public-request-lane.yml' if route['lane'] else name
                self.assertEqual(path, '/repos/pvtkyron/pantry-core/actions/workflows/' + expected + '/dispatches')
                self.assertEqual(body['ref'], 'main')
                if route['lane']:
                    self.assertEqual(body['inputs']['workflow'], name)
                    self.assertEqual(json.loads(body['inputs']['input_json']), values)

    def test_named_mirror_and_boolean_inputs_are_preserved(self):
        self.send('workflow', {'workflow': 'pantry-mirror.yml', 'inputs': {'pantry_sha': 'c' * 40}})
        self.assertEqual(self.requests[-1][1]['inputs'], {'pantry_sha': 'c' * 40})
        self.send('workflow', {'workflow': 'component-lib.yml', 'inputs': {'validate_only': 'false'}})
        self.assertIs(self.requests[-1][1]['inputs']['validate_only'], False)
        self.send('workflow', {'workflow': 'component-lib.yml', 'inputs': {'validate_only': True}})
        self.assertIs(self.requests[-1][1]['inputs']['validate_only'], True)

    def test_named_event_cannot_dispatch_another_component(self):
        self.send('workflow', {'workflow': 'component-dex.yml', 'event': 'repository_dispatch',
                              'action': 'component-dex', 'client_payload': {'workspace_sha': 'd' * 40}})
        self.assertEqual(self.requests[-1][1], {'event_type': 'component-dex', 'client_payload': {'workspace_sha': 'd' * 40}})
        with self.assertRaises(ValueError):
            self.send('workflow', {'workflow': 'component-dex.yml', 'event': 'repository_dispatch',
                                   'action': 'kyron-laptop-control', 'client_payload': {}})
        self.assertEqual(len(self.requests), 1)

    def test_schedule_origin_is_preserved_and_source_router_runs(self):
        self.send('workflow', {'workflow': 'device-registry.yml', 'event': 'schedule', 'inputs': {}})
        self.assertEqual(self.requests[-1][1]['inputs']['request_origin'], 'schedule')
        self.send('workflow', {'workflow': 'actions-history-cleaner.yml', 'event': 'push', 'inputs': {}})
        self.assertEqual(self.requests[-1][1]['inputs']['request_origin'], 'push')
        self.send('workflow', {'workflow': 'source-watch.yml', 'event': 'schedule', 'inputs': {}})
        self.assertIs(self.requests[-1][1]['inputs']['watch'], True)

    def test_manual_source_router_preserves_watch_choice(self):
        for inputs, expected in (({}, False), ({'watch': False}, False),
                                 ({'watch': 'false'}, False), ({'watch': True}, True)):
            with self.subTest(inputs=inputs):
                self.send('workflow', {'workflow': 'source-watch.yml', 'inputs': inputs})
                path, body = self.requests[-1]
                self.assertEqual(path, '/repos/pvtkyron/pantry-core/actions/workflows/source-watch.yml/dispatches')
                self.assertIs(body['inputs']['watch'], expected)

    def test_named_request_rejects_unknown_workflow_inputs_and_revisions(self):
        bad = [{'workflow': '../../private.yml'},
               {'workflow': 'site.yml'},
               {'workflow': 'kyron-coherent-updater.yml'},
               {'workflow': 'pantry-mirror.yml', 'inputs': {'pantry_sha': 'main'}},
               {'workflow': 'component-lib.yml', 'inputs': {'arbitrary': 'value'}},
               {'workflow': 'component-lib.yml', 'inputs': {'validate_only': 'no'}},
               {'workflow': 'workspace-java.yml', 'inputs': {}}]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.send('workflow', payload)
        self.assertEqual(self.requests, [])

    def test_invalid_requests_make_no_network_request(self):
        for operation, payload, repository in [('arbitrary-workflow', {}, 'pvtkyron/pantry-core'),
                                               ('mirror', {'pantry_sha': 'main'}, 'pvtkyron/pantry-core'),
                                               ('component-lib', {}, 'untrusted/destination'),
                                               ('component-lib', {}, 'pvtkyron/Workspace')]:
            with self.subTest(operation=operation, repository=repository):
                with self.assertRaises(ValueError):
                    self.send(operation, payload, repository)
        self.assertEqual(self.requests, [])


if __name__ == '__main__':
    unittest.main()
