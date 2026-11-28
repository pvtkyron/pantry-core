#!/usr/bin/env python3
"""Exercise the Workspace source router's actual component classifier."""

from pathlib import Path
import subprocess
import os
import tempfile
import unittest
import yaml


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

    def test_content_plus_compiler_cannot_drop_lua_or_font_resources(self):
        for owner in ("Launcher/jni/Main.cpp","VeraInternal/src/Native.cpp","Distribution/src/io/Host.java"):
            with self.subTest(owner=owner):
                self.assertEqual(classify(owner,"Distribution/lua/gfx.lua"),"workspace-release")
                self.assertEqual(classify(owner,"Distribution/Font/font_emoji.ttf"),"workspace-release")
        self.assertEqual(classify("KyronLink/build.ps1","Distribution/lua/gfx.lua").split(),["component-kyronlink","pantry-delta"])
    def test_qa_only_script_does_not_trigger_full_recompile(self):
        self.assertEqual(classify("etc/devtools/tests/Test-PantryIndependentLanes.ps1"),"none")
    def test_mixed_component_changes_keep_atomic_full_release(self):
        self.assertEqual(
            classify("Launcher/jni/Main.cpp", "Distribution/src/io/Host.java"),
            "workspace-release",
        )
        self.assertEqual(
            classify("Launcher/jni/Main.cpp", "VeraInternal/src/Native.cpp"),
            "workspace-release",
        )

    def test_publisher_pipeline_changes_still_trigger_release_without_native_elf_rebuild(self):
        self.assertEqual(classify("Distribution/tools/kyron_pipeline.py"),"workspace-release")
        self.assertEqual(classify("Distribution/tools/kyron_pipeline.py","Distribution/lua/gfx.lua"),"workspace-release")
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


class SourceWatchOwnerAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = yaml.safe_load((ROOT / ".github/workflows/source-watch.yml").read_text())
        cls.step = next(step for step in workflow["jobs"]["watch"]["steps"]
                        if step.get("id") == "route")

    def admit(self, paths=(), force_full="false", missing_changes=False):
        with tempfile.TemporaryDirectory(prefix="source-owner-admission-") as raw:
            root = Path(raw)
            changes = root / "changes.txt"
            if not missing_changes:
                changes.write_text("".join(path + "\n" for path in paths))
            output = root / "output"
            output.touch()
            result = subprocess.run(["bash", "-c", self.step["run"]],
                capture_output=True, text=True, timeout=10, env=os.environ | {
                    "RECIPE_ROOT": str(ROOT), "FORCE_FULL": force_full,
                    "CHANGED_PATHS_FILE": str(changes), "GITHUB_OUTPUT": str(output),
                })
            return result, output.read_text()

    def test_unchanged_and_documentation_sources_skip_receipts_and_compilers(self):
        for paths in ((), ("README.md",), ("Launcher/README.md", "KyronLink/README.md")):
            with self.subTest(paths=paths):
                result, output = self.admit(paths)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.strip(), "needs_routing=false")
                self.assertIn("[ROUTER][NOOP]", result.stdout)
                self.assertNotIn("[WAIT]", result.stdout)

    def test_each_changed_owner_keeps_its_existing_admission(self):
        for path in ("Launcher/jni/Main.cpp", "VeraInternal/Native.cpp",
                     "Distribution/src/Host.java", "KyronLink/build.ps1",
                     "Distribution/lua/gfx.lua", "Shared/pantry_contract.hpp"):
            with self.subTest(path=path):
                result, output = self.admit((path,))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.strip(), "needs_routing=true")

    def test_missing_baseline_cannot_be_silenced_as_an_unchanged_source(self):
        result, output = self.admit(force_full="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.strip(), "needs_routing=true")

    def test_invalid_scan_state_and_missing_change_list_remain_fatal(self):
        for arguments in ({"force_full": "unknown"}, {"missing_changes": True}):
            with self.subTest(arguments=arguments):
                result, output = self.admit(**arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("needs_routing=false", output)


if __name__ == "__main__":
    unittest.main()
