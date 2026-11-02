#!/usr/bin/env python3
"""Fast mocked tests of the exact Ace 2 vendor build entrypoint contract."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ace2-run-vendor-build.sh"

STUB = """#!/usr/bin/env bash
printf 'target=%s variant=%s board=%s recomp=%s\\n' "$1" "$2" "$TARGET_BOARD_PLATFORM" "$RECOMPILE_KERNEL"
if [[ "\${ACE2_MOCK_WLAN_LINE:-0}" == 1 ]]; then
  echo 'Kbuild: Overriding WLAN config with: CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y'
fi
exit "\${ACE2_MOCK_EXIT:-0}"
"""


class VendorBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.platform = root / "official"
        self.reports = root / "reports"
        self.entry = self.platform / "kernel_platform/build/android/prepare_vendor.sh"
        self.entry.parent.mkdir(parents=True)
        self.entry.write_text(STUB, encoding="utf-8")
        self.env = dict(os.environ)
        self.env.update({
            "ACE2_PLATFORM_ROOT": str(self.platform),
            "ACE2_REPORT_ROOT": str(self.reports),
            "ACE2_COMPILE_CANDIDATE": "0",
        })

    def run_build(self):
        return subprocess.run(
            ["bash", str(SCRIPT)], env=self.env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15,
        )

    def test_vendor_nonzero_cannot_be_masked_by_tee(self):
        self.env["ACE2_MOCK_EXIT"] = "17"
        result = self.run_build()
        self.assertEqual(result.returncode, 17, result.stdout)
        self.assertIn("ACE2_BASELINE_BUILD_FAILED exit_code=17", result.stdout)
        self.assertIn("target=waipio variant=gki board=taro recomp=1",
                      (self.reports / "kernel-build.log").read_text())

    def test_baseline_does_not_require_wlan_override(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ACE2_VENDOR_BUILD_EXIT_SUCCESS", result.stdout)

    def test_candidate_rejects_missing_wlan_compilation(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        result = self.run_build()
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertIn("ACE2_CANDIDATE_WLAN_CFG_NOT_CONSUMED", result.stdout)

    def test_candidate_wlan_override_is_visible(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env["ACE2_MOCK_WLAN_LINE"] = "1"
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_official_entrypoint_fails(self):
        self.entry.unlink()
        result = self.run_build()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("ACE2_BUILD_ENTRYPOINT_MISSING", result.stdout)


if __name__ == "__main__":
    unittest.main()
