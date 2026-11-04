#!/usr/bin/env bash
# Recover only manifest-pinned CodeLinaro compiler worktree checkout failures.
# This operates in a disposable CI checkout; no device writes or toolchain swaps.
set -euo pipefail
: "${ACE2_SYNC_ROOT:?Set the official repo checkout path}"
: "${ACE2_REPORT_ROOT:?Set a writable diagnostic report directory}"
cd "$ACE2_SYNC_ROOT"
mkdir -p "$ACE2_REPORT_ROOT"

# Names and paths are taken from OnePlusOSS/kernel_manifest oneplus_ace2_v.xml.
declare -A manifest_project=(
  ["kernel_platform/prebuilts-master/clang/host/linux-x86"]="kernelplatform/prebuilts-master/clang/host/linux-x86"
  ["kernel_platform/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8"]="kernelplatform/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8"
)
declare -A manifest_sha=(
  ["kernel_platform/prebuilts-master/clang/host/linux-x86"]="0fc3d01a780023469b7acc18c56a9cf5099a6d6c"
  ["kernel_platform/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8"]="c9f87ae369034b4942536a1c5bd62e4cd1d828e3"
)
paths=(
  "kernel_platform/prebuilts-master/clang/host/linux-x86"
  "kernel_platform/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8"
)
jobs="${ACE2_SYNC_JOBS:-2}"
if [[ ! "$jobs" =~ ^[1-8]$ ]]; then
  echo "Refusing invalid ACE2_SYNC_JOBS: $jobs" >&2
  exit 2
fi

sync_report() {
  local label="$1" path
  {
    echo "phase=$label"
    date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
    df -h . || true
    df -ih . || true
    for path in "${paths[@]}"; do
      echo "project=${manifest_project[$path]}"
      du -sh "$path" 2>/dev/null || true
      if [[ -e "$path" ]]; then
        git -C "$path" status --short --branch 2>&1 | head -20 || true
      fi
    done
  } > "$ACE2_REPORT_ROOT/repo-sync-diagnostics-$label.txt" 2>&1
}
sync_report preflight
ok=0
# A failed project recovery can uncover another broken compiler worktree.
# Bound retries to three full passes, each with at most two serial recoveries.
for round in 1 2 3; do
  echo "ACE2_SYNC_ALL_ATTEMPT_$round"
  log="$ACE2_REPORT_ROOT/repo-sync-all-$round.log"
  if repo sync -c --no-tags --retry-fetches=3 -j"$jobs" --fail-fast \
      2>&1 | tee "$log"; then
    ok=1
    break
  fi

  # Keep retry scope limited to the manifest's exact pinned prebuilt projects.
  failed=""
  for path in "${paths[@]}"; do
    if grep -Fq "Cannot initialize work tree for ${manifest_project[$path]}" "$log"; then
      if [[ -n "$failed" ]]; then
        echo "ACE2_SYNC_MULTIPLE_FAILURES: manual investigation required" >&2
        sync_report "all-$round"
        exit 1
      fi
      failed="$path"
    fi
  done
  if [[ -z "$failed" ]]; then
    echo "ACE2_SYNC_OTHER_FAILURE: not a known pinned compiler worktree" >&2
    sync_report "all-$round"
    exit 1
  fi
  sync_report "all-$round"
  echo "ACE2_SYNC_PINNED_COMPILER_RECOVERY project=${manifest_project[$failed]}"
  recovered=0
  for attempt in 1 2; do
    echo "ACE2_SYNC_COMPILER_ATTEMPT_$round-$attempt"
    if repo sync -c --no-tags --retry-fetches=3 -j1 --fail-fast "$failed" \
        2>&1 | tee "$ACE2_REPORT_ROOT/repo-sync-compiler-$round-$attempt.log"; then
      recovered=1
      break
    fi
    sync_report "compiler-$round-$attempt"
  done
  if (( recovered == 0 )); then
    echo 'ACE2_SYNC_COMPILER_RECOVERY_FAILED' >&2
    exit 1
  fi
done
if (( ok == 0 )); then
  echo 'ACE2_SYNC_ALL_RETRIES_EXHAUSTED' >&2
  sync_report exhausted
  exit 1
fi

# Never accept an unrelated compiler version or a truncated worktree.
for path in "${paths[@]}"; do
  expected="${manifest_sha[$path]}"
  if ! actual="$(git -C "$path" rev-parse HEAD)"; then
    echo "ACE2_SYNC_COMPILER_MISSING: $path" >&2
    sync_report verify
    exit 1
  fi
  if [[ "$actual" != "$expected" ]]; then
    echo "ACE2_SYNC_COMPILER_PIN_MISMATCH: $path expected=$expected actual=$actual" >&2
    sync_report verify
    exit 1
  fi
  echo "ACE2_SYNC_PINNED_COMPILER_OK: $path $actual"
done
echo 'ACE2_SYNC_SUCCESS'
sync_report complete
