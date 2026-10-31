"""Validate exact source revisions before private Workspace checkout."""
from pathlib import Path
import os
import shutil
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
NEXT = 'b' * 40

@unittest.skipUnless(shutil.which('pwsh'), 'PowerShell required')
class SourcePinRevisionTests(unittest.TestCase):
    def test_payload_revision_is_validated_before_checkout_and_selected_as_source(self):
        for name in ('source-pin.yml', 'source-pin-component.yml'):
            with self.subTest(workflow=name):
                document = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
                steps = document['jobs']['pin']['steps']
                checkout_index = next(i for i, step in enumerate(steps)
                                      if step.get('with', {}).get('path') == 'workspace')
                validation = next((step for step in steps[:checkout_index]
                                   if step.get('name') == 'Validate requested Workspace revision'), None)
                self.assertIsNotNone(validation, 'Requested revision must be validated before checkout')
                self.assertEqual(validation['env']['WORKSPACE_SHA'],
                                 '${{ github.event.client_payload.workspace_sha }}')
                self.assertEqual(steps[checkout_index]['with']['ref'],
                                 "${{ github.event.client_payload.workspace_sha || 'main' }}")
                for revision, accepted in (('', True), (NEXT, True), ('A' * 40, False),
                                           ('a' * 39, False), ('a' * 41, False),
                                           ('refs/heads/main', False), (' ', False),
                                           (NEXT + '\n', False)):
                    with self.subTest(revision=revision):
                        result = subprocess.run(
                            ['pwsh', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', validation['run']],
                            env=os.environ | {'WORKSPACE_SHA': revision}, capture_output=True,
                            text=True, timeout=20,
                        )
                        self.assertEqual(result.returncode == 0, accepted, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
