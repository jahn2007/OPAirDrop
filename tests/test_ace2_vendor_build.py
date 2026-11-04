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
printf 'LTO=%s\\n' "${LTO:-stock}"
if [[ "${ACE2_MOCK_WLAN_LINE:-0}" == 1 ]]; then
  echo 'Kbuild: Overriding WLAN config with: CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y'
fi
exit "${ACE2_MOCK_EXIT:-0}"
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

    def test_candidate_gki_success_without_wlan_kbuild_log(self):
        # Official prepare_vendor compiles GKI/vendor pieces; the separate
        # ace2-build-wlan.sh owns the PAS flag and actual wlan.ko checks.
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env["WLAN_CFG_OVERRIDE"] = "CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y"
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ACE2_GKI_BUILD_PASSED_WLAN_MODULE_UNVERIFIED", result.stdout)
        self.assertNotIn("Overriding WLAN config", result.stdout)

    def test_candidate_vendor_does_not_claim_wlan_compilation(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env["ACE2_MOCK_WLAN_LINE"] = "1"
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ACE2_GKI_BUILD_PASSED_WLAN_MODULE_UNVERIFIED", result.stdout)
        self.assertNotIn("ACE2_WLAN_EXTERNAL_BUILD_SUCCESS", result.stdout)

    def test_candidate_defaults_to_fast_non_release_lto(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env.pop("LTO", None)
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("LTO=thin", result.stdout)
        self.assertIn("diagnostic_candidate_not_abi_verified=true",
                      (self.reports / "build-invocation.txt").read_text())

    def test_candidate_rejects_no_lto_cfi_kmi_mismatch(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env["ACE2_DIAGNOSTIC_LTO"] = "none"
        result = self.run_build()
        self.assertEqual(result.returncode, 2)
        self.assertIn("ACE2_LTO_NONE_CFI_KMI_INCOMPATIBLE", result.stdout)
        self.assertFalse((self.reports / "kernel-build.log").exists())

    def test_candidate_rejects_invalid_lto(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "1"
        self.env["ACE2_DIAGNOSTIC_LTO"] = "invalid"
        result = self.run_build()
        self.assertEqual(result.returncode, 2)
        self.assertIn("ACE2_UNSUPPORTED_DIAGNOSTIC_LTO", result.stdout)

    def test_missing_official_entrypoint_fails(self):
        self.entry.unlink()
        result = self.run_build()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("ACE2_BUILD_ENTRYPOINT_MISSING", result.stdout)


if __name__ == "__main__":
    unittest.main()
