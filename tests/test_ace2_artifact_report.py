#!/usr/bin/env python3
"""Fast offline checks of target-specific QCACLD module verification."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ace2-artifact-report.py"


class Ace2ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "kernel_platform").mkdir()
        self.out = self.root / "reports" / "modules.json"

    def execute(self):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root),
                               "--out", str(self.out)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=10)

    def test_unrelated_wlan_name_cannot_falsely_pass(self):
        (self.root / "kernel_platform" / "wlan_platform.ko").write_bytes(b"not an ELF")
        result = self.execute()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("No qcacld-3.0 wlan.ko", result.stdout)
        self.assertFalse(json.loads(self.out.read_text())["qcacld_wlan_found"])

    def test_unrelated_wlan_module_cannot_falsely_pass(self):
        (self.root / "kernel_platform" / "wlan.ko").write_bytes(b"\x7fELFother")
        result = self.execute()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(json.loads(self.out.read_text())["qcacld_wlan_found"])

    def test_exact_wlan_module_is_identified(self):
        wlan = self.root / "vendor/qcom/opensource/wlan/qcacld-3.0/wlan.ko"
        wlan.parent.mkdir(parents=True)
        wlan.write_bytes(b"\x7fELFmodule-test-fixture")
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue(json.loads(self.out.read_text())["qcacld_wlan_found"])

    def test_wrong_file_magic_cannot_falsely_pass(self):
        wlan = self.root / "vendor/qcom/opensource/wlan/qcacld-3.0/wlan.ko"
        wlan.parent.mkdir(parents=True)
        wlan.write_bytes(b"NOT_AN_ELF")
        result = self.execute()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertFalse(json.loads(self.out.read_text())["qcacld_wlan_found"])

    def test_empty_modules_are_rejected(self):
        result = self.execute()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No kernel modules found", result.stdout)


if __name__ == "__main__":
    unittest.main()
