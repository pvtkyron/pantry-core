"""Cross-language compatibility and rejection tests for the encrypted CI handoff.

Run with Python's cryptography dependency and pwsh (or KYRON_TEST_PWSH).
All keys and payloads here are disposable synthetic fixtures.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


SOURCE = Path(__file__).resolve().parents[1] / "workflows/workspace-handoff.ps1"
SECRET = "synthetic handoff fixture / \u06a9\u06cc\u0631\u0648\u0646"
MATERIAL = hashlib.sha512(("kyron-ci-handoff-v1\0" + SECRET).encode()).digest()
WORKER = r"""
param([string]$Source,[string]$Mode,[string]$InputFile,[string]$OutputFile)
$ErrorActionPreference='Stop'
$Secret=$env:KYRON_HANDOFF_TEST_SECRET
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Production handoff did not parse'}
foreach($name in @('Utf8','Derive','FixedEq','Protect-Bytes','Unprotect-Bytes')){
    $node=$ast.Find({param($n) $n-is[Management.Automation.Language.FunctionDefinitionAst]-and$n.Name-eq$name},$false)
    if(!$node){throw "Production function missing: $name"}
    . ([scriptblock]::Create($node.Extent.Text))
}
$inputBytes=[IO.File]::ReadAllBytes($InputFile)
$result=if($Mode-eq'protect'){Protect-Bytes $inputBytes}else{Unprotect-Bytes $inputBytes}
if($result-isnot[byte[]]){throw 'Handoff bytes were enumerated through the PowerShell pipeline'}
[IO.File]::WriteAllBytes($OutputFile,$result)
"""


def reference_seal(plain: bytes) -> bytes:
    # Fixed IV is confined to this independent fixture, never production output.
    iv = bytes(range(16))
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    encryptor = Cipher(algorithms.AES(MATERIAL[:32]), modes.CBC(iv)).encryptor()
    body = b"KYRONCI1" + iv + encryptor.update(padded) + encryptor.finalize()
    return body + hmac.digest(MATERIAL[32:], body, "sha256")


def reference_open(blob: bytes) -> bytes:
    assert blob[:8] == b"KYRONCI1"
    assert hmac.compare_digest(blob[-32:], hmac.digest(MATERIAL[32:], blob[:-32], "sha256"))
    decryptor = Cipher(algorithms.AES(MATERIAL[:32]), modes.CBC(blob[8:24])).decryptor()
    padded = decryptor.update(blob[24:-32]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


class FullSourceCheckoutTest(unittest.TestCase):
    """Expand the production complete-root pattern after a blobless recipe view."""

    def test_pinned_full_source_replaces_recipe_view_without_changing_inputs(self):
        with tempfile.TemporaryDirectory(prefix="kyron-checkout-test-") as directory:
            root=Path(directory);origin=root/"origin.git";author=root/"author";checkout=root/"checkout"
            def git(path,*args):
                return subprocess.run(["git","-C",str(path),*args],check=True,capture_output=True,text=True).stdout.strip()
            subprocess.run(["git","init","--bare","-q",str(origin)],check=True)
            subprocess.run(["git","init","-q","-b","main",str(author)],check=True)
            git(author,"config","user.name","fixture");git(author,"config","user.email","fixture@example.invalid")
            fixture={".gitattributes":b"* -text\n",
                     ".github/actions/private-capsule/action.yml":b"name: recipe\n",
                     "Distribution/SrcVersion.ini":b"pinned contract\n",
                     "Distribution/lib/runtime.bin":b"\0exact synthetic signed output\xff",
                     "Shared/contract.hpp":b"// pinned source\n","etc/build/owner.ps1":b"# pinned build owner\n"}
            for relative,data in fixture.items():
                path=author/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            git(author,"add",".");git(author,"commit","-q","-m","pinned fixture");pinned=git(author,"rev-parse","HEAD")
            git(author,"remote","add","origin",str(origin));git(author,"push","-q","origin","main")
            git(origin,"config","uploadpack.allowFilter","true")
            git(origin,"config","uploadpack.allowAnySHA1InWant","true")
            subprocess.run(["git","clone","-q","--filter=blob:none","--no-checkout","--depth=1","--branch","main",origin.as_uri(),str(checkout)],check=True)
            git(checkout,"sparse-checkout","set","--no-cone","/.github/")
            git(checkout,"checkout","-q","main")
            self.assertFalse((checkout/"Distribution").exists())
            # The authenticated second checkout sets this root explicitly;
            # no credential-free materialization of private blobs precedes it.
            git(checkout,"sparse-checkout","set","--no-cone","/*")
            git(checkout,"checkout","-q",pinned)
            for relative,data in fixture.items():self.assertEqual((checkout/relative).read_bytes(),data)
            self.assertEqual(git(checkout,"rev-parse","HEAD"),pinned)
            self.assertEqual(git(checkout,"status","--porcelain"),"")


class HandoffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwsh = os.environ.get("KYRON_TEST_PWSH") or shutil.which("pwsh") or shutil.which("powershell")
        if not cls.pwsh:
            raise RuntimeError("PowerShell is required; set KYRON_TEST_PWSH to its executable")

    def invoke(self, mode, payload, *, secret=SECRET, rejected=False):
        with tempfile.TemporaryDirectory(prefix="kyron-handoff-test-") as directory:
            root = Path(directory)
            script, source, output = root / "worker.ps1", root / "input.bin", root / "output.bin"
            script.write_text(WORKER, encoding="utf-8")
            source.write_bytes(payload)
            result = subprocess.run(
                [self.pwsh, "-NoLogo", "-NoProfile", "-File", str(script),
                 "-Source", str(SOURCE), "-Mode", mode,
                 "-InputFile", str(source), "-OutputFile", str(output)],
                env=os.environ | {"KYRON_HANDOFF_TEST_SECRET": secret},
                cwd=root, capture_output=True, text=True, timeout=60,
            )
            if rejected:
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists(), "Rejected ciphertext produced plaintext output")
                return result.stderr
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return output.read_bytes()

    def test_reference_format_both_directions_at_padding_boundaries(self):
        for length in (0, 1, 15, 16, 17, 63, 1024):
            with self.subTest(length=length):
                plain = bytes(index % 251 for index in range(length))
                self.assertEqual(self.invoke("unprotect", reference_seal(plain)), plain)
                self.assertEqual(reference_open(self.invoke("protect", plain)), plain)

    def test_multi_megabyte_buffer_round_trip(self):
        plain = bytes(range(256)) * 8192
        self.assertEqual(self.invoke("unprotect", self.invoke("protect", plain)), plain)

    def test_wrong_key_is_rejected_before_plaintext_output(self):
        error = self.invoke("unprotect", reference_seal(b"fixture"), secret="wrong synthetic key", rejected=True)
        self.assertIn("MAC mismatch", error)

    def test_header_iv_ciphertext_and_mac_corruption_are_rejected(self):
        sealed = reference_seal(b"authenticated fixture" * 4)
        for offset in (0, 8, 24, len(sealed) - 1):
            with self.subTest(offset=offset):
                damaged = bytearray(sealed)
                damaged[offset] ^= 1
                error = self.invoke("unprotect", damaged, rejected=True)
                self.assertIn("magic mismatch" if offset == 0 else "MAC mismatch", error)

    def test_truncated_packets_are_rejected(self):
        for length in (0, 7, 24, 71):
            with self.subTest(length=length):
                self.invoke("unprotect", reference_seal(b"fixture")[:length], rejected=True)

    def test_valid_mac_does_not_bypass_invalid_ciphertext_length(self):
        body = reference_seal(b"fixture" * 8)[:-33]
        malformed = body + hmac.digest(MATERIAL[32:], body, "sha256")
        error = self.invoke("unprotect", malformed, rejected=True)
        self.assertNotIn("MAC mismatch", error)

    def test_invalid_mac_is_rejected_before_invalid_ciphertext_length(self):
        sealed = reference_seal(b"fixture" * 8)
        malformed = sealed[:-33] + sealed[-32:]
        error = self.invoke("unprotect", malformed, rejected=True)
        self.assertIn("MAC mismatch", error)

    def test_fresh_iv_is_generated_for_each_seal(self):
        first = self.invoke("protect", b"same synthetic payload")
        second = self.invoke("protect", b"same synthetic payload")
        self.assertNotEqual(first[8:24], second[8:24])
        self.assertEqual(reference_open(first), reference_open(second))


if __name__ == "__main__":
    unittest.main()
