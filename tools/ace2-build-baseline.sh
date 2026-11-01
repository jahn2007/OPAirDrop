#!/usr/bin/env bash
# Reproducible official SM8475 baseline kernel build. No phone operations.
set -euo pipefail
ROOT="${ACE2_BUILD_ROOT:-$PWD/ace2-build}"
PORT="${ACE2_PORT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
REPO_TOOL="${ACE2_REPO_TOOL:-$ROOT/bin/repo}"
mkdir -p "$ROOT/bin" "$ROOT/reports" "$ROOT/output"
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
echo "ACE2_BASELINE_BUILD_BEGIN"
# The published OnePlus 15.0 kernel script accepts waipio/gki.
# It builds its own vendor modules and may need a large Linux runner.
export OPLUS_EXTRA_KBUILD_ARGS="${OPLUS_EXTRA_KBUILD_ARGS:-}"
bash kernel_platform/oplus/build/oplus_build_kernel.sh waipio gki
echo "ACE2_BASELINE_BUILD_END"
# Save only provenance, ELF metadata and checksums, never boot images to artifacts by default.
python3 "$PORT/tools/ace2-artifact-report.py" --root "$ROOT/platform" \
  --out "$ROOT/reports/build-artifacts.json"
if command -v sha256sum >/dev/null; then
  find "$ROOT/platform" -type f -name '*.ko' -print0 \
    | sort -z | xargs -0 -r sha256sum > "$ROOT/reports/module-sha256.txt"
fi
echo "ACE2_BASELINE_SUCCESS"
