#!/usr/bin/env python3
"""Host-only tests for the native Ace 2 WMA bridge integration point."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ace2-port-wma-hook.py"
spec = importlib.util.spec_from_file_location("ace2_wma_hook", TOOL)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

C_SOURCE = """#include <linux/types.h>
QDF_STATUS wma_tx_packet(void)
{
    return QDF_STATUS_SUCCESS;
error:
    return QDF_STATUS_E_FAILURE;
}

/**
 * wma_ds_peek_rx_packet_info() - peek rx packet info
 */
QDF_STATUS wma_ds_peek_rx_packet_info(void)
{
    return QDF_STATUS_SUCCESS;
}
"""

HEADER = """#ifdef DRIVER_PASSTHRU_MODE
bool opairshare_pas_mgmt_xmit(void);
#endif
"""


class Ace2WmaHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        directory = self.root / hook.WLAN
        directory.mkdir(parents=True)
        self.wma = directory / "wma_data.c"
        self.bridge = directory / "wma_opairshare_pas_mgmt.h"
        self.wma.write_text(C_SOURCE, encoding="utf-8")
        self.bridge.write_text(HEADER, encoding="utf-8")

    def test_dry_run_write_and_idempotence(self):
        original = self.wma.read_bytes()
        self.assertEqual(hook.port(self.root, False)["state"], "would-stage")
        self.assertEqual(original, self.wma.read_bytes())
        self.assertEqual(hook.port(self.root, True)["state"], "staged")
        self.assertEqual(self.wma.read_text().count(hook.INCLUDE), 1)
        staged = self.wma.read_bytes()
        self.assertEqual(hook.port(self.root, True)["state"], "already-staged")
        self.assertEqual(staged, self.wma.read_bytes())
        self.assertFalse(hook.port(self.root, True)["driver_compiled"])

    def test_no_header_fails_closed(self):
        self.bridge.unlink()
        original = self.wma.read_bytes()
        with self.assertRaisesRegex(ValueError, "not staged"):
            hook.port(self.root, True)
        self.assertEqual(original, self.wma.read_bytes())

    def test_changed_vendor_function_fails_closed(self):
        self.wma.write_text(C_SOURCE.replace("wma_tx_packet", "some_other_packet"))
        with self.assertRaisesRegex(ValueError, "TX function layout"):
            hook.port(self.root, True)

    def test_unexpected_duplicate_include_fails_closed(self):
        self.wma.write_text('#include "wma_opairshare_pas_mgmt.h"\n' + C_SOURCE)
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            hook.port(self.root, True)

    def test_bad_donor_header_fails_closed(self):
        self.bridge.write_text("/* unrelated */")
        with self.assertRaisesRegex(ValueError, "Unexpected WMA bridge header"):
            hook.port(self.root, True)


if __name__ == "__main__":
    unittest.main()
