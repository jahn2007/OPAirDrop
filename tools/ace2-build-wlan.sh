#!/usr/bin/env bash
# Ace 2 QCACLD external-module compiler probe; never installs to a device.
set -euo pipefail
: "${ACE2_PLATFORM_ROOT:?Official OnePlusOSS checkout required}"
: "${ACE2_REPORT_ROOT:?Writable report directory required}"
ROOT="$(realpath "$ACE2_PLATFORM_ROOT")"
REPORT="$(realpath -m "$ACE2_REPORT_ROOT")"
KSRC="$(realpath -m "${ACE2_KERNEL_SOURCE:-$ROOT/kernel_platform/common}")"
KOUT="$(realpath -m "${ACE2_KERNEL_OUTPUT:-$ROOT/kernel_platform/out/msm-waipio-waipio-gki/gki_kernel/common}")"
WLAN="$ROOT/vendor/qcom/opensource/wlan/qcacld-3.0"
CANDIDATE="${ACE2_COMPILE_CANDIDATE:-0}"
mkdir -p "$REPORT"
fail() { echo "ACE2_WLAN_BUILD_BLOCKED: $*" >&2; exit 2; }
[[ "$CANDIDATE" == 0 || "$CANDIDATE" == 1 ]] || fail "invalid candidate setting"
[[ -f "$WLAN/Makefile" && -f "$WLAN/Kbuild" ]] || fail "official qcacld-3.0 source missing"
[[ -d "$WLAN/cmn" && -d "$ROOT/vendor/qcom/opensource/wlan/fw-api" ]] || fail "WLAN dependency source missing"
[[ -f "$KSRC/Makefile" ]] || fail "kernel source missing"
[[ -f "$KOUT/include/generated/autoconf.h" && -f "$KOUT/include/config/auto.conf" &&
   -s "$KOUT/Module.symvers" ]] || fail "prepared kernel output or Module.symvers missing: $KOUT"
if [[ "$CANDIDATE" == 1 ]]; then
  [[ "${WLAN_CFG_OVERRIDE:-}" == "CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y" ]] ||
    fail "candidate build must explicitly enable PAS feature"
  grep -Fq 'ccflags-$(CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE)' "$WLAN/Kbuild" ||
    fail "candidate PAS Kbuild flag not staged"
fi
CLANG_BIN="${ACE2_CLANG_BIN:-}"
if [[ -z "$CLANG_BIN" ]]; then
  shopt -s nullglob
  clang_matches=("$ROOT"/kernel_platform/prebuilts-master/clang/host/linux-x86/clang-r*/bin/clang)
  (( ${#clang_matches[@]} == 1 )) ||
    fail "select the manifest-pinned clang with ACE2_CLANG_BIN (matches=${#clang_matches[@]})"
  CLANG_BIN="$(dirname "${clang_matches[0]}")"
fi
CLANG_BIN="$(realpath -m "$CLANG_BIN")"
[[ -x "$CLANG_BIN/clang" ]] || fail "pinned Clang missing"
case "$CLANG_BIN/" in
  "$ROOT"/kernel_platform/prebuilts-master/clang/host/linux-x86/*) ;;
  *) fail "refusing Clang outside the official synced source" ;;
esac
EXTRA_SYMBOLS="${ACE2_WLAN_EXTRA_SYMBOLS:-}"
for p in $EXTRA_SYMBOLS; do
  [[ -s "$p" ]] || fail "required external Module.symvers missing: $p"
done
export PATH="$CLANG_BIN:$PATH"
{
  printf 'kernel_source=%s\nkernel_output=%s\nwlan_source=%s\n' "$KSRC" "$KOUT" "$WLAN"
  printf 'compiler=%s/clang\ncandidate=%s\nextra_symbols=%s\ninstallable=false\n' "$CLANG_BIN" "$CANDIDATE" "$EXTRA_SYMBOLS"
} > "$REPORT/wlan-build-invocation.txt"
# Ensure an older .ko can never make a new compile appear successful.
rm -f "$WLAN/wlan.ko"
echo ACE2_WLAN_EXTERNAL_BUILD_BEGIN
set +e
make -C "$KSRC" O="$KOUT" ARCH=arm64 LLVM=1 LLVM_IAS=1 \
  M="$WLAN" modules MODNAME=wlan \
  WLAN_ROOT="$WLAN" WLAN_COMMON_ROOT=cmn WLAN_COMMON_INC="$WLAN/cmn" \
  WLAN_FW_API="$ROOT/vendor/qcom/opensource/wlan/fw-api" WLAN_PROFILE=default \
  CONFIG_QCA_CLD_WLAN=m WLAN_CFG_OVERRIDE="${WLAN_CFG_OVERRIDE:-}" \
  KBUILD_EXTRA_SYMBOLS="$EXTRA_SYMBOLS" \
  2>&1 | tee "$REPORT/wlan-build.log"
rc=${PIPESTATUS[0]}
set -e
if (( rc != 0 )); then
  echo "ACE2_WLAN_COMPILER_FAILED exit_code=$rc" >&2
  exit "$rc"
fi
if [[ "$CANDIDATE" == 1 ]] &&
   ! grep -Fq 'Overriding WLAN config with: CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y' "$REPORT/wlan-build.log"; then
  echo ACE2_WLAN_PAS_FLAG_NOT_CONSUMED >&2
  exit 3
fi
MODULE="$WLAN/wlan.ko"
[[ -s "$MODULE" ]] || fail "no qcacld-3.0 wlan.ko after make"
[[ "$(od -An -tx1 -N4 "$MODULE" | tr -d ' \n')" == 7f454c46 ]] || fail "module is not ELF"
modinfo -F vermagic "$MODULE" > "$REPORT/wlan-vermagic.txt" ||
  fail "modinfo rejected WLAN module"
[[ -s "$REPORT/wlan-vermagic.txt" ]] || fail "empty WLAN vermagic"
readelf -h "$MODULE" > "$REPORT/wlan-elf-header.txt" || fail "invalid WLAN ELF"
sha256sum "$MODULE" > "$REPORT/wlan-sha256.txt"
echo "ACE2_WLAN_EXTERNAL_BUILD_SUCCESS (compile only, not radio/AirDrop validation)"
