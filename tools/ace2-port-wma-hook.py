#!/usr/bin/env python3
"""Stage the Ace 2 WMA bridge include at the native SM8475 TX function boundary.

This only creates a guarded integration point; it does not certify that the
SM8750 donor bridge compiles against QCA6490 APIs or works on its firmware.
"""
import argparse
import json
from pathlib import Path

WLAN = Path("vendor/qcom/opensource/wlan/qcacld-3.0/core/wma/src")
INCLUDE = (
    "#if defined(OPAIRSHARE_ACE2_PAS_BRIDGE) && defined(DRIVER_PASSTHRU_MODE)\n"
    '#include "wma_opairshare_pas_mgmt.h"\n'
    "#endif /* OPAIRSHARE_ACE2_PAS_BRIDGE && DRIVER_PASSTHRU_MODE */\n"
)
ANCHOR = (
    "\n}\n\n/**\n"
    " * wma_ds_peek_rx_packet_info() - peek rx packet info\n"
)


def port(source: Path, write: bool) -> dict:
    root = source.resolve()
    directory = (root / WLAN).resolve()
    target = (directory / "wma_data.c").resolve()
    header = (directory / "wma_opairshare_pas_mgmt.h").resolve()
    if not directory.is_relative_to(root) or not target.is_file():
        raise ValueError("Missing official SM8475 WMA source tree")
    if not header.is_file():
        raise ValueError("WMA bridge header is not staged; port verified overlays first")
    donor = header.read_text(encoding="utf-8")
    if "#ifdef DRIVER_PASSTHRU_MODE" not in donor or "opairshare_pas_mgmt_xmit" not in donor:
        raise ValueError("Unexpected WMA bridge header contents")

    data = target.read_text(encoding="utf-8")
    staged_anchor = "\n}\n\n" + INCLUDE + "\n/**\n * wma_ds_peek_rx_packet_info() - peek rx packet info\n"
    if data.count("QDF_STATUS wma_tx_packet(") != 1:
        raise ValueError("Unexpected SM8475 WMA TX function layout")
    if data.count(staged_anchor) == 1:
        if data.count(INCLUDE) != 1:
            raise ValueError("Duplicated WMA bridge include")
        pos = data.index(staged_anchor)
        state = "already-staged"
    elif data.count(ANCHOR) == 1 and INCLUDE not in data:
        if 'include "wma_opairshare_pas_mgmt.h"' in data:
            raise ValueError("Unrecognized WMA bridge include; refusing duplicate")
        pos = data.index(ANCHOR)
        state = "staged" if write else "would-stage"
        if write:
            target.write_text(data.replace(ANCHOR, staged_anchor, 1), encoding="utf-8")
    else:
        raise ValueError("Unexpected SM8475 WMA hook anchor or existing include")
    start = data.index("QDF_STATUS wma_tx_packet(")
    if start > pos or "error:\n" not in data[start:pos]:
        raise ValueError("WMA bridge hook is not after wma_tx_packet")
    return {
        "platform": "oneplus_ace2_sm8475",
        "source": str(target.relative_to(root)),
        "state": state,
        "wma_hook_staged": state in ("staged", "already-staged"),
        "driver_compiled": False,
        "firmware_verified": False,
        "feature_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = port(args.source, args.write)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
