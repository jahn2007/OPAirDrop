#!/usr/bin/env bash
# Experimental integration candidate: compile diagnostics only, NEVER auto-install.
# Run after official OnePlusOSS Ace 2 manifest sync and ace2-port-core.py.
set -euo pipefail
PORT="$ACE2_PORT_ROOT"
PLATFORM="$ACE2_PLATFORM_ROOT"
REPORT="$ACE2_REPORT_ROOT"
BASE="$PLATFORM/../sm8750-base"
mkdir -p "$REPORT"
test -f "$PORT/kernel/source-map.json"
test -f "$PLATFORM/vendor/qcom/opensource/wlan/qcacld-3.0/core/wma/src/wma_data.c"

# The ancestor is a pinned real OnePlusOSS SM8750 checkout; never use a
# synthetic SHA or silently discard the ancestry mismatch protection.
if [[ ! -d "$BASE/.git" ]]; then
  git clone --filter=blob:none --depth=1 --no-checkout \
    --branch oneplus/sm8750_b_16.0.0_oneplus_13 \
    https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8750.git \
    "$BASE"
  python3 - "$PORT/kernel/source-map.json" > "$REPORT/ace2-sparse-paths" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    data = json.load(handle)
for path in sorted({v["kernel_path"] for v in data.values() if "kernel_path" in v}):
    print("/" + path)
PY
  git -C "$BASE" sparse-checkout init --no-cone
  git -C "$BASE" sparse-checkout set --no-cone --stdin < "$REPORT/ace2-sparse-paths"
  git -C "$BASE" fetch --depth 1 origin d50b305f7da9e14715a25120a4ac7b1a4b8b97c3
  git -C "$BASE" checkout --detach d50b305f7da9e14715a25120a4ac7b1a4b8b97c3
fi
test "$(git -C "$BASE" rev-parse HEAD)" = "d50b305f7da9e14715a25120a4ac7b1a4b8b97c3"

mkdir -p "$REPORT/candidate-preview" "$REPORT/candidate-safe"
# Drift/conflict report intentionally returns nonzero; require the conflict
# files before we may use the strictly scoped native-Lithium resolver.
if python3 "$PORT/tools/ace2-port-overlays.py" \
  --donor "$PORT" --sm8750-base "$BASE" --ace2 "$PLATFORM" \
  --report-dir "$REPORT/candidate-preview" --preview-base-drift; then
  echo "ACE2 candidate preview has no blockers"
else
  test -s "$REPORT/candidate-preview/ace2-overlay-merge.json"
fi
python3 "$PORT/tools/ace2-port-overlays.py" \
  --donor "$PORT" --sm8750-base "$BASE" --ace2 "$PLATFORM" \
  --report-dir "$REPORT/candidate-safe" --write --safe-only

python3 "$PORT/tools/ace2-resolve-core.py" \
  --conflict-root "$REPORT/candidate-preview/conflicts" \
  --target-root "$PLATFORM" \
  --report "$REPORT/candidate-critical.json" --write
python3 "$PORT/tools/ace2-port-wma-hook.py" \
  --source "$PLATFORM" --report "$REPORT/candidate-wma-hook.json" --write
python3 "$PORT/tools/ace2-port-hdd-tx.py" \
  --source "$PLATFORM" --report "$REPORT/candidate-hdd-hook.json" --write

# Assert the disposable candidate really contains the audited hooks and only
# the three scoped resolver outputs before letting the compiler see it.
python3 - "$REPORT" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
with (root / "candidate-critical.json").open(encoding="utf-8") as f:
    critical = json.load(f)
expected = {
    "qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_rx_ops.c",
    "qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c",
    "qcacld-3.0/core/wma/src/wma_dev_if.c",
}
actual = {record["path"].removeprefix("vendor/qcom/opensource/wlan/") for record in critical["records"]}
if actual != expected or not critical["written"]:
    raise SystemExit("Candidate bridge is not the expected three-file Lithium resolution")
for name in ("candidate-wma-hook.json", "candidate-hdd-hook.json"):
    with (root / name).open(encoding="utf-8") as f:
        report = json.load(f)
    if report["state"] not in ("staged", "already-staged"):
        raise SystemExit(f"Unstaged native Ace 2 hook: {name}")
print("ACE2_CANDIDATE_SOURCE_ASSERTIONS_PASS; build status remains unknown")
PY

# The build harness must explicitly enable this guard when requested;
# there is no installer or runtime activation in this stage script.
{
  echo 'candidate_port=staged'
  echo 'compiler_validation=pending'
  echo 'runtime_validation=not_performed'
  echo 'installable=false'
  echo 'required_make_override=CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y'
} > "$REPORT/candidate-build-stage.txt"
echo "ACE2_CANDIDATE_SOURCE_STAGED; NOT a proven WLAN module"
