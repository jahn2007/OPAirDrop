#!/usr/bin/env bash
# Strict, independently testable official Ace 2 kernel entrypoint. No installs.
set -euo pipefail
: "${ACE2_PLATFORM_ROOT:?Set official manifest checkout}"
: "${ACE2_REPORT_ROOT:?Set reports directory}"
ROOT="$(realpath "$ACE2_PLATFORM_ROOT")"
REPORT="$(realpath -m "$ACE2_REPORT_ROOT")"
mkdir -p "$REPORT"
cd "$ROOT"
# The published OnePlus wrapper sources missing vendorsetup.sh and masks
# prepare_vendor pipe failures. Use the published prepare_vendor directly.
test -f kernel_platform/build/android/prepare_vendor.sh || {
  echo "ACE2_BUILD_ENTRYPOINT_MISSING" >&2
  exit 2
}
export TOPDIR="$ROOT"
export ANDROID_BUILD_TOP="$ROOT"
export CHIPSET_COMPANY=QCOM
export OPLUS_VND_BUILD_PLATFORM=SM8475
export TARGET_BOARD_PLATFORM=taro
export ANDROID_PRODUCT_OUT="$ROOT/out/target/product/taro"
export RECOMPILE_KERNEL=1
export EXTRA_KBUILD_ARGS="--skip abl"
if [[ "${ACE2_COMPILE_CANDIDATE:-0}" == 1 ]]; then
  # The official build/build.sh accepts LTO=full|thin|none.
  # Fast C/API diagnostics are explicitly NON-ABI, NON-RELEASE builds.
  # The final device-matched build MUST restore stock config and ABI checks.
  export LTO="${ACE2_DIAGNOSTIC_LTO:-thin}"
  case "$LTO" in
    thin|full) ;;
    none) echo "ACE2_LTO_NONE_CFI_KMI_INCOMPATIBLE: __cfi_slowpath is required by stock symbol list" >&2; exit 2 ;;
    *) echo "ACE2_UNSUPPORTED_DIAGNOSTIC_LTO: $LTO" >&2; exit 2 ;;
  esac
fi
mkdir -p "$ANDROID_PRODUCT_OUT/tmp" LOGDIR
{
  echo "entrypoint=kernel_platform/build/android/prepare_vendor.sh"
  echo "target=waipio"
  echo "variant=gki"
  echo "candidate=${ACE2_COMPILE_CANDIDATE:-0}"
  echo "lto_mode=${LTO:-stock}"
  echo "diagnostic_candidate_not_abi_verified=true"
  echo "wlan_cfg_override=${WLAN_CFG_OVERRIDE:-none}"
  echo "build_is_installable=false"
} > "$REPORT/build-invocation.txt"
set +e
bash kernel_platform/build/android/prepare_vendor.sh waipio gki \
  2>&1 | tee "$REPORT/kernel-build.log"
rc=${PIPESTATUS[0]}
set -e
if (( rc != 0 )); then
  if grep -Fq 'Symbols missing from ksymtab:' "$REPORT/kernel-build.log" &&
     grep -Fq ' - __cfi_slowpath' "$REPORT/kernel-build.log"; then
    echo "ACE2_KMI_CFI_SYMBOL_MISSING: check LTO/CFI configuration against the official GKI ABI; do not bypass ABI verification" >&2
  fi
  echo "ACE2_BASELINE_BUILD_FAILED exit_code=$rc" >&2
  exit "$rc"
fi
# This entrypoint builds the official GKI/vendor baseline, not the standalone
# qcacld-3.0 module. Requiring a WLAN Kbuild warning here incorrectly fails
# a successful GKI build before the separate WLAN compiler can even run.
# The actual external WLAN build validates WLAN_CFG_OVERRIDE consumption and
# the produced AArch64 wlan.ko in ace2-build-wlan.sh.
# A successful GKI build alone is not a WLAN driver build. Always defer
# artifact/symbol checks to ace2-artifact-report.py before claiming success.
if [[ "${ACE2_COMPILE_CANDIDATE:-0}" == 1 ]]; then
  echo "ACE2_GKI_BUILD_PASSED_WLAN_MODULE_UNVERIFIED"
fi
echo "ACE2_VENDOR_BUILD_EXIT_SUCCESS (module verification still required)"
