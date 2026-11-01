#!/usr/bin/env python3
"""Read-only Ace 2 Qualcomm WLAN source inventory (NOT a firmware compatibility test)."""
import argparse
import json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path, help="OnePlusOSS modules/devicetree repository root")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable results")
    args = ap.parse_args()
    config = json.loads((Path(__file__).resolve().parent.parent / "platforms" / "oneplus-ace2" / "platform.json").read_text(encoding="utf-8"))
    source_root = args.source.resolve()
    wlan = source_root / config["wlan_path"]
    checks = []
    for entry in config["source_checks"]:
        path = wlan / entry["path"]
        if not path.is_file():
            checks.append({"path": entry["path"], "present": False, "missing": list(entry["all"])})
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        missing = [needle for needle in entry["all"] if needle not in content]
        checks.append({"path": entry["path"], "present": True, "missing": missing})
    ok = all(x["present"] and not x["missing"] for x in checks)
    result = {"platform": config["id"], "source": str(source_root), "source_audit_pass": ok,
              "firmware_compatibility_proven": False, "checks": checks}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for entry in checks:
            print(("PASS" if entry["present"] and not entry["missing"] else "FAIL") + " " + entry["path"])
            if entry["missing"]:
                print("  missing:", ", ".join(entry["missing"]))
        print("source audit:", "PASS" if ok else "FAIL", "(never implies a working AirDrop port)")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
