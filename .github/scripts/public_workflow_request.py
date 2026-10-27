"""Validate named Pantry Core entrypoints for execution in Pantry Core."""
import json
from pathlib import Path
import re

ROUTES = json.loads(Path(__file__).with_name('public_workflow_routes.json').read_text())
PUBLIC_PATHS = {'.github/workflows/' + name for name in ROUTES} | {'.github/workflows/automation-request.yml'}


def validate_revisions(payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid request payload')
    for key in ('workspace_sha', 'pantry_sha'):
        if key in payload and payload[key] and not re.fullmatch('[0-9a-f]{40}', str(payload[key])):
            raise ValueError('Invalid source revision')


def resolve(payload):
    name = payload.get('workflow')
    if not isinstance(name, str) or name not in ROUTES:
        raise ValueError('Unsupported workflow')
    route = ROUTES[name]
    event = payload.get('event', 'workflow_dispatch')
    if event not in ('workflow_dispatch', 'repository_dispatch', 'schedule', 'push'):
        raise ValueError('Unsupported request event')
    if event == 'repository_dispatch':
        action = payload.get('action')
        if action not in route['events']:
            raise ValueError('Workflow event mismatch')
        data = payload.get('client_payload', {})
        validate_revisions(data)
        return '/dispatches', {'event_type': action, 'client_payload': data}
    supplied = payload.get('inputs', {})
    if not isinstance(supplied, dict) or set(supplied) - set(route['inputs']):
        raise ValueError('Unsupported workflow inputs')
    inputs = {}
    for key, spec in route['inputs'].items():
        if key not in supplied:
            if spec.get('required') and 'default' not in spec:
                raise ValueError('Missing workflow input')
            if 'default' not in spec:
                continue
        value = supplied.get(key, spec.get('default'))
        kind = spec['type']
        if kind == 'boolean':
            if isinstance(value, str) and value in ('true', 'false'):
                value = value == 'true'
            if not isinstance(value, bool):
                raise ValueError('Invalid boolean input')
        elif kind == 'number':
            if isinstance(value, str):
                try: value = float(value)
                except ValueError: raise ValueError('Invalid number input') from None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError('Invalid number input')
        elif not isinstance(value, str) or (kind == 'choice' and value not in spec['options']):
            raise ValueError('Invalid workflow input')
        inputs[key] = value
    validate_revisions(inputs)
    if name == 'source-watch.yml':
        inputs['watch'] = True
    if name in ('device-registry.yml', 'actions-history-cleaner.yml'):
        inputs['request_origin'] = event
    if route['lane']:
        return '/actions/workflows/public-request-lane.yml/dispatches', {'ref': 'main', 'inputs': {'workflow': name, 'input_json': json.dumps(inputs)}}
    return '/actions/workflows/' + name + '/dispatches', {'ref': 'main', 'inputs': inputs}
