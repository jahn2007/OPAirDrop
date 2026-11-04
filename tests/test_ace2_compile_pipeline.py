#!/usr/bin/env python3
"""Fast tests for full-GKI versus WLAN-diagnostic pipeline failure ownership."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[1] / "tools/ace2-compile-pipeline.sh"
FAKE_GKI = """#!/usr/bin/env bash
mkdir -p "$ACE2_REPORT_ROOT"
if [[ "${ACE2_TEST_KMI:-0}" == 1 ]]; then
  printf 'ERROR: Differences between ksymtab and symbol list detected!\\nSymbols missing from ksymtab:\\n - __cfi_slowpath\\n' > "$ACE2_REPORT_ROOT/kernel-build.log"
else
  printf 'fake compiler message\\n' > "$ACE2_REPORT_ROOT/kernel-build.log"
fi
exit "${ACE2_TEST_GKI_RC:-0}"
"""
FAKE_WLAN = """#!/usr/bin/env bash
echo called > "$ACE2_REPORT_ROOT/wlan-called"
exit "${ACE2_TEST_WLAN_RC:-0}"
"""


class PipelineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.port = self.root / "port"
        (self.port / "tools").mkdir(parents=True)
        for filename, src in (("ace2-run-vendor-build.sh", FAKE_GKI),
                              ("ace2-build-wlan.sh", FAKE_WLAN)):
            path = self.port / "tools" / filename
            path.write_text(src)
        self.source = self.root / "official"
        self.out = self.source / "kernel_platform/out/msm-waipio-waipio-gki/gki_kernel/common"
        self.out.mkdir(parents=True)
        (self.out / "Module.symvers").write_text("real-like symbols")
        self.reports = self.root / "reports"
        self.env = dict(os.environ)
        self.env.update({
            "ACE2_PORT_ROOT": str(self.port),
            "ACE2_PLATFORM_ROOT": str(self.source),
            "ACE2_REPORT_ROOT": str(self.reports),
            "ACE2_COMPILE_CANDIDATE": "1",
        })

    def run_pipeline(self):
        return subprocess.run(["bash", str(RUNNER)], env=self.env,
                              text=True, capture_output=True, timeout=15)

    def test_success_runs_both_build_stages(self):
        p = self.run_pipeline()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue((self.reports / "wlan-called").exists())
        self.assertIn("gki_kmi_passed=true",
                      (self.reports / "compile-stage-results.txt").read_text())

    def test_kmi_failure_collects_wlan_error_but_never_passes(self):
        self.env.update(ACE2_TEST_GKI_RC="1", ACE2_TEST_KMI="1")
        p = self.run_pipeline()
        self.assertNotEqual(p.returncode, 0)
        self.assertTrue((self.reports / "wlan-called").exists())
        self.assertIn("gki_kmi_passed=false",
                      (self.reports / "compile-stage-results.txt").read_text())

    def test_unknown_gki_failure_blocks_wlan(self):
        self.env["ACE2_TEST_GKI_RC"] = "9"
        p = self.run_pipeline()
        self.assertEqual(p.returncode, 9)
        self.assertFalse((self.reports / "wlan-called").exists())

    def test_missing_symvers_blocks_wlan_after_kmi_failure(self):
        self.env.update(ACE2_TEST_GKI_RC="1", ACE2_TEST_KMI="1")
        (self.out / "Module.symvers").unlink()
        p = self.run_pipeline()
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.reports / "wlan-called").exists())

    def test_wlan_failure_is_not_masked(self):
        self.env["ACE2_TEST_WLAN_RC"] = "17"
        p = self.run_pipeline()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("wlan_exit=17",
                      (self.reports / "compile-stage-results.txt").read_text())

    def test_baseline_never_runs_candidate_wlan(self):
        self.env["ACE2_COMPILE_CANDIDATE"] = "0"
        p = self.run_pipeline()
        self.assertEqual(p.returncode, 0)
        self.assertFalse((self.reports / "wlan-called").exists())


if __name__ == "__main__":
    unittest.main()
