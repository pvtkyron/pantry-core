import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

spec = importlib.util.spec_from_file_location("delivery", Path(__file__).parents[1] / "scripts/restore_prepared_delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
SHA = "a" * 40
SECRET = "\ufeff delivery-key\r\n"
PATH = "source/Distribution/release/runtime-lane-v1.json"

def envelope(path=PATH, content=b'{"schema":1}\n', *, sha=SHA, extra=False, wrong_digest=False):
    memory = io.BytesIO()
    row = {"path": path, "size": len(content), "sha256": "0" * 64 if wrong_digest else hashlib.sha256(content).hexdigest()}
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr("handoff.json", json.dumps({"schema": 1, "lane": "delivery", "workspace_sha": sha, "pantry_sha": sha, "files": [row]}))
        archive.writestr(path, content)
        if extra:
            archive.writestr("source/Distribution/client/unlisted.exe", b"unlisted")
    material = hashlib.sha512(("kyron-ci-handoff-v1\0" + SECRET).encode()).digest()
    padder = padding.PKCS7(128).padder()
    padded = padder.update(memory.getvalue()) + padder.finalize()
    iv = os.urandom(16)
    encryptor = Cipher(algorithms.AES(material[:32]), modes.CBC(iv)).encryptor()
    body = b"KYRONCI1" + iv + encryptor.update(padded) + encryptor.finalize()
    return body + hmac.digest(material[32:], body, "sha256")

class PreparedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        self.blob = Path(self.temp.name) / "delivery.bin"
        self.destination = self.root / "Distribution/release/runtime-lane-v1.json"
        self.head = patch.object(delivery.subprocess, "check_output", return_value=SHA + "\n")
        self.ignored = patch.object(delivery.subprocess, "run", return_value=SimpleNamespace(returncode=0))
        self.head.start()
        self.ignored_mock = self.ignored.start()
        self.addCleanup(self.head.stop)
        self.addCleanup(self.ignored.stop)

    def restore(self, blob):
        self.blob.write_bytes(blob)
        delivery.restore(self.blob, self.root, SHA, SECRET)

    def test_valid_original_bytes_restore_and_idempotent_retry(self):
        blob = envelope()
        self.restore(blob)
        self.assertEqual(self.destination.read_bytes(), b'{"schema":1}\n')
        self.restore(blob)

    def test_ciphertext_tampering_fails_before_writes(self):
        blob = bytearray(envelope())
        blob[30] ^= 1
        with self.assertRaisesRegex(ValueError, "authentication"):
            self.restore(blob)
        self.assertFalse(self.destination.exists())

    def test_wrong_source_receipt_fails(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.restore(envelope(sha="b" * 40))

    def test_traversal_fails_even_when_authenticated(self):
        with self.assertRaisesRegex(ValueError, "path"):
            self.restore(envelope(path="source/Distribution/client/runtime/" + "a" * 32 + "/../../outside"))

    def test_source_file_is_not_a_delivery(self):
        with self.assertRaisesRegex(ValueError, "path"):
            self.restore(envelope(path="source/Distribution/tools/owner.py"))

    def test_unlisted_archive_file_fails(self):
        with self.assertRaisesRegex(ValueError, "path|inventory"):
            self.restore(envelope(extra=True))

    def test_changed_destination_is_preserved(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_bytes(b"existing")
        with self.assertRaisesRegex(ValueError, "different data"):
            self.restore(envelope())
        self.assertEqual(self.destination.read_bytes(), b"existing")

    def test_file_digest_mismatch_fails_before_writes(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            self.restore(envelope(wrong_digest=True))
        self.assertFalse(self.destination.exists())

    def test_tracked_or_unignored_destination_fails(self):
        self.ignored_mock.return_value = SimpleNamespace(returncode=1)
        with self.assertRaisesRegex(ValueError, "ignored"):
            self.restore(envelope())

    def test_pinned_checkout_must_match(self):
        with patch.object(delivery.subprocess, "check_output", return_value="b" * 40):
            with self.assertRaisesRegex(ValueError, "checkout"):
                self.restore(envelope())

if __name__ == "__main__":
    unittest.main(verbosity=2)
