#!/usr/bin/env python3
"""Three-way port OPAirDrop WLAN source overlays onto SM8475.

CAUTION: A clean textual merge does not imply the code builds, that WMI is
compatible, or that firmware can send/receive AWDL frames. Never auto-flash.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

INCOMPATIBLE_COMPONENTS = {
    "kernel/driver/dp_be_rx.c",
    "kernel/driver/hal_be_api_mon.h",
}
def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def root_check(root: Path, child: Path) -> Path:
    path = (root / child).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Invalid path escapes source root: " + str(child))
    return path

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--donor", type=Path, default=Path(__file__).resolve().parent.parent)
    p.add_argument("--sm8750-base", type=Path, required=True,
                   help="Unmodified OnePlusOSS SM8750 checkout at the OPAirDrop source-lock SHA")
    p.add_argument("--ace2", type=Path, required=True,
                   help="Unmodified official OnePlusOSS SM8475 checkout")
    p.add_argument("--report-dir", type=Path, required=True)
    p.add_argument("--write", action="store_true",
                   help="Apply clean merges to Ace 2 checkout, keeping a report (default: dry-run)")
    p.add_argument("--safe-only", action="store_true",
                   help="Stage only verified clean/new paths; report and skip all blocked paths")
    p.add_argument("--preview-base-drift", action="store_true",
                   help="Dry-run only: preview textual merges even when recorded SM8750 source hash differs")
    p.add_argument("--include-risky", action="store_true",
                   help="Show/attempt incompatible SM8750 BE datapath files (off by default)")
    args = p.parse_args()
    donor, base, target = (x.resolve() for x in (args.donor, args.sm8750_base, args.ace2))
    if args.safe_only and args.preview_base_drift:
        p.error("--safe-only cannot be combined with --preview-base-drift")
    if args.write and args.preview_base_drift:
        p.error("--preview-base-drift can never be combined with --write")
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((donor / "kernel/source-map.json").read_text(encoding="utf-8"))
    entries = []
    pending = {}  # defer filesystem writes until full eligibility is known
    failures = 0
    for key, value in sorted(mapping.items()):
        if "kernel_path" not in value:
            continue  # host-side test helpers, not source overlays
        rel = Path(value["kernel_path"])
        if key in INCOMPATIBLE_COMPONENTS and not args.include_risky:
            entries.append({"source":key,"target":str(rel),"status":"skipped-architecture-incompatible"})
            continue
        source = root_check(donor, Path(key))
        ancestor = root_check(base, rel)
        destination = root_check(target, rel)
        status = {"source":key,"target":str(rel)}
        if not source.is_file():
            status["status"] = "missing-donor"
            failures += 1
        elif not ancestor.is_file() and not destination.is_file():
            # A genuinely new adapter/header can be copied; it still requires
            # a separate build to prove its dependencies exist on Lithium.
            status["status"] = "new-platform-source"
            status["changed"] = True
            # New code files may contain historical extra empty lines at EOF.
            # Normalize only trailing newlines; never alter non-newline bytes.
            pending[destination] = source.read_bytes().rstrip(b"\n") + b"\n"
        elif not ancestor.is_file():
            status["status"] = "no-common-ancestor"
            failures += 1
        elif not destination.is_file():
            status["status"] = "missing-target"
            failures += 1
        else:
            expected_hash = value.get("sha256")
            expected_ok = (expected_hash == sha256(ancestor.read_bytes())) if expected_hash else None
            status["reference_base_hash_match"] = expected_ok
            if expected_ok is False and not args.preview_base_drift:
                status["status"] = "reference-sha-mismatch"
                failures += 1
            else:
                proc = subprocess.run(["git","merge-file","--stdout",
                     "-L","sm8475-target","-L","sm8750-original","-L","opairdrop-overlay",
                     str(destination),str(ancestor),str(source)],
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                if proc.returncode == 0 and b"<<<<<<<" not in proc.stdout:
                    status["status"] = "base-drift-clean-preview" if expected_ok is False else "clean-merged"
                    status["changed"] = proc.stdout != destination.read_bytes()
                    if status["changed"]:
                        pending[destination] = proc.stdout
                else:
                    status["status"] = "base-drift-conflict" if (expected_ok is False and proc.returncode > 0) else ("conflict" if proc.returncode > 0 else "merge-error")
                    status["merge_exit"] = proc.returncode
                    status["stderr"] = proc.stderr.decode(errors="replace")[:1000]
                    conflict = report_dir / "conflicts" / rel
                    conflict.parent.mkdir(parents=True, exist_ok=True)
                    conflict.write_bytes(proc.stdout)
                if expected_ok is False or proc.returncode != 0 or b"<<<<<<<" in proc.stdout:
                    failures += 1  # One blocker per file; a drifted ancestor is never release-safe.
        entries.append(status)
    if args.write and (not failures or args.safe_only):
        for dest, contents in pending.items():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(contents)
    summary = {"device":"OnePlus Ace 2 SM8475", "applied": args.write,
        "firmware_verified":False,"runtime_usable":False,
        "partial_safe_stage": bool(args.safe_only), "files_written": len(pending) if args.write and (not failures or args.safe_only) else 0,
        "source_mapped_files":len(entries),
        "clean":sum(e["status"] in ("clean-merged","new-platform-source") for e in entries),
        "unresolved":failures,
        "entries":entries}
    (report_dir/"ace2-overlay-merge.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Source overlays:", summary["source_mapped_files"])
    print("Clean source merges:", summary["clean"])
    print("Unresolved:", summary["unresolved"])
    for entry in entries:
        if entry["status"] not in ("clean-merged", "new-platform-source", "skipped-architecture-incompatible"):
            print("BLOCKER", entry["status"], entry["source"], "->", entry["target"])
    print("Report:", report_dir / "ace2-overlay-merge.json")
    if failures and not args.safe_only:
        raise SystemExit("Refused to claim port success: unresolved source merges")
    if failures:
        print("SAFE PARTIAL STAGING: unresolved source merges remain; release is blocked")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
