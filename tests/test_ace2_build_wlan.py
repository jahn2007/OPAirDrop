#!/usr/bin/env python3
"""Fast mocked contract tests for the official Ace 2 external WLAN build gate."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/ace2-build-wlan.sh"

FAKE_MAKE = """#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
pathlib.Path(os.environ['ACE2_TEST_MAKE_ARGS']).write_text('\\n'.join(args))
rc = int(os.environ.get('ACE2_TEST_MAKE_EXIT', '0'))
if rc:
    sys.exit(rc)
if os.environ.get('ACE2_TEST_SKIP_KO') != '1':
    m = next(s[2:] for s in args if s.startswith('M='))
    (pathlib.Path(m) / 'wlan.ko').write_bytes(b'\\x7fELFmockkernelmodule')
if os.environ.get('ACE2_TEST_SKIP_FLAG') != '1':
    print('Overriding WLAN config with: CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y')
"""


class WlanBuildTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.platform = self.tmp / "official"
        self.reports = self.tmp / "reports"
        self.kout = self.platform / "kernel_platform/out/msm-waipio-waipio-gki/gki_kernel/common"
        self.clang = self.platform / "kernel_platform/prebuilts-master/clang/host/linux-x86/clang-r123/bin"
        self.wlan = self.platform / "vendor/qcom/opensource/wlan/qcacld-3.0"
        for p in (self.clang, self.wlan / "cmn",
                  self.platform / "vendor/qcom/opensource/wlan/fw-api",
                  self.platform / "kernel_platform/common",
                  self.kout / "include/generated",
                  self.kout / "include/config"):
            p.mkdir(parents=True, exist_ok=True)
        for p in (self.wlan / "Makefile", self.wlan / "Kbuild",
                  self.platform / "kernel_platform/common/Makefile",
                  self.kout / "include/generated/autoconf.h",
                  self.kout / "include/config/auto.conf",
                  self.kout / "include/generated/utsrelease.h"):
            p.write_text("placeholder")
        (self.kout / "include/generated/utsrelease.h").write_text('#define UTS_RELEASE "5.10.226"\\n')
        (self.kout / "Module.symvers").write_text("0x1\\tfake\\tvmlinux\\tEXPORT_SYMBOL\\n")
        (self.wlan / "Kbuild").write_text('ccflags-$(CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE) += -DOPAIRSHARE_ACE2_PAS_BRIDGE')
        (self.clang / "clang").write_text("#!/bin/sh\nexit 0\n")
        (self.clang / "clang").chmod(0o755)
        # Official CodeLinaro prebuilt project contains multiple clang-r*
        # directories. GKI build log, rather than glob order, is authoritative.
        for version in ("clang-r111", "clang-r222", "clang-r333"):
            other = self.clang.parent.parent / version / "bin"
            other.mkdir(parents=True)
            (other / "clang").write_text("#!/bin/sh\nexit 0\n")
            (other / "clang").chmod(0o755)
        self.reports.mkdir(parents=True)
        (self.reports / "kernel-build.log").write_text(
            f"PATH=/usr/bin:{self.clang}:/bin\n")
        bindir = self.tmp / "bin"
        bindir.mkdir()
        for name, text in {
            "make": FAKE_MAKE,
            "modinfo": "#!/bin/sh\necho \"${ACE2_TEST_MODINFO_VERSION:-5.10.226} SMP mod_unload\"\n",
            "readelf": "#!/bin/sh\necho 'ELF Header: AArch64'\n",
        }.items():
            p = bindir / name
            p.write_text(text)
            p.chmod(0o755)
        self.log = self.tmp / "make.args"
        self.env = dict(os.environ)
        self.env.update({
            "ACE2_PLATFORM_ROOT": str(self.platform),
            "ACE2_REPORT_ROOT": str(self.reports),
            "ACE2_COMPILE_CANDIDATE": "1",
            "ACE2_CLANG_BIN": str(self.clang),
            "ACE2_TEST_MAKE_ARGS": str(self.log),
            "WLAN_CFG_OVERRIDE": "CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y",
            "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
        })

    def run_build(self):
        return subprocess.run(["bash", str(SCRIPT)], env=self.env,
                              text=True, capture_output=True, timeout=20)

    def test_module_compiles_with_exact_vendor_parameters(self):
        p = self.run_build()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        args = self.log.read_text()
        for required in ("ARCH=arm64", "LLVM=1", "M=" + str(self.wlan),
                         "CONFIG_QCA_CLD_WLAN=m",
                         "CONFIG_CNSS_QCA6490=y",
                         "WLAN_CFG_OVERRIDE=CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y"):
            self.assertIn(required, args)
        self.assertTrue((self.reports / "wlan-sha256.txt").exists())
        self.assertIn("installable=false",
                      (self.reports / "wlan-build-invocation.txt").read_text())

    def test_selects_exact_gki_clang_from_multiple_synced_versions(self):
        self.env.pop("ACE2_CLANG_BIN")
        p = self.run_build()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        invocation = (self.reports / "wlan-build-invocation.txt").read_text()
        self.assertIn("compiler=" + str(self.clang / "clang"), invocation)
        self.assertIn("compiler_source=official_gki_build_log", invocation)
        self.assertIn("ACE2_WLAN_COMPILER_MATCHED_GKI", p.stdout)

    def test_refuses_ambiguous_gki_compiler_log(self):
        self.env.pop("ACE2_CLANG_BIN")
        with (self.reports / "kernel-build.log").open("a") as f:
            f.write("PATH=" + str(self.clang.parent.parent / "clang-r222/bin") + ":/bin\n")
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("exactly one synced Clang", p.stderr)
        self.assertFalse(self.log.exists())

    def test_refuses_missing_gki_compiler_log(self):
        self.env.pop("ACE2_CLANG_BIN")
        (self.reports / "kernel-build.log").unlink()
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("without kernel-build.log", p.stderr)
        self.assertFalse(self.log.exists())

    def test_refuses_explicit_mismatched_gki_compiler(self):
        other = self.clang.parent.parent / "clang-r222/bin"
        self.env["ACE2_CLANG_BIN"] = str(other)
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("differs from the compiler", p.stderr)
        self.assertFalse(self.log.exists())

    def test_prepared_symbols_are_mandatory(self):
        (self.kout / "Module.symvers").unlink()
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("Module.symvers missing", p.stderr)
        self.assertFalse(self.log.exists())

    def test_candidate_needs_explicit_pas_flag(self):
        self.env["WLAN_CFG_OVERRIDE"] = ""
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertFalse(self.log.exists())

    def test_nonzero_compiler_exit_survives_tee(self):
        self.env["ACE2_TEST_MAKE_EXIT"] = "23"
        p = self.run_build()
        self.assertEqual(p.returncode, 23, p.stdout + p.stderr)
        self.assertIn("ACE2_WLAN_COMPILER_FAILED", p.stderr)

    def test_missing_module_is_not_green(self):
        self.env["ACE2_TEST_SKIP_KO"] = "1"
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("no qcacld-3.0 wlan.ko", p.stderr)

    def test_missing_consumed_pas_flag_is_not_green(self):
        self.env["ACE2_TEST_SKIP_FLAG"] = "1"
        p = self.run_build()
        self.assertEqual(p.returncode, 3)
        self.assertIn("ACE2_WLAN_PAS_FLAG_NOT_CONSUMED", p.stderr)

    def test_rejects_unpinned_host_compiler(self):
        self.env["ACE2_CLANG_BIN"] = "/usr/bin"
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("refusing Clang outside", p.stderr)

    def test_mismatched_kernel_release_rejected(self):
        self.env["ACE2_TEST_MODINFO_VERSION"] = "6.6.118"
        p = self.run_build()
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("module vermagic does not match", p.stderr)

    def test_rejects_invalid_parallelism_before_compiler(self):
        self.env["ACE2_WLAN_JOBS"] = "500"
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("invalid WLAN parallel compiler limit", p.stderr)
        self.assertFalse(self.log.exists())

    def test_extra_symvers_must_exist(self):
        self.env["ACE2_WLAN_EXTRA_SYMBOLS"] = str(self.tmp / "missing.symvers")
        p = self.run_build()
        self.assertEqual(p.returncode, 2)
        self.assertIn("required external Module.symvers missing", p.stderr)


if __name__ == "__main__":
    unittest.main()
