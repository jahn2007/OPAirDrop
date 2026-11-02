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
repo sync -c --no-tags -j"${ACE2_SYNC_JOBS:-4}" --fail-fast
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
echo "ACE2_BASELINE_BUILD_BEGIN"
# The published OnePlus 15.0 kernel script accepts waipio/gki.
# It builds its own vendor modules and may need a large Linux runner.
export OPLUS_EXTRA_KBUILD_ARGS="${OPLUS_EXTRA_KBUILD_ARGS:-}"
# The vendor build may use this temporary output directory before creating it.
mkdir -p "$ROOT/platform/out/target/product/taro/tmp"
# Preserve the official build's output, including the last successful compiler step.
set +e
bash kernel_platform/oplus/build/oplus_build_kernel.sh waipio gki \
  > >(tee "$ROOT/reports/kernel-build.stdout.log") \
  2> >(tee "$ROOT/reports/kernel-build.stderr.log" >&2)
build_rc=$?
set -e
if (( build_rc != 0 )); then
  echo "ACE2_BASELINE_BUILD_FAILED exit_code=$build_rc" >&2
  exit "$build_rc"
fi
echo "ACE2_BASELINE_BUILD_END"
# Save only provenance, ELF metadata and checksums, never boot images to artifacts by default.
python3 "$PORT/tools/ace2-artifact-report.py" --root "$ROOT/platform" \
  --out "$ROOT/reports/build-artifacts.json"
if command -v sha256sum >/dev/null; then
  find "$ROOT/platform" -type f -name '*.ko' -print0 \
    | sort -z | xargs -0 -r sha256sum > "$ROOT/reports/module-sha256.txt"
fi
echo "ACE2_BASELINE_SUCCESS"
