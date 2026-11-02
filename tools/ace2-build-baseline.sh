#!/usr/bin/env bash
# Reproducible official SM8475 baseline kernel build. No phone operations.
set -euo pipefail
ROOT="${ACE2_BUILD_ROOT:-$PWD/ace2-build}"
PORT="${ACE2_PORT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
REPO_TOOL="${ACE2_REPO_TOOL:-$ROOT/bin/repo}"
mkdir -p "$ROOT/bin" "$ROOT/reports" "$ROOT/output"
# Keep actionable failure diagnostics even if GitHub terminates the compiler.
ace2_diagnostics() {
  local rc=$?
  trap - EXIT
  {
    echo "exit_code=$rc"
    echo "build_root=$ROOT"
    echo "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    df -h "$ROOT" || true
    free -h || true
    find "$ROOT/platform" -name 'Module.symvers' -o -name 'vmlinux' -o -name '*.ko' 2>/dev/null | head -100 || true
  } > "$ROOT/reports/diagnostics.txt" 2>&1
  exit "$rc"
}
trap ace2_diagnostics EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
if [ ! -x "$REPO_TOOL" ]; then
  curl -fsSL --retry 3 https://storage.googleapis.com/git-repo-downloads/repo -o "$REPO_TOOL"
  chmod 755 "$REPO_TOOL"
fi
export PATH="$ROOT/bin:$PATH"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.version GIT_CONFIG_VALUE_0=HTTP/1.1
echo "ACE2_SYNC_BEGIN"
mkdir -p "$ROOT/platform"
cd "$ROOT/platform"
repo init --depth=1 --partial-clone --clone-filter=blob:limit=1m \
  -u https://github.com/OnePlusOSS/kernel_manifest \
  -b oneplus/sm8475 -m oneplus_ace2_v.xml
export ACE2_SYNC_ROOT="$ROOT/platform"
export ACE2_REPORT_ROOT="$ROOT/reports"
bash "$PORT/tools/ace2-sync-kernel.sh"
repo manifest -r -o "$ROOT/reports/source-lock.xml"
echo "ACE2_SOURCE_AUDIT_BEGIN"
python3 "$PORT/tools/ace2-source-audit.py" --source "$ROOT/platform" --json \
  > "$ROOT/reports/source-audit.json"
python3 "$PORT/tools/ace2-source-audit.py" --source "$ROOT/platform"
if [[ "${ACE2_APPLY_MODE_PATCH:-0}" == 1 ]]; then
  echo "ACE2_APPLY_PAS_HOST_QDF_PATCH"
  python3 "$PORT/tools/ace2-port-core.py" --source "$ROOT/platform" \
    --report "$ROOT/reports/pas-host-mode.json"
fi
if [[ "${ACE2_COMPILE_CANDIDATE:-0}" == 1 ]]; then
  if [[ "${ACE2_APPLY_MODE_PATCH:-0}" != 1 ]]; then
    echo "Refuse candidate compilation without PAS host QDF definitions" >&2
    exit 2
  fi
  echo "ACE2_CANDIDATE_STAGE_BEGIN"
  export ACE2_PORT_ROOT="$PORT"
  export ACE2_PLATFORM_ROOT="$ROOT/platform"
  export ACE2_REPORT_ROOT="$ROOT/reports"
  bash "$PORT/tools/ace2-stage-candidate.sh"
  # Kbuild WLAN_CFG_OVERRIDE is explicitly consumed via its $(eval ...) loop.
  # This only requests compiler validation, never device installation.
  export WLAN_CFG_OVERRIDE="CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y"
  echo "ACE2_CANDIDATE_COMPILE_REQUESTED"
fi
echo "ACE2_BASELINE_BUILD_BEGIN"
export ACE2_PLATFORM_ROOT="$ROOT/platform"
export ACE2_REPORT_ROOT="$ROOT/reports"
bash "$PORT/tools/ace2-run-vendor-build.sh"
echo "ACE2_BASELINE_BUILD_END"
# Save only provenance, ELF metadata and checksums, never boot images to artifacts by default.
python3 "$PORT/tools/ace2-artifact-report.py" --root "$ROOT/platform" \
  --out "$ROOT/reports/build-artifacts.json"
if command -v sha256sum >/dev/null; then
  find "$ROOT/platform" -type f -name '*.ko' -print0 \
    | sort -z | xargs -0 -r sha256sum > "$ROOT/reports/module-sha256.txt"
fi
echo "ACE2_BASELINE_SUCCESS"
