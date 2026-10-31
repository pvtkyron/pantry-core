#!/usr/bin/env python3
"""Exercise the Workspace source router's actual component classifier."""

from pathlib import Path
import subprocess
import os
import unittest


ROOT = Path(__file__).resolve().parent.parent.parent
CLASSIFIER = Path(os.environ.get("KYRON_ROUTER_CLASSIFIER", ROOT / ".github/scripts/classify_workspace_change.sh"))


def classify(*paths: str) -> str:
    result = subprocess.run(
        ["bash", str(CLASSIFIER)],
        input="".join(f"{path}\n" for path in paths),
        text=True,
        check=True,
        capture_output=True,
    )
    return result.stdout.strip()


class SourceWatchRoutingTests(unittest.TestCase):
    def test_kyronlink_code_uses_its_managed_validation_lane(self):
        self.assertEqual(classify("KyronLink/jni/src/io/kyron/link/PhoneDnsShareServer.java"),
                         "component-kyronlink")
        self.assertEqual(classify("KyronLink/build_mundo_sources.py"), "component-kyronlink")

    def test_kyronlink_docs_do_not_compile(self):
        self.assertEqual(classify("KyronLink/README.md", "KyronLink/jni/container/PROVENANCE.md"),
                         "none")

    def test_kyronlink_validation_survives_mixed_release_changes(self):
        self.assertEqual(classify("KyronLink/jni/src/io/kyron/link/PhoneDnsShareServer.java",
                                  "Shared/pantry_contract.hpp").split(),
                         ["component-kyronlink", "workspace-release"])
        self.assertEqual(classify("KyronLink/build.ps1", "Launcher/jni/Main.cpp").split(),
                         ["component-kyronlink", "component-launcher"])

    def test_launcher_only_changes_use_launcher_lane(self):
        self.assertEqual(
            classify("Launcher/jni/Main.cpp", "README.md"),
            "component-launcher",
        )

    def test_vera_only_changes_use_native_lib_lane(self):
        self.assertEqual(classify("VeraInternal/src/Native.cpp"), "component-lib")

    def test_java_only_changes_use_dex_lane(self):
        self.assertEqual(
            classify("Distribution/src/io/kyron/link/KyronVpnService.java"),
            "component-dex",
        )

    def test_shared_version_headers_use_only_their_two_native_consumers(self):
        self.assertEqual(
            classify("src/common/Shared/SrcVersionBlob.hpp"),
            "component-launcher component-lib",
        )

    def test_mixed_component_changes_keep_atomic_full_release(self):
        self.assertEqual(
            classify("Launcher/jni/Main.cpp", "Distribution/src/io/Host.java"),
            "workspace-release",
        )
        self.assertEqual(
            classify("Launcher/jni/Main.cpp", "VeraInternal/src/Native.cpp"),
            "workspace-release",
        )

    def test_contract_and_bootstrap_inputs_keep_full_release(self):
        self.assertEqual(classify("Bootstrap/jni/Main.cpp"), "workspace-release")
        self.assertEqual(
            classify("Distribution/tools/prepare_snapshot.py"),
            "workspace-release",
        )

    def test_control_and_docs_only_changes_do_not_compile(self):
        self.assertEqual(
            classify(".kyron/control/request.json", "README.md"),
            "none",
        )


if __name__ == "__main__":
    unittest.main()
