#!/usr/bin/env bash
# Recover only the known CodeLinaro clang worktree checkout failure in a disposable
# official Ace 2 repo manifest checkout; never substitute an unpinned compiler.
set -euo pipefail
: "${ACE2_SYNC_ROOT:?Set the official repo checkout path}"
: "${ACE2_REPORT_ROOT:?Set a writable diagnostic report directory}"
cd "$ACE2_SYNC_ROOT"
mkdir -p "$ACE2_REPORT_ROOT"
toolchain='kernel_platform/prebuilts-master/clang/host/linux-x86'
project='kernelplatform/prebuilts-master/clang/host/linux-x86'
pinned='0fc3d01a780023469b7acc18c56a9cf5099a6d6c'
jobs="${ACE2_SYNC_JOBS:-2}"
if [[ ! "$jobs" =~ ^[1-8]$ ]]; then
  echo "Refusing invalid ACE2_SYNC_JOBS: $jobs" >&2
  exit 2
fi
sync_report() {
  {
    date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
    df -h . || true
    df -ih . || true
    du -sh "$toolchain" ".repo/project-objects/$project.git" \
      ".repo/projects/$toolchain.git" 2>/dev/null || true
    if [[ -e "$toolchain" ]]; then
      git -C "$toolchain" status --short --branch 2>&1 | head -30 || true
    fi
  } > "$ACE2_REPORT_ROOT/repo-sync-diagnostics.txt" 2>&1
}
sync_report
echo 'ACE2_SYNC_ALL_ATTEMPT_1'
if repo sync -c --no-tags --retry-fetches=3 -j"$jobs" --fail-fast \
    2>&1 | tee "$ACE2_REPORT_ROOT/repo-sync-initial.log"; then
  echo 'ACE2_SYNC_ALL_INITIAL_SUCCESS'
else
  # A transient large checkout failure needs a project-scoped serial recovery.
  # Do not use --force-checkout or silently replace/rebase the official source.
  if ! grep -Fq "Cannot initialize work tree for $project" \
       "$ACE2_REPORT_ROOT/repo-sync-initial.log"; then
    echo 'ACE2_SYNC_OTHER_FAILURE: no unsafe generic recovery attempted' >&2
    sync_report
    exit 1
  fi
  echo 'ACE2_SYNC_CLANG_WORKTREE_RECOVERY'
  sync_report
  ok=0
  for attempt in 1 2; do
    echo "ACE2_SYNC_CLANG_ATTEMPT_$attempt"
    if repo sync -c --no-tags --retry-fetches=3 -j1 --fail-fast "$toolchain" \
        2>&1 | tee "$ACE2_REPORT_ROOT/repo-sync-clang-$attempt.log"; then
      ok=1
      break
    fi
    sync_report
  done
  if (( ok == 0 )); then
    echo 'ACE2_SYNC_CLANG_RECOVERY_FAILED' >&2
    sync_report
    exit 1
  fi
  echo 'ACE2_SYNC_ALL_RESUME'
  if ! repo sync -c --no-tags --retry-fetches=3 -j"$jobs" --fail-fast \
      2>&1 | tee "$ACE2_REPORT_ROOT/repo-sync-resumed.log"; then
    echo 'ACE2_SYNC_RESUME_FAILED' >&2
    sync_report
    exit 1
  fi
fi
# The manifest pins this exact CodeLinaro commit. Refuse unrelated versions.
actual="$(git -C "$toolchain" rev-parse HEAD)"
if [[ "$actual" != "$pinned" ]]; then
  echo "ACE2_SYNC_CLANG_PIN_MISMATCH: expected=$pinned actual=$actual" >&2
  sync_report
  exit 1
fi
echo "ACE2_SYNC_SUCCESS clang=$actual"
sync_report
