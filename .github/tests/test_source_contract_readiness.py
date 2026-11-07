"""Behavior of source readiness against an actual generator subprocess."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECK = Path(__file__).parents[1] / "scripts/verify_source_contract.py"


class SourceContractReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.owner = self.workspace / "Distribution/tools/sync_consumer_contract.py"
        self.owner.parent.mkdir(parents=True)
        self.config = self.workspace / "Distribution/SrcVersion.ini"
        self.header = self.workspace / "Shared/pantry_contract.hpp"
        self.header.parent.mkdir()
        self.config.write_text("source config\n")
        self.header.write_text("original header\n")
        self.output = root / "outputs"
        self.summary = root / "summary"

    def invoke(self, message, code=1, *, create_owner=True):
        if create_owner:
            # A real producer would mutate its output without --check.
            self.owner.write_text(
                "from pathlib import Path\nimport sys\n"
                "if '--check' not in sys.argv:\n"
                "    Path(sys.argv[sys.argv.index('--output')+1]).write_text('unexpected rewrite')\n"
                f"print({message!r}, file=sys.stderr)\nraise SystemExit({code})\n"
            )
        env = dict(os.environ, GITHUB_OUTPUT=str(self.output), GITHUB_STEP_SUMMARY=str(self.summary))
        result = subprocess.run([sys.executable, str(CHECK), "--workspace", str(self.workspace)],
                                env=env, text=True, capture_output=True)
        self.assertEqual(self.header.read_text(), "original header\n")
        self.assertEqual(self.config.read_text(), "source config\n")
        return result

    def test_current_projection_is_ready(self):
        result = self.invoke("private diagnostic should remain hidden", 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[OK]", result.stdout)
        self.assertEqual(self.output.read_text(), "pending=false\n")
        self.assertNotIn("private diagnostic", result.stdout + result.stderr)

    def test_only_canonical_stale_projection_waits_without_error(self):
        result = self.invoke("[CONTRACT][E] stale generated consumer header: private/path/header.hpp")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[WAIT]", result.stdout)
        self.assertNotIn("::error", result.stdout)
        self.assertNotIn("private/path", result.stdout + result.stderr)
        self.assertEqual(self.output.read_text(), "pending=true\n")
        self.assertIn("publication are skipped", self.summary.read_text())

    def test_mapping_error_is_fatal(self):
        result = self.invoke("runtime/pantry mapping drift: private contract details")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error", result.stdout)
        self.assertEqual(self.output.read_text(), "pending=false\n")
        self.assertNotIn("private contract details", result.stdout + result.stderr)

    def test_missing_required_configuration_is_fatal(self):
        result = self.invoke("section missing: private config")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing or invalid", result.stdout)

    def test_unrecognized_failure_is_fatal_and_sanitized(self):
        result = self.invoke("private token diagnostic; stale generated consumer header")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("private token", result.stdout + result.stderr)
        self.assertNotIn("[WAIT]", result.stdout)

    def test_noncanonical_exit_code_is_fatal(self):
        result = self.invoke("[CONTRACT][E] stale generated consumer header: private/path", 2)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("[WAIT]", result.stdout)

    def test_missing_generator_is_fatal(self):
        result = self.invoke("", create_owner=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("[WAIT]", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
