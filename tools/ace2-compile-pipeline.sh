#!/usr/bin/env bash
# Coordinate official GKI and external WLAN build without masking either result.
set -euo pipefail
: "${ACE2_PORT_ROOT:?Required source checkout}"
: "${ACE2_PLATFORM_ROOT:?Required official kernel checkout}"
: "${ACE2_REPORT_ROOT:?Required reports path}"
PORT="$ACE2_PORT_ROOT"
ROOT="$ACE2_PLATFORM_ROOT"
REPORT="$ACE2_REPORT_ROOT"
mkdir -p "$REPORT"
candidate="${ACE2_COMPILE_CANDIDATE:-0}"
echo ACE2_GKI_BUILD_BEGIN
gki_rc=0
bash "$PORT/tools/ace2-run-vendor-build.sh" || gki_rc=$?
echo "ACE2_GKI_BUILD_RC=$gki_rc"
if (( gki_rc != 0 )); then
  if [[ "$candidate" != 1 ]] ||
     ! grep -Fq 'Symbols missing from ksymtab:' "$REPORT/kernel-build.log" ||
     ! grep -Fq ' - __cfi_slowpath' "$REPORT/kernel-build.log" ||
     [[ ! -s "$ROOT/kernel_platform/out/msm-waipio-waipio-gki/gki_kernel/common/Module.symvers" ]]; then
    echo "ACE2_GKI_HARD_FAILURE; cannot safely run external WLAN diagnostics" >&2
    exit "$gki_rc"
  fi
  # A real GKI/KMI failure remains a failed build. Only gather extra compiler
  # diagnostics from the already prepared output so this CI run is useful.
  echo "ACE2_GKI_CFI_KMI_FAILURE: continuing WLAN compiler diagnostics; build remains FAILED" >&2
fi
wlan_rc=0
if [[ "$candidate" == 1 ]]; then
  bash "$PORT/tools/ace2-build-wlan.sh" || wlan_rc=$?
  echo "ACE2_WLAN_BUILD_RC=$wlan_rc"
fi
{
  echo "gki_exit=$gki_rc"
  echo "wlan_exit=$wlan_rc"
  echo "candidate=$candidate"
  echo "gki_kmi_passed=$([[ "$gki_rc" == 0 ]] && echo true || echo false)"
  echo "wlan_compiler_passed=$([[ "$candidate" == 1 && "$wlan_rc" == 0 ]] && echo true || echo false)"
  echo "installable=false"
} > "$REPORT/compile-stage-results.txt"
if (( gki_rc != 0 || wlan_rc != 0 )); then
  echo "ACE2_CANDIDATE_DIAGNOSTICS_FAILED gki=$gki_rc wlan=$wlan_rc" >&2
  exit 1
fi
echo "ACE2_BUILD_STAGES_SUCCESS; ABI and firmware runtime still require independent verification"
