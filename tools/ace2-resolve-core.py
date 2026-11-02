#!/usr/bin/env python3
"""Reviewable SM8475-specific resolution of three critical Qualcomm merge conflicts.

Input is a conflict file produced by git merge-file. This tool preserves the
SM8475 code whenever a conflict introduces unsupported SM8750 APIs.
A candidate source merge is NOT buildable or verified until a real kernel build.
"""
import argparse
import json
import re
from pathlib import Path

VENDOR = Path("vendor/qcom/opensource/wlan")
CONFLICT = re.compile(
    r"^<<<<<<< sm8475-target\n(.*?)^=======\n(.*?)^>>>>>>> opairdrop-overlay\n",
    re.M | re.S,
)
DECISIONS = {
    "qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_rx_ops.c":
       ("pas-declaration", "pas-start-response"),
    "qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c":
       ("target",),
    "qcacld-3.0/core/wma/src/wma_dev_if.c":
       ("pas-self-peer", "target", "target", "target"),
}

def resolve(rel: str, text: str) -> tuple[str, list[str]]:
    choices = DECISIONS[rel]
    blocks = list(CONFLICT.finditer(text))
    if len(blocks) != len(choices):
        raise ValueError(f"{rel}: expected {len(choices)} conflicts, found {len(blocks)}")
    decisions = []
    for match, action in reversed(list(zip(blocks, choices))):
        local, donor = match.group(1), match.group(2)
        if action == "target":
            resolved = local
        elif action == "pas-declaration":
            if "opairshare_pas_rx_vdev_event" not in donor:
                raise ValueError("Unexpected PAS event declaration")
            resolved = (
                "#ifdef DRIVER_PASSTHRU_MODE\n"
                "void opairshare_pas_rx_vdev_event(struct wlan_objmgr_psoc *psoc,\n"
                "                                    uint8_t id, bool deleted);\n"
                "#endif\n"
            )
        elif action == "pas-start-response":
            if "start_pending != restart_pending" not in donor:
                raise ValueError("Missing PAS start-response disambiguation")
            # SM8475 retains its native no-brace conditional. A bare brace from
            # the newer donor here would leave the following else unmatched.
            needle = "if (vdev_start_resp.resp_type == WMI_HOST_VDEV_RESTART_RESP_EVENT) {"
            if donor.count(needle) != 1:
                raise ValueError("Unexpected restart-response syntax")
            resolved = donor.replace(needle, needle[:-2], 1)
            if "mode = wlan_vdev_mlme_get_opmode(vdev)" not in resolved:
                raise ValueError("Missing vdev mode lookup")
        elif action == "pas-self-peer":
            if "static bool opairshare_pas_ndi_peer" not in donor:
                raise ValueError("Missing PAS/NDI self-peer helper")
            resolved = donor
        else:
            raise ValueError(f"Unknown conflict decision: {action}")
        text = text[:match.start()] + resolved + text[match.end():]
        decisions.append(action)
    if rel.endswith("target_if_vdev_mgr_rx_ops.c"):
        signature = "struct vdev_response_timer *vdev_rsp;\n"
        # Only the start-response handler needs these locals; find its body.
        begin = text.index("static int target_if_vdev_mgr_start_response_handler(")
        pos = text.index(signature, begin)
        if text.find(signature, pos + len(signature), text.index("if (!scn || !data)", begin)) != -1:
            raise ValueError("Ambiguous vdev timer declaration")
        local = (
            "#ifdef DRIVER_PASSTHRU_MODE\n"
            "    struct wlan_objmgr_vdev *vdev;\n"
            "    enum QDF_OPMODE mode = QDF_MAX_NO_OF_MODE;\n"
            "#endif\n"
        )
        text = text[:pos + len(signature)] + local + text[pos + len(signature):]
        # The preprocessor must guard the lookup as well, not just its uses.
        start = text.index("\tvdev = wlan_objmgr_get_vdev_by_id_from_psoc", begin)
        end = text.index("\tif (vdev_start_resp.resp_type == WMI_HOST_VDEV_RESTART_RESP_EVENT)", start)
        # This includes an existing guarded conditional; keep a single outer guard.
        block = text[start:end]
        if block.count("#ifdef DRIVER_PASSTHRU_MODE") != 1:
            raise ValueError("Unexpected nested PAS response guard layout")
        block = block.replace("#ifdef DRIVER_PASSTHRU_MODE\n", "", 1)
        block = block.replace("#endif\n", "", 1)
        text = text[:start] + "#ifdef DRIVER_PASSTHRU_MODE\n" + block + "#endif\n" + text[end:]
    if CONFLICT.search(text) or "<<<<<<<" in text or ">>>>>>>" in text:
        raise ValueError(f"{rel}: unresolved conflict markers")
    return text, list(reversed(decisions))

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--conflict-root", type=Path, required=True)
    p.add_argument("--target-root", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--write", action="store_true", help="Write candidate source files (not release-ready)")
    args = p.parse_args()
    confroot = args.conflict_root.resolve()
    target = args.target_root.resolve()
    if not (target / VENDOR / "qcacld-3.0" / "Kbuild").is_file():
        raise SystemExit("This is not an OnePlusOSS WLAN platform checkout")
    staged = {}
    records = []
    for rel in DECISIONS:
        f = (confroot / VENDOR / rel).resolve()
        dst = (target / VENDOR / rel).resolve()
        if not f.is_relative_to(confroot) or not dst.is_relative_to(target):
            raise SystemExit("Path escaped trusted tree")
        if not f.is_file() or not dst.is_file():
            raise SystemExit(f"Missing candidate or source: {rel}")
        data, resolved = resolve(rel, f.read_text(encoding="utf-8"))
        if rel == "qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c":
            # This older SM8475 driver has a different HDD/adapter layout.
            # A whole-file SM8750 3-way merge introduces donor PAS TX and
            # newer deflink-only fields that the native Lithium WLAN lacks.
            # Retain the native vendor TX implementation and stage only
            # the minimal, guarded PAS dispatch in ace2-port-hdd-tx.py.
            # We still parse the conflict above to detect upstream drift.
            native = dst.read_text(encoding="utf-8")
            if native.count("netdev_tx_t hdd_hard_start_xmit(") != 1:
                raise ValueError("Missing unique native SM8475 HDD TX entry")
            if "hdd_hard_start_xmit_passthru(" in native or (
                "opairshare_pas_mgmt_xmit(" in native
            ):
                raise ValueError("Native SM8475 source unexpectedly has PAS TX")
            data = native
            resolved = ["native-sm8475-hdd-preserved"]
        staged[dst] = data
        records.append({"path":str(VENDOR/rel), "resolved_conflicts":resolved})
    if args.write:
        for path, content in staged.items():
            path.write_text(content, encoding="utf-8")
    report = {
        "device":"OnePlus Ace 2 SM8475",
        "status":"candidate-source-merge-only",
        "written":args.write,
        "compile_tested":False,
        "airdrop_verified":False,
        "records":records,
        "requires_manual_review":True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
