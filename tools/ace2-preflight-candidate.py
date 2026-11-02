#!/usr/bin/env python3
"""Fail-closed, fast preflight for the staged OnePlus Ace 2 WLAN candidate.

This verifies source wiring, not compilation, KMI compatibility or firmware.
Run before the expensive official kernel build.
"""
import argparse
import json
import re
from pathlib import Path

WLAN = Path("vendor/qcom/opensource/wlan")
HDD = WLAN / "qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c"
WMA = WLAN / "qcacld-3.0/core/wma/src/wma_data.c"
BRIDGE = WLAN / "qcacld-3.0/core/wma/src/wma_opairshare_pas_mgmt.h"
KBUILD = WLAN / "qcacld-3.0/Kbuild"
QDF = WLAN / "qca-wifi-host-cmn/qdf/inc/qdf_types.h"
CANDIDATE_HEADERS = re.compile(r'^\s*#\s*include\s+"(wma_opairshare_[\w-]+\.h|ace2_awdl_frame\.h)"\s*$', re.M)


def validate(root: Path) -> dict:
    base = root.resolve()
    paths = (HDD, WMA, BRIDGE, KBUILD, QDF)
    src = {}
    errors = []
    for rel in paths:
        p = (base / rel).resolve()
        if not p.is_relative_to(base) or not p.is_file():
            errors.append(f"missing: {rel}")
        else:
            src[str(rel)] = p.read_text(encoding="utf-8")
    if errors:
        return {"candidate_source_preflight": False, "errors": errors,
                "driver_compiled": False, "airdrop_verified": False}

    hdd, wma, bridge, kbuild, qdf = (src[str(r)] for r in paths)
    checks = {
        "hdd_native_tx": hdd.count("netdev_tx_t hdd_hard_start_xmit(") == 1
            and "hdd_hard_start_xmit_passthru(" not in hdd,
        "hdd_pas_dispatch": hdd.count("opairshare_pas_mgmt_xmit(") == 2
            and "adapter->device_mode == QDF_PASSTHRU_MODE" in hdd
            and "NETDEV_TX_BUSY : NETDEV_TX_OK" in hdd,
        "wma_native_include": wma.count('#include "wma_opairshare_pas_mgmt.h"') == 1
            and wma.count("QDF_STATUS wma_tx_packet(") == 1,
        "wma_feature_guard": "#if defined(OPAIRSHARE_ACE2_PAS_BRIDGE) && defined(DRIVER_PASSTHRU_MODE)" in wma,
        "pas_bridge_definition": "int opairshare_pas_mgmt_xmit(" in bridge
            and "#ifdef DRIVER_PASSTHRU_MODE" in bridge,
        "qdf_pas_enum": qdf.count("QDF_PASSTHRU_MODE,") == 1,
        "kbuild_override_consumed": "WLAN_CFG_OVERRIDE" in kbuild
            and "$(eval $(cfg))" in kbuild,
        "kbuild_bridge_defines": "ccflags-$(CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE)" in kbuild
            and "-DOPAIRSHARE_ACE2_PAS_BRIDGE -DDRIVER_PASSTHRU_MODE" in kbuild,
        "no_conflict_markers": all(
            "<<<<<<<" not in content and ">>>>>>>" not in content
            for content in src.values()
        ),
    }
    headers = {name for name in CANDIDATE_HEADERS.findall(bridge)}
    # The WMA bridge includes a family of source-local helpers: verify the
    # entire bundle has been staged instead of discovering a missing header
    # only after the expensive GKI link finishes.
    for name in headers:
        local = (base / BRIDGE.parent / name).resolve()
        if not local.is_relative_to(base) or not local.is_file():
            errors.append(f"missing WMA helper: {name}")
    checks["wma_helper_headers"] = bool(headers) and not errors
    failures = sorted(name for name, ok in checks.items() if not ok)
    failures.extend(errors)
    return {
        "candidate_source_preflight": not failures,
        "checks": checks,
        "errors": failures,
        "wma_headers_verified": sorted(headers),
        "driver_compiled": False,
        "airdrop_verified": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--report", type=Path)
    opts = p.parse_args()
    result = validate(opts.source)
    if opts.report:
        opts.report.parent.mkdir(parents=True, exist_ok=True)
        opts.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["candidate_source_preflight"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
