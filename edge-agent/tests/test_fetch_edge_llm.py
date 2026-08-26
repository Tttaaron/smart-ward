"""拉取/校验脚本（scripts/fetch_edge_llm.py）的下载与 sha256 校验测试"""

import hashlib
import os
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from fetch_edge_llm import download  # noqa: E402


class FetchEdgeLLMTest(unittest.TestCase):
    def _make_source(self, tmp, content=b"distilled-gguf-bytes"):
        src = os.path.join(tmp, "src.gguf")
        with open(src, "wb") as f:
            f.write(content)
        return src, hashlib.sha256(content).hexdigest()

    def test_download_with_correct_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, digest = self._make_source(tmp)
            dest = os.path.join(tmp, "out", "model.gguf")
            actual = download(src, dest, digest)
            self.assertEqual(actual, digest)
            self.assertTrue(os.path.exists(dest))
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"distilled-gguf-bytes")

    def test_download_wrong_checksum_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, _ = self._make_source(tmp)
            dest = os.path.join(tmp, "out", "model.gguf")
            with self.assertRaises(SystemExit):
                download(src, dest, "0" * 64)
            self.assertFalse(os.path.exists(dest))

    def test_download_file_url_scheme(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, digest = self._make_source(tmp)
            dest = os.path.join(tmp, "out", "model.gguf")
            actual = download("file://" + src, dest, "sha256:" + digest)
            self.assertEqual(actual, digest)
            self.assertTrue(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
