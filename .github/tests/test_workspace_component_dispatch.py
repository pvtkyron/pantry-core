"""Exercise the scheduled Workspace component router without network access."""
from pathlib import Path
import json, os, shutil, subprocess, tempfile, unittest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / ".github/scripts/route_workspace_changes.sh"
SHA = "b" * 40

@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "bash and jq required")
class WorkspaceRouteDispatchTests(unittest.TestCase):
    def run_route(self, *paths, force_full=False, sha=SHA, repository="pvtkyron/pantry-core", ref="refs/heads/main", gh_exit=0, approval="true", candidate="false", match="false", kyronlink_validated="false", dry_run="false", source_approved="false"):
        with tempfile.TemporaryDirectory(prefix="kyron-route-") as temporary:
            case = Path(temporary); bindir = case / "bin"; bindir.mkdir()
            events = case / "events.jsonl"; events.touch()
            fake_gh = """#!/usr/bin/env python3
import json, os, sys
assert sys.argv[1:] == ["api", "--method", "POST", "repos/pvtkyron/pantry-core/dispatches", "--input", "-"], sys.argv
assert os.environ["GH_TOKEN"] == "synthetic-test-token"
with open(os.environ["FIXTURE_EVENTS"], "a") as output:
    output.write(json.dumps(json.load(sys.stdin)) + "\\n")
raise SystemExit(int(os.environ["FIXTURE_GH_EXIT"]))
"""
            command = bindir / "gh"; command.write_text(fake_gh); command.chmod(0o755)
            changes = case / "changes.txt"; changes.write_text("".join(f"{path}\n" for path in paths))
            result = subprocess.run(["bash", str(SCRIPT)], cwd=case, capture_output=True, text=True, timeout=10, env=os.environ | {
                "PATH": str(bindir) + ":" + os.environ["PATH"], "GH_TOKEN": "synthetic-test-token",
                "GITHUB_REPOSITORY": repository, "GITHUB_REF": ref, "WORKSPACE_SHA": sha,
                "CHANGED_PATHS_FILE": str(changes), "FORCE_FULL": str(force_full).lower(),
                "NATIVE_SOURCE_APPROVED": source_approved, "NATIVE_APPROVAL_READY": approval, "NATIVE_CANDIDATE_VERIFIED": candidate,
                "NATIVE_CANDIDATE_MATCHES_PINS": match, "KYRONLINK_VALIDATED": kyronlink_validated,
                "ROUTER_DRY_RUN":dry_run,"FIXTURE_EVENTS": str(events), "FIXTURE_GH_EXIT": str(gh_exit)})
            sent = [json.loads(line) for line in events.read_text().splitlines()]
            self.assertNotIn("synthetic-test-token", result.stdout + result.stderr)
            return result, sent

    def assert_event(self, sent, name):
        self.assertEqual(sent, [{"event_type": name, "client_payload": {"workspace_sha": SHA}}])

    def test_lua_and_content_only_publish_without_unrelated_compilers(self):
        for path in ('Distribution/lua/script.lua','Distribution/assest/language.json','Distribution/dist/InputHost.dex','Distribution/enrollment/device.json'):
            with self.subTest(path=path):
                result,sent=self.run_route(path)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assert_event(sent,'pantry-delta')

    def test_no_source_changes_or_component_documentation_is_noop(self):
        for paths in ((),('Launcher/README.md',),('VeraInternal/README.md',)):
            result,sent=self.run_route(*paths)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(sent,[])

    def test_inspection_selects_changed_owner_without_build_or_publication(self):
        result,sent=self.run_route("Launcher/jni/Main.cpp",dry_run="true")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(sent,[])
        self.assertIn("selected=component-launcher",result.stdout)
        self.assertIn("no_build=true no_prepare=true no_publish=true",result.stdout)

    def test_native_only(self):
        result, sent = self.run_route("VeraInternal/src/Native.cpp"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "component-lib")

    def test_old_approved_hashes_do_not_skip_changed_native_compiler_inputs(self):
        for paths in (("VeraInternal/src/Native.cpp", "Launcher/jni/Main.cpp"),
                      ("src/common/Shared/contract.hpp",)):
            with self.subTest(paths=paths):
                r, sent = self.run_route(*paths, approval="true")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assert_event(sent, "component-lib")
                r, sent = self.run_route(*paths, approval="true", candidate="true")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(sent, [])
                self.assertIn("[ROUTER][WAIT]", r.stdout)

    def test_unknown_native_source_proof_rejected(self):
        r, sent = self.run_route("VeraInternal/src/Native.cpp", source_approved="unknown")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(sent, [])

    def test_launcher_only(self):
        result, sent = self.run_route("Launcher/jni/Main.cpp"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "component-launcher")

    def test_java_only(self):
        result, sent = self.run_route("Distribution/src/io/Host.java"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "component-dex")

    def test_mixed_lanes_use_atomic_full_release(self):
        result, sent = self.run_route("VeraInternal/src/Native.cpp", "Launcher/jni/Main.cpp", source_approved="true"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "workspace-release")

    def test_shared_header_uses_atomic_full_release(self):
        result, sent = self.run_route("src/common/Shared/SrcVersionBlob.hpp", source_approved="true"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "workspace-release")

    def test_missing_baseline_falls_back_to_full_release(self):
        result, sent = self.run_route("README.md", force_full=True, source_approved="true"); self.assertEqual(result.returncode, 0, result.stderr); self.assert_event(sent, "workspace-release")

    def test_full_fallback_preserves_independent_kyronlink_validation(self):
        result, sent = self.run_route("KyronLink/build.ps1", force_full=True, source_approved="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x["event_type"] for x in sent], ["workspace-release", "component-kyronlink"])

    def test_docs_only_change_is_noop(self):
        result, sent = self.run_route("README.md", "KyronLink/README.md"); self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(sent, []); self.assertIn("[ROUTER][NOOP]", result.stdout)

    def test_kyronlink_validation_survives_native_change(self):
        result, sent = self.run_route("KyronLink/build.ps1", "VeraInternal/src/Native.cpp"); self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([x["event_type"] for x in sent], ["component-lib", "component-kyronlink"])
        self.assertTrue(all(x["client_payload"]["workspace_sha"] == SHA for x in sent))

    def test_native_candidate_built_once_while_unapproved(self):
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", approval="false")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_event(sent, "component-lib")
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", approval="false", candidate="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])
        self.assertIn("[ROUTER][WAIT]", r.stdout)

    def test_wait_does_not_compile_launcher_without_native_approval(self):
        r, sent = self.run_route("Launcher/jni/Main.cpp", approval="false")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])

    def test_signed_native_candidate_that_matches_approved_pins(self):
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", approval="true", candidate="true", match="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])
        self.assertIn("[ROUTER][NATIVE/NOOP]",r.stdout)

    def test_signed_native_candidate_with_wrong_pins_waits(self):
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", approval="true", candidate="true", match="false")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])
        self.assertIn("[ROUTER][WAIT]", r.stdout)

    def test_mixed_release_candidate_once_then_wait(self):
        paths = ("VeraInternal/jni/Nara/Mora.hpp", "Launcher/jni/Main.cpp")
        r, sent = self.run_route(*paths, approval="false")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_event(sent, "component-lib")
        r, sent = self.run_route(*paths, approval="false", candidate="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])

    def test_kyronlink_validation_not_dropped_while_native_waits(self):
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", "KyronLink/build.ps1", approval="false", candidate="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_event(sent, "component-kyronlink")

    def test_successful_kyronlink_receipt_suppresses_repeated_validation(self):
        r, sent = self.run_route("KyronLink/build.ps1", kyronlink_validated="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])
        self.assertIn("[ROUTER][KYRONLINK/NOOP]", r.stdout)

    def test_native_wait_does_not_repeat_kyronlink_when_validated(self):
        r, sent = self.run_route("VeraInternal/src/Native.cpp", "KyronLink/build.ps1", approval="false",
                                candidate="true", kyronlink_validated="true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sent, [])

    def test_invalid_kyronlink_receipt_state_rejected(self):
        r, sent = self.run_route("KyronLink/build.ps1", kyronlink_validated="unknown")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(sent, [])

    def test_unknown_readiness_flag_rejected(self):
        r, sent = self.run_route("VeraInternal/jni/Nara/Mora.hpp", approval="invalid")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(sent, [])

    def test_invalid_sha_and_noncanonical_context_are_rejected(self):
        for kwargs in ({"sha": "A" * 40}, {"repository": "fixture/other"}, {"ref": "refs/heads/other"}):
            with self.subTest(kwargs=kwargs):
                result, sent = self.run_route("Launcher/jni/Main.cpp", **kwargs); self.assertNotEqual(result.returncode, 0); self.assertEqual(sent, [])

    def test_dispatch_failure_propagates(self):
        result, sent = self.run_route("VeraInternal/src/Native.cpp", gh_exit=19); self.assertEqual(result.returncode, 19); self.assertEqual(len(sent), 1); self.assertNotIn("[ROUTER][DISPATCHED]", result.stdout)

if __name__ == "__main__": unittest.main(verbosity=2)
