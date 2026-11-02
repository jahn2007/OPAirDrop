# OnePlus Ace 2 (SM8475/QCA6490) platform port

## Goal

Native bidirectional **AirDrop** interoperability with Apple devices through existing OShare + Mosey + Wonder. This is **not** achieved merely by spoofing the device model or adding a share target. Preserve existing SM8750 behavior.

## Current state

**SOURCE AUDIT ONLY — NOT A WORKING PORT.** The QCA6490 host driver exposes Monitor RX, NDI management, WMI management TX with explicit frame-type parameters, and MAC RX filter command construction. None proves that the shipping firmware accepts arbitrary AWDL QoS DATA in an NDI vdev, nor that its MAC will ACK as needed.

The hardware must remain untouched until the user chooses to perform device tests. Do not mark any build working until both directions transfer and SHA256-check real files.

## Initial strategy

1. Use exact vendor kernel source ref from `platform.json`, pin source commits and build with the matching 5.10 ABI. Never reuse peach-v2/6.6 .ko files.
2. Reuse `kernel/wonder`, `mosey`, `oshare`, `native`; adapt only their version-specific boundaries.
3. Introduce a PAS-host API mapped to an NDI-firmware vdev, including CREATE/START/STOP/DELETE, self-peer/map and proper event ownership. Do not bypass regulatory channel checks.
4. Route AWDL Probe/Action and QoS DATA via the existing WMI management-TX framework, explicitly describing data frame type; handle completions, callbacks and orderly shutdown.
5. Deliver radiotap + full IEEE 802.11 Monitor RX to Wonder; apply and validate RX MAC-filter status. Keep native REO/BA and parallel STA out of the first milestone.
6. Support single-channel AWDL-exclusive mode while STA may disconnect; restore original WLAN state on exit or failure.
7. Reconcile APK/FFI/Binder versions, APatch boot lifecycle, and OShare hooks on ColorOS 15.
8. Build artifacts on GitHub Actions. Explicitly distinguish compile success from firmware compatibility and end-to-end device acceptance.

## Source audit

The JSON manifest lists required baseline paths and symbols. With the OnePlusOSS platform tree already checked out, run:

```bash
python3 tools/ace2-source-audit.py --source /path/to/android_kernel_modules_and_devicetree_oneplus_sm8475
```

All listed checks are **source presence checks**, not compiled-feature or firmware behavior proofs.

## Acceptance gates

- **P0** Official baseline fully builds with exact device KMI / symbols; stock WLAN load/unload recovery plan prepared.
- **P1** Modified driver compiles and has validated PAS/NDI state transition semantics.
- **P2** AirDrop discovery plus small-file sending and receiving verified on real Apple device; SHA256 matches. (Requires future user-approved testing.)
- **P3** Failure recovery and repeat start/stop; then optimize performance and coexistence.

## External constraints

The repo currently packages archived driver and Mosey binaries; a release ZIP is not a reproducible kernel build by itself. The platform port must not silently substitute the existing SM8750 binaries or claim functionality based only on host-side WMI APIs.

## Implementation update — 2026-11-02

The following files on this branch now generate actual changes to the official
SM8475 vendor source, rather than merely documenting an implementation route:

- `tools/ace2-port-core.py` inserts the PAS host enum entries into QDF,
  adds the disabled-by-default `CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE` Kconfig
  symbol and Kbuild define, and installs the validated classifier header.
- `kernel/ace2/wlan_hdd_opairshare_frame.h` classifies probe request,
  Action and Apple-encapsulated QoS DATA frames. This is wired into
  `kernel/driver/wma_opairshare_pas_mgmt.h` only when
  `OPAIRSHARE_ACE2_PAS_BRIDGE` is defined. Host C tests exercise the layout.
- `tools/ace2-port-overlays.py` stages only the exact-hash verified parts
  of the SM8750 driver overlays, transactionally, without copying BE-only
  sources. It reports blocked files and produces a standalone source patch.
- `tools/ace2-resolve-core.py` produces a separate **candidate** patch for
  the older SM8475 `target_if_vdev_mgr_rx_ops.c`, `wlan_hdd_tx_rx.c` and
  `wma_dev_if.c`. It preserves the older RPS path and excludes new-generation
  code where it cannot be safely transplanted.
- GitHub Actions `ace2-kernel.yml` validates the C frame classifier,
  stages source changes and exports a patch. Full official Linux 5.10 vendor
  kernel build is an additional gated job.
- GitHub Actions `ace2-merge-preview.yml` exports the strict partial patch
  and separately the candidate conflict-resolution patch, together with the
  complete blocker list.

**The platform port is still incomplete.** A patch generation green check is
not a kernel compilation result. The vendor QCA6490 driver has not yet been
proven to create, start, and delete the required Wonder-bound PAS/NDI session,
nor to transmit QoS DATA over WMI RAW, nor to deliver the receive path and ACKs.
No Ace 2 installer or Release is authorized by these steps.

Current blockers are the remaining QCA6490 WMA/HDD/DP source differences,
missing target paths, Linux 5.10 symbol/ABI reconciliation, full vendor kernel
compilation, and (when the user authorizes hardware testing) firmware behavior.

## Experimental native TX integration — 2026-11-02 continuation

- `tools/ace2-port-wma-hook.py` adds a tightly anchored, idempotent feature-guarded include to the official SM8475 `wma_data.c`, after `wma_tx_packet()`. Merely staging a donor WMI header previously left it disconnected from compilation.
- `tools/ace2-port-hdd-tx.py` stages a distinct `QDF_PASSTHRU_MODE` dispatch in the native `hdd_hard_start_xmit()`. Ordinary STA TX is left unchanged; PAS radiotap frames never silently fall into the Ethernet data path. The WMA TX bridge's BUSY return preserves skb ownership.
- `tools/ace2-port-core.py` provides `DRIVER_PASSTHRU_MODE` and `OPAIRSHARE_ACE2_PAS_BRIDGE` C defines **only** for the opt-in `CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE` build, default disabled.
- The donor WMA bridge normalizes Retry/Power-Management/More-Data bits **only for its type/subtype decisions** under the Ace 2 guard, preserving the actual radiotap/802.11 skb.
- The separate experimental `tools/ace2-stage-candidate.sh` stages strict verified overlays and the three previously reviewed conflict candidates in a synced official 5.10 kernel checkout. It installs both native TX hooks after resolving the appropriate files. Unlike preview mode it is a compiler candidate, **not a validated driver**.
- `.github/workflows/ace2-kernel.yml` now exposes manually dispatched `full_kernel=true, candidate_port=true`. For automated one-off diagnostics, commits tagged `[ace2-candidate-kernel]` also trigger the candidate build, while normal pushes continue to run the lightweight source tests. The candidate uses `WLAN_CFG_OVERRIDE=CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y` and retains compiler diagnostics. The exact effectiveness of this override and all vendor cross-generation APIs must be proven by the resulting build.
- `ace2-merge-preview.yml` stages the WMA inclusion and HDD TX dispatch in its artifact, plus reports of remaining conflicting source files; it still does not compile a kernel module.

**This is not a working or installable AirDrop release.** PAS vdev lifecycle, Wonder provider, WMI raw data completion, monitor receive path and firmware ACK behavior remain blockers. Never force-load an experimental WLAN binary into PHK110.
