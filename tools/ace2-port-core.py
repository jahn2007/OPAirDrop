#!/usr/bin/env python3
"""Fail-closed, repeatable SM8475 PAS host-mode preparation. No device writes.

Prepares only generic QDF modes and an *inactive* feature flag. It does not
claim to attach Wonder to the QCA6490 or to make NDI RAW TX usable.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path("vendor/qcom/opensource/wlan")
FILES = {
    "qca-wifi-host-cmn/qdf/inc/qdf_types.h": [
        ("\tQDF_NAN_DISC_MODE,\n", "\tQDF_NAN_DISC_MODE,\n\tQDF_PASSTHRU_MODE,\n")
    ],
    "qca-wifi-host-cmn/qdf/src/qdf_types.c": [
        ('\tcase QDF_NAN_DISC_MODE:\n\t\treturn "NAN";\n',
         '\tcase QDF_NAN_DISC_MODE:\n\t\treturn "NAN";\n\tcase QDF_PASSTHRU_MODE:\n\t\treturn "PASSTHRU";\n')
    ],
    "qca-wifi-host-cmn/dp/inc/cdp_txrx_cmn_struct.h": [
        ("\twlan_op_mode_ndi,\n", "\twlan_op_mode_ndi,\n\twlan_op_mode_passthru,\n")
    ],
    "qcacld-3.0/Kconfig": [
        ("endif # QCA_CLD_WLAN\n",
         'config OPAIRSHARE_ACE2_PAS_BRIDGE\n\tbool "OPAirDrop Ace 2 PAS/NDI host bridge"\n'
         '\tdefault n\n\thelp\n\t  Off until the Ace 2 NDI firmware backend has been ported.\n\nendif # QCA_CLD_WLAN\n')
    ],
}

def patch_once(path: Path, before: str, after: str, dry: bool):
    original = path.read_text(encoding="utf-8")
    if after in original:
        return "already-applied"
    if original.count(before) != 1:
        raise ValueError(f"unsafe anchor in {path}: expected 1 occurrence of {before!r}, got {original.count(before)}")
    if not dry:
        path.write_text(original.replace(before, after, 1),encoding="utf-8")
    return "would-apply" if dry else "applied"

def main():
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--source",required=True,type=Path)
    arg.add_argument("--dry-run",action="store_true")
    arg.add_argument("--report",type=Path)
    x=arg.parse_args()
    root=x.source.resolve()
    if not (root/"kernel_platform").is_dir():
        raise SystemExit("Expected OnePlusOSS platform checkout; refusing edits")
    tasks=[]
    for rel, replacements in FILES.items():
        p=(root/ROOT/rel).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise SystemExit(f"Missing official Ace 2 source file: {rel}")
        text=p.read_text(encoding="utf-8")
        for before,after in replacements:
            if after not in text and text.count(before)!=1:
                raise SystemExit(f"Refuse partial edits: invalid anchor {rel}: {before!r}")
        tasks.append((p,rel,replacements))
    result=[]
    for p,rel,replacements in tasks:
        for before,after in replacements:
            result.append({"file":str(ROOT/rel),"status":patch_once(p,before,after,x.dry_run)})
    report={"platform":"oneplus_ace2_sm8475","changes":result,
            "feature_enabled":False,"kernel_module_compiled":False,"airdrop_verified":False}
    print(json.dumps(report,indent=2))
    if x.report:
        x.report.parent.mkdir(parents=True,exist_ok=True)
        x.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()
