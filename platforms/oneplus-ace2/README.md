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
