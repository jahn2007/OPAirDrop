#!/usr/bin/env python3
"""Mocked, fast checks of candidate source guardrails; no kernel needed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ace2-preflight-candidate.py"
spec = importlib.util.spec_from_file_location("ace2_preflight", TOOL)
pre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pre)


class Ace2CandidatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = {
            pre.HDD: (
                "netdev_tx_t hdd_hard_start_xmit("
                "\n#if defined(OPAIRSHARE_ACE2_PAS_BRIDGE)\n"
                "int opairshare_pas_mgmt_xmit(struct sk_buff *skb);\n"
                "adapter->device_mode == QDF_PASSTHRU_MODE;\n"
                "opairshare_pas_mgmt_xmit(skb);\n"
                "return passthru_result == 2 ? NETDEV_TX_BUSY : NETDEV_TX_OK;\n"
            ),
            pre.WMA: (
                "QDF_STATUS wma_tx_packet(\n"
                "#if defined(OPAIRSHARE_ACE2_PAS_BRIDGE) && defined(DRIVER_PASSTHRU_MODE)\n"
                '#include "wma_opairshare_pas_mgmt.h"\n#endif\n'
            ),
            pre.BRIDGE: (
                "#ifdef DRIVER_PASSTHRU_MODE\n"
                '#include "wma_opairshare_awdl_target.h"\n'
                "int opairshare_pas_mgmt_xmit(struct sk_buff *skb);\n#endif\n"
            ),
            pre.KBUILD: (
                "$(foreach cfg, $(WLAN_CFG_OVERRIDE),\n"
                "  $(eval $(cfg)))\n"
                "ccflags-$(CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE) += "
                "-DOPAIRSHARE_ACE2_PAS_BRIDGE -DDRIVER_PASSTHRU_MODE\n"
            ),
            pre.QDF: "QDF_PASSTHRU_MODE,\n",
            pre.BRIDGE.parent / "wma_opairshare_awdl_target.h": "#pragma once\n",
        }
        for path, body in self.data.items():
            p = self.root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

    def test_complete_stage_passes_without_claiming_compilation(self):
        report = pre.validate(self.root)
        self.assertTrue(report["candidate_source_preflight"], report)
        self.assertFalse(report["driver_compiled"])
        self.assertFalse(report["airdrop_verified"])

    def test_missing_local_wma_helper_fails(self):
        (self.root / pre.BRIDGE.parent / "wma_opairshare_awdl_target.h").unlink()
        report = pre.validate(self.root)
        self.assertFalse(report["candidate_source_preflight"])
        self.assertTrue(any("missing WMA helper" in v for v in report["errors"]))

    def test_missing_bridge_build_flag_fails(self):
        (self.root / pre.KBUILD).write_text("$(foreach cfg, $(WLAN_CFG_OVERRIDE), $(eval $(cfg)))\n")
        report = pre.validate(self.root)
        self.assertFalse(report["checks"]["kbuild_bridge_defines"])

    def test_missing_native_hdd_refuses(self):
        (self.root / pre.HDD).unlink()
        report = pre.validate(self.root)
        self.assertFalse(report["candidate_source_preflight"])

    def test_donor_hdd_passthru_conflict_refuses(self):
        path = self.root / pre.HDD
        path.write_text(path.read_text() + "hdd_hard_start_xmit_passthru(\n")
        report = pre.validate(self.root)
        self.assertFalse(report["checks"]["hdd_native_tx"])

    def test_conflict_markers_fail(self):
        path = self.root / pre.QDF
        path.write_text("<<<<<<< sm8475-target\n=======\n>>>>>>> opairdrop-overlay\n")
        report = pre.validate(self.root)
        self.assertFalse(report["checks"]["no_conflict_markers"])


if __name__ == "__main__":
    unittest.main()
