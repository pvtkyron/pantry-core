"""Prevent serializing safe Doctor checks or weakening publication gates."""
from pathlib import Path
import unittest
import yaml

WORKFLOW=Path(__file__).resolve().parents[1]/'workflows/patisserie.yml'
SOURCE_CAPSULE='$'+'{{ needs.sources.outputs.capsule }}'
DELIVERY_CAPSULE='$'+'{{ needs.workspace.outputs.delivery_capsule }}'

class CriticalPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs=yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))['jobs']

    def test_portable_preflight_stays_required(self):
        preflight=self.jobs['portable_preflight']
        self.assertEqual(preflight['needs'],'sources')
        self.assertEqual(preflight['with']['platform'],'Portable')
        self.assertEqual(preflight['with']['capsule'],SOURCE_CAPSULE)
        build=self.jobs['workspace']
        self.assertEqual(set(build['needs']),{'sources','portable_preflight'})
        self.assertIn("needs.portable_preflight.result == 'success'",build['if'])

    def test_windows_doctor_runs_on_same_pinned_source_in_parallel(self):
        doctor=self.jobs['doctor']
        self.assertEqual(set(doctor['needs']),{'sources','portable_preflight'})
        self.assertEqual(doctor['uses'],'./.github/workflows/doctor.yml')
        self.assertEqual(doctor['with']['platform'],'Windows')
        self.assertEqual(doctor['with']['capsule'],SOURCE_CAPSULE)
        for guard in ("needs.sources.result == 'success'","needs.portable_preflight.result == 'success'","needs.sources.outputs.delivery_pending != 'true'"):
            self.assertIn(guard,doctor['if'])
        self.assertNotIn('needs.workspace',doctor['if'])

    def test_publish_waits_for_successful_doctor_and_verified_delivery(self):
        publish=self.jobs['publish']
        self.assertEqual(set(publish['needs']),{'workspace','doctor'})
        self.assertEqual(publish['with']['capsule'],DELIVERY_CAPSULE)
        for guard in ("needs.doctor.result == 'success'","needs.workspace.result == 'success'","needs.workspace.outputs.superseded != 'true'","needs.workspace.outputs.delivery_pending != 'true'","needs.workspace.outputs.delivery_capsule != ''"):
            self.assertIn(guard,publish['if'])

    def test_postpublish_headless_gate_unchanged(self):
        headless=self.jobs['headless']
        self.assertEqual(set(headless['needs']),{'workspace','publish'})
        self.assertIn("needs.publish.result",headless['if'])
        self.assertEqual(headless['with']['capsule'],DELIVERY_CAPSULE)

if __name__=='__main__':unittest.main(verbosity=2)
