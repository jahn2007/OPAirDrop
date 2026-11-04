#!/usr/bin/env python3
"""Summarize SM8475 baseline .ko artifacts. Reports compilation, NOT AirDrop support."""
import argparse
import json
import pathlib
import subprocess

def read_modinfo(module):
    if not _has_tool("modinfo"):
        return {}
    data = {}
    for key in ("name", "vermagic", "depends", "srcversion", "signer"):
        p = subprocess.run(["modinfo", "-F", key, str(module)], capture_output=True, text=True)
        if p.returncode == 0:
            data[key] = p.stdout.strip()
    return data

def _has_tool(name):
    import shutil
    return bool(shutil.which(name))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if not (root / "kernel_platform").is_dir():
        raise SystemExit("Not a OnePlusOSS kernel checkout")
    mods = []
    for module in sorted(root.rglob("*.ko")):
        if len(mods) >= 500:
            raise SystemExit("Unexpected excessive .ko candidates")
        import hashlib
        dig = hashlib.sha256()
        with module.open("rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                dig.update(block)
        mods.append({"path": str(module.relative_to(root)), "bytes":module.stat().st_size,
                     "sha256":dig.hexdigest(), "modinfo":read_modinfo(module)})
    # The external-module stage writes exactly this output. A different
    # wlan.ko elsewhere in GKI/vendor outputs is not evidence of the patched
    # Lithium QCACLD module compiling.
    qcacld_rel = pathlib.Path("vendor/qcom/opensource/wlan/qcacld-3.0/wlan.ko")
    qcacld = root / qcacld_rel
    is_elf = qcacld.is_file() and qcacld.stat().st_size > 4
    if is_elf:
        with qcacld.open("rb") as f:
            is_elf = f.read(4) == b"\x7fELF"
    wlan = [m for m in mods if m["path"] == qcacld_rel.as_posix()] if is_elf else []
    result = {"platform":"oneplus_ace2_sm8475","modules_found":len(mods),
              "qcacld_wlan_found":bool(wlan),
              "firmware_awdl_verified":False,"airdrop_working":False,"modules":mods}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Reported", len(mods), "modules to", args.out)
    if not mods:
        raise SystemExit("No kernel modules found; build output is incomplete")
    # Official QCACLD Kbuild MODNAME=wlan. An unrelated WLAN platform helper
    # artifact cannot establish that the modified driver compiled.
    if not wlan:
        raise SystemExit("No qcacld-3.0 wlan.ko artifact found; candidate module not built")
if __name__=="__main__":
    main()
