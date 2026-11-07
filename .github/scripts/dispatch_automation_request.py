"""Translate authenticated requests into Pantry Core workflow entrypoints."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from public_workflow_request import resolve

EVENTS = {
    'workspace-release', 'component-apk', 'component-dex', 'component-lib',
    'component-lua', 'component-sdk', 'component-web', 'component-launcher',
    'component-kyronlink', 'pantry-delta', 'device-enrollment', 'kyron-laptop-control',
}
MANUAL = {
    'mirror': 'pantry-mirror.yml',
    'checks': 'ci-fast-path-smoke.yml',
    'doctor': 'doctor-targeted-validation.yml',
    'regression': 'workspace-powershell-regression.yml',
}


def dispatch(event, repository, token, api):
    if repository.lower() != 'pvtkyron/pantry-core':
        raise ValueError('Repository guard rejected')
    data = event.get('client_payload', {})
    operation = data.get('request', 'refresh')
    payload = data.get('payload', {})
    if not isinstance(payload, dict):
        raise ValueError('Invalid request payload')
    for key in ('workspace_sha', 'pantry_sha'):
        if key in payload and not re.fullmatch('[0-9a-f]{40}', str(payload[key])):
            raise ValueError('Invalid source revision')
    if operation == 'refresh':
        operation = 'workspace-release'
    if operation == 'workflow':
        suffix, body = resolve(payload)
        path = '/repos/' + repository + suffix
    elif operation in MANUAL:
        inputs = {}
        if operation == 'mirror':
            inputs['pantry_sha'] = payload.get('pantry_sha', '')
            inputs.update({key: payload[key] for key in ('delivery_run_id', 'delivery_run_attempt') if key in payload})
            suffix, body = resolve({'workflow': 'pantry-mirror.yml', 'inputs': inputs})
            path = '/repos/' + repository + suffix
        else:
            path = f'/repos/{repository}/actions/workflows/{MANUAL[operation]}/dispatches'
            body = {'ref': 'main', 'inputs': inputs}
    elif operation in EVENTS:
        path = f'/repos/{repository}/dispatches'
        body = {'event_type': operation, 'client_payload': payload}
    else:
        raise ValueError('Unsupported automation request')
    request = urllib.request.Request(api.rstrip('/') + path,
        data=json.dumps(body).encode(), method='POST', headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        })
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 204:
            raise ValueError('Request was not accepted')


if __name__ == '__main__':
    try:
        event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        if os.environ['GITHUB_EVENT_NAME']=='workflow_dispatch':
            values=event.get('inputs', {})
            event={'client_payload': {'request': values.get('request', 'refresh'), 'payload': json.loads(values.get('payload') or '{}')}}
        dispatch(event,
                 os.environ['GITHUB_REPOSITORY'], os.environ['AUTOMATION_TOKEN'],
                 os.environ['GITHUB_API_URL'])
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        raise SystemExit('Automation request failed; inspect Pantry Core configuration') from None
    print('Automation request accepted')
