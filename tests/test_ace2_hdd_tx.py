#!/usr/bin/env python3
"""Source-level staging tests for SM8475 HDD PAS-only TX dispatch."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ace2-port-hdd-tx.py"
spec = importlib.util.spec_from_file_location("ace2_hdd", TOOL)
hdd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hdd)


class Ace2HddTxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / hdd.TARGET
        self.path.parent.mkdir(parents=True)
        self.path.write_text("/* Qualcomm */\n" + hdd.ANCHOR + "\n", encoding="utf-8")

    def test_stage_dry_run_and_idempotence(self):
        initial = self.path.read_bytes()
        self.assertEqual(hdd.stage(self.root, False)["state"], "would-stage")
        self.assertEqual(self.path.read_bytes(), initial)
        self.assertEqual(hdd.stage(self.root, True)["state"], "staged")
        changed = self.path.read_text()
        self.assertIn("adapter->device_mode == QDF_PASSTHRU_MODE", changed)
        self.assertIn("return passthru_result == 2 ? NETDEV_TX_BUSY : NETDEV_TX_OK", changed)
        self.assertIn("__hdd_hard_start_xmit(skb, net_dev)", changed)
        self.assertEqual(hdd.stage(self.root, True)["state"], "already-staged")
        self.assertFalse(hdd.stage(self.root, True)["hook_compiled"])

    def test_no_source_fails_closed(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing official"):
            hdd.stage(self.root, True)

    def test_drift_refuses_changes(self):
        altered = self.path.read_text().replace("hdd_dp_ssr_protect();", "changed_protect();")
        self.path.write_text(altered)
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            hdd.stage(self.root, True)
        self.assertEqual(self.path.read_text(), altered)

    def test_partial_duplicate_refused(self):
        altered = self.path.read_text() + "\nextern int opairshare_pas_mgmt_xmit(void);\n"
        self.path.write_text(altered)
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            hdd.stage(self.root, True)


if __name__ == "__main__":
    unittest.main()
