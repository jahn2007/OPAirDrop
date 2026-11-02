#!/usr/bin/env python3
"""Offline regression tests for retrying a pinned CodeLinaro repo checkout."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ace2-sync-kernel.sh"
PINNED = "0fc3d01a780023469b7acc18c56a9cf5099a6d6c"
FAKE_REPO = """#!/usr/bin/env python3
import os, sys
from pathlib import Path
log = Path(os.environ['ACE2_MOCK_CALLS'])
args = sys.argv[1:]
if not args or args[0] != 'sync':
    sys.exit(2)
with log.open('a', encoding='utf-8') as f:
    f.write(' '.join(args) + '\\n')
calls = log.read_text().splitlines()
scenario = os.environ.get('ACE2_MOCK_SCENARIO', 'checkout')
if scenario == 'generic' and len(calls) == 1:
    print('Cannot checkout unrelated project')
    sys.exit(1)
if scenario in ('checkout', 'recovery-fails') and len(calls) == 1:
    print('error.GitError: Cannot checkout kernelplatform/prebuilts-master/clang/host/linux-x86: Cannot initialize work tree for kernelplatform/prebuilts-master/clang/host/linux-x86')
    sys.exit(1)
if scenario == 'recovery-fails' and len(calls) <= 3:
    print('Transient checkout failed again')
    sys.exit(1)
print('repo sync completed')
"""
FAKE_GIT = """#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if 'rev-parse' in args and 'HEAD' in args:
    print(os.environ.get('ACE2_MOCK_SHA', '0fc3d01a780023469b7acc18c56a9cf5099a6d6c'))
elif 'status' in args:
    print('## HEAD (detached)')
"""


class Ace2RepoSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "platform"
        self.root.mkdir()
        (self.root / "kernel_platform/prebuilts-master/clang/host/linux-x86").mkdir(parents=True)
        self.report = base / "reports"
        self.bin = base / "bin"
        self.bin.mkdir()
        for name, script in (("repo", FAKE_REPO), ("git", FAKE_GIT)):
            path = self.bin / name
            path.write_text(script, encoding="utf-8")
            path.chmod(0o755)
        self.calls = base / "repo-calls.log"
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env["PATH"],
            "ACE2_SYNC_ROOT": str(self.root),
            "ACE2_REPORT_ROOT": str(self.report),
            "ACE2_MOCK_CALLS": str(self.calls),
            "ACE2_SYNC_JOBS": "2",
        })

    def run_sync(self):
        return subprocess.run(["bash", str(SCRIPT)], env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=15)

    def test_known_clang_failure_retries_serially_and_resumes(self):
        p = self.run_sync()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("ACE2_SYNC_SUCCESS", p.stdout)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(len(calls), 3)
        self.assertIn("-j1", calls[1])
        self.assertIn("kernel_platform/prebuilts-master/clang/host/linux-x86", calls[1])
        self.assertNotIn("--force-checkout", " ".join(calls))
        self.assertTrue((self.report / "repo-sync-clang-1.log").exists())

    def test_other_failure_is_not_hidden_by_retry(self):
        self.env["ACE2_MOCK_SCENARIO"] = "generic"
        p = self.run_sync()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ACE2_SYNC_OTHER_FAILURE", p.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)

    def test_failed_recovery_exits_nonzero(self):
        self.env["ACE2_MOCK_SCENARIO"] = "recovery-fails"
        p = self.run_sync()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ACE2_SYNC_CLANG_RECOVERY_FAILED", p.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 3)

    def test_wrong_clang_revision_fails_closed(self):
        self.env["ACE2_MOCK_SCENARIO"] = "success"
        self.env["ACE2_MOCK_SHA"] = "0" * 40
        p = self.run_sync()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("ACE2_SYNC_CLANG_PIN_MISMATCH", p.stdout)
        self.assertEqual(len(self.calls.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
