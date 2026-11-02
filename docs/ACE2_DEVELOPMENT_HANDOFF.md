# OnePlus Ace 2 ↔ Apple AirDrop: FULL PROJECT HANDOFF / CONVERSATION CONTEXT

> **IMPORTANT FOR A NEW CHAT / CODING AGENT:** This is a durable reconstruction of the user's complete relevant intentions, the technical analysis, repository changes, tests, constraints, actual state and next actions from the development conversation through **2026-11-02 (UTC+8)**. It is the primary handoff document for [PR #1](https://github.com/jahn2007/OPAirDrop/pull/1). **Read this document AND inspect live PR diffs and Actions before modifying anything.** It is not a claim of functional AirDrop support.
>
> **Status at handoff:** **WIP, NOT INSTALLABLE, NOT TESTED ON ACE 2, NOT AN AIRDROP RELEASE.** GitHub Actions source audit and candidate-patch generation passed. No confirmed full kernel/WLAN build, no firmware behavior confirmation, no bidirectional AirDrop transfer.

## 0. Resume in a new conversation — don't require this conversation

A user may open a completely new conversation and provide only:

> 继续完成 https://github.com/jahn2007/OPAirDrop/pull/1 的一加 Ace 2 AirDrop 移植。请先完整阅读 PR 描述、所有开发上下文和 docs/ACE2_DEVELOPMENT_HANDOFF.md，检查分支最新代码和 GitHub Actions，再直接修改 PR 开发分支继续实现，直至得到可安装、可实际双向互传 AirDrop 的版本。不要让我在电脑安装开发环境，构建交给 GitHub Actions。现阶段未经我同意不要在手机上进行测试；不要把仅可编译或未测试的版本说成可用成品。

The developer/assistant should **continue coding rather than simply drafting a proposal**. No need to ask the user again about device model, OS, root solution, kernel generation, repo name, target functionality, Wi-Fi disconnect tolerance, release pipeline, or the choice of architecture. **Prioritize functional outcome over preserving any specific implementation plan**. Be transparent when firmware/ABI verification requires a test that the user has not authorized.

## 1. Repositories, branches, original upstream, task objective

| Meaning | Value |
| --- | --- |
| User's fork / only modification destination | https://github.com/jahn2007/OPAirDrop |
| PR under development | https://github.com/jahn2007/OPAirDrop/pull/1 |
| PR state | Open **Draft PR**; do not merge before completion |
| Head branch | `feat/oneplus-ace2-sm8475` |
| Base branch | `main` |
| Latest reviewed head SHA BEFORE this handoff was added | `cd3bc524411580f082b7c0d79a0d14561dc8cf69` (will change when this file is committed) |
| Original project | TimelessU/OPAirDrop lineage, currently SM8750/OnePlus13 PJZ110-oriented |
| Existing platform | OnePlus 13, SM8750/sun/peach-v2, kernel 6.6, Android SDK 37 |
| New target | **OnePlus Ace 2, PHK110, SM8475, QCA6490, kernel 5.10, ColorOS 15** |
| Final product | Genuine AirDrop-compatible, **two-way discovery and FILE TRANSFER** with stock iPhone/macOS sharing UI |
| Preferred integration | Native-feeling **ColorOS OShare** share-sheet entry with discovered Apple devices, real progress, accepting/declining files |
| Delivery | Finished binary APK/root module as needed; artifacts compiled and released by **GitHub Actions / GitHub Releases**, with auditable source and signatures. Nothing required on the user's PC except existing Git. |
| Explicit non-goals for first working version | Concurrent normal Wi-Fi connection, high throughput, data aggregation, MLO/BE feature parity, GPU-related features |

The user was explicit repeatedly:
1. They initially believed this project merely added an interface to ColorOS and impersonated Apple. After clarification, they asked whether AWDL can be simulated entirely in software and requested viability analysis.
2. They chose **plan B**, a minimal Qualcomm RAW send/receive bridge **reusing Mosey, Wonder and OShare**, rather than reimplementing AWDL.
3. They then broadened the mandate: **“选择方案B。我的目标是实现此功能，具体路径不做过多要求”**, **“直接完整修改项目，目标是达到可用”**, **“继续实现”**. Thus a better validated route MAY replace plan B.
4. The user now wants **ALL RELEVANT CONTEXT SAVED TO PR** so that providing the PR URL in a new chat permits immediate resumption.

Do not substitute cloud relays, QR codes, manual IP file transfer, fake device icons, or a successful packaging job for genuine native AirDrop interoperability. Do not imply that the Android device must globally pose as an authenticated Apple device; AWDL transport and higher-layer AirDrop discovery/service compatibility are distinct.

## 2. User environment / previously observed phone capabilities

Only project-relevant context is preserved (no passwords, identifiers or unrelated personal information).

- Phone: **OnePlus Ace 2**, Chinese mainland device model **PHK110**.
- ROM: **China ColorOS 15**, NOT the overseas OxygenOS build. Android SDK **35**.
- SoC reported as **SM8475**; WLAN radio **Qualcomm QCA6490** (phy0).
- Kernel reported from phone: **`5.10.226-android12-9-o-g8bd2963f3e80`** on aarch64. Kernel branch name or published 15.0 source does **not** by itself prove matching full stock image/config/KMI/Module.symvers.
- Root: **APatch**; formerly observed `uid=0(root)`, SELinux **Enforcing**, context `u:r:magisk:s0`, root-managed module directory `/data/adb/modules`.
- Interfaces seen: `wlan0`, `wlan1`, `p2p0`, `wifi-aware0`. `iw` phy capabilities include **managed/AP/P2P**, and monitor capability observed/tested.
- Prior non-Apple **monitor receive** test on phone successfully created a monitor interface `awdlmon0` and brought it up on existing 5 GHz ch36 while STA used `wlan0`. Existing STA Wi-Fi disconnected as monitor-mode test proceeded; it did not automatically reconnect after the process exited. **This proves neither AWDL transmit injection nor iPhone compatibility nor NDI + WMI RAW TX success.**
- Previous test details (historical only): Android shell root command ran read-only and passive monitor tests; logs were placed under `/sdcard/Download/ace2_monitor_probe_*.txt`, `/sdcard/Download/ace2_monitor_rx_*.txt` (paths were on user's phone, **not present in repository**). First script execution path `/storage/emulated/0/Documents/test.sh`.
- User's explicit tolerance: **“我可以接受在airdrop时断开wifi网络”**. AWDL-exclusive STA-disconnected v1 is authorized as a functional compromise. MUST restore Wi-Fi connection/state as safely as possible after exit/timeout/error.
- **Very important:** During this porting session user directed **NO further tests on their phone now**. Reuse historic observations and public sources, GitHub Actions compile or source audits only. Do not ask user to install/run probes or flash anything without a new explicit permission.
- User prefers direct implementation, complete ready software via GitHub builds, no extensive confirmation cycles, and clear differentiation between working artifact and theoretical engineering feasibility.

## 3. Core technical understanding; why this is nontrivial

AirDrop involves higher-level discovery/security/service/file exchange over a compatible direct radio link. The Apple Wireless Direct Link **AWDL** layer uses specific 802.11 discovery/action/data formats, channel coordination and interface behavior. A virtual `awdl0`/TUN/mac80211 netdev is not itself a radio transmitter: an ordinary Android `wlan0` packet path normally converts Ethernet frames for STA/AP use. Application-level spoofing does not yield direct link compatibility. A fully userspace AWDL protocol can exist (e.g. the public **Open Wireless Link / OWL** project), but still requires raw IEEE 802.11 TX/RX/channel/ack hardware support.

**Selected implementation route, allowed to change when justified:**
```
ColorOS share menu / OShare / LSPosed bridge (UI / discovery / progress)
     ↕
Mosey Java provider / service and native daemon FFI
     ↕
Wonder virtual soft-MAC / Linux mac80211
     ↕ wondertap_ops / vendor provider
QCA6490-specific host PAS adapted via firmware NDI vdev
     ↕
WMI MGMT TX frame_type=DATA (full 802.11 RAW), monitor RX incl radiotap,
peer self-map, RX MAC filter and correct 802.11 ACK behavior
     ↕
Stock QCA6490 proprietary firmware / physical 802.11 radio
     ↕
iPhone or Mac with native AirDrop
```

- The original **SM8750** OPAirDrop implementation records that trying firmware-native `PAS` (`WMI_VDEV_TYPE_PAS=9`) triggered a firmware assert; workaround was **host PAS mapped to firmware NDI (type 7)**, a self peer, peer-map/AST, WMI raw management pipeline carrying 802.11 Action/Probe and QoS DATA, monitor RX, and RX MAC address filtering. Its high-throughput native REO/RX, ADDBA, aggregation and STA coexistence are **optional**, and some are BE-generation-specific. See `docs/SM8750-AWDL.md` and `docs/TECHNICAL.md`.
- Do NOT naively transplant SM8750 `peach-v2` 6.6 `.ko` onto SM8475 Linux 5.10. Linux KMI/exported CRC and Qualcomm Lithium vs BE data paths materially differ.
- Ace 2 publicly released **QCA6490/LITHIUM** host code contains WMI TX management parameter setters, `CONFIG_QCACLD_FEATURE_NAN` and monitor RX paths; **that is only HOST SOURCE SUPPORT, not proof that OEM firmware accepts WMI RAW QoS DATA from NDI or performs hardware 802.11 ACK**.
- Especially important source finding: SM8475 `qcacld-3.0/core/wma/src/wma_data.c` `wma_tx_packet()` for ordinary `TXRX_FRM_802_11_DATA` **decapsulates full 802.11 into 802.3** and forwards to `cdp_tx_non_std()`. That ordinary path CANNOT simply stand in for AWDL full RAW QoS frames. The existing OPAirDrop WMI management-TX route with explicit `tx_param.frame_type=WMA_TX_SEND_DATA_TYPE` is the more viable starting point, subject to firmware acceptance.
- 802.11 unicast ACK timing normally belongs to firmware/hardware, not arbitrary Android userspace. Receiver must accept address/peer context for ACK to happen. RX MAC filter may be critical.
- `qcacld-3.0/core/hdd/src/wlan_hdd_main.c` monitor ops on 15.0 branch have `ndo_open/stop/get_stats` and **no `ndo_start_xmit`**; monitor interface creation DOES NOT prove raw injection.
- Some SM8475 `dp_rx.c` paths have `DP_RX_DROP_RAW_FRM`; verify actual enabled config and full 802.11/radiotap delivery.
- No proof that Google's official Quick Share–AirDrop interoperability can simply be enabled on this older device. Reported official OnePlus model was OnePlus 15, NOT Ace 2; another route can be investigated but **do not assume undocumented universal compatibility**.

## 4. Authoritative public source and exact code locations

Official OnePlusOSS source manifest:
- [`oneplus_ace2_v.xml`, branch `oneplus/sm8475`](https://github.com/OnePlusOSS/kernel_manifest/blob/oneplus/sm8475/oneplus_ace2_v.xml)
- Source tree: [`android_kernel_modules_and_devicetree_oneplus_sm8475`, branch `oneplus/sm8475_v_15.0.0_ace_2`](https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8475/tree/oneplus/sm8475_v_15.0.0_ace_2)
- Additional manifest projects: `android_kernel_common_oneplus_sm8475`, `android_kernel_oneplus_sm8475` on same branch; external prebuilts/toolchain from CodeLinaro with project-specific SHAs.
- Kernel build verified *source entrypoint*: `kernel_platform/oplus/build/oplus_build_kernel.sh waipio gki`, calls the official vendor builder; **not yet confirmed to complete on GitHub runner**.
- Vendor WLAN source prefix: `vendor/qcom/opensource/wlan/`, QCACLD module `qcacld-3.0` `Makefile` defaults to **MODNAME=wlan** (actual shipping module naming/ABI must be inspected; NOT `qca_cld3_peach_v2` by assumption).

Public SM8475 locations analyzed:
- `qcacld-3.0/configs/default_defconfig`: `CONFIG_CNSS_QCA6490`, `CONFIG_LITHIUM`, `CONFIG_QCACLD_FEATURE_NAN`, monitor flags; `DP_RX_DROP_RAW_FRM` check required.
- `qcacld-3.0/core/hdd/src/wlan_hdd_main.c`: station/monitor adapter netdev ops; monitor .ndo_start_xmit absent; target of PAS host hook.
- `qcacld-3.0/core/hdd/src/wlan_hdd_rx_monitor.c`: `hdd_rx_monitor_callback()`, `cdp_set_monitor_mode()`.
- `qcacld-3.0/core/hdd/src/wlan_hdd_nan_datapath.c`: `hdd_ndi_open`, `hdd_ndi_start`, `hdd_ndi_delete`; firmware `nan_datapath_enabled` capability gate.
- `qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c`: original `hdd_hard_start_xmit()`; requires distinct PAS raw transmitter.
- `qcacld-3.0/core/wma/src/wma_data.c`: `wma_update_tx_send_params()`, `wma_tx_packet()`; data decapsulation pitfall noted above.
- `qcacld-3.0/core/wma/src/wma_mgmt.c`: `wma_mgmt_unified_cmd_send()`, firmware `wmi_service_mgmt_tx_wmi` capability gate.
- `qcacld-3.0/core/wma/src/wma_dev_if.c`: vdev/NDI peer handling and critical cross-version conflicts.
- `qca-wifi-host-cmn/wmi/src/wmi_unified_tlv.c`: `populate_tx_send_params()`, `WMI_MGMT_TX_SEND_CMDID`, explicit `frame_type/retry_limit/mcs_mask/bw_mask`.
- `qca-wifi-host-cmn/wmi/src/wmi_unified_p2p_tlv.c`: `WMI_VDEV_ADD_MAC_ADDR_TO_RX_FILTER_CMDID`, response parsing.
- `qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_tx_ops.c` and `rx_ops.c`: vdev create/start/up/stop/response.
- `qca-wifi-host-cmn/dp/wifi3.0/dp_tx.c`: `dp_tx_prepare_raw()`; raw host path not equal to firmware acceptance.
- `qca-wifi-host-cmn/dp/wifi3.0/dp_rx.c`: RAW receiver, decapsulation/drop handling.
- `qca-wifi-host-cmn/qdf/inc/qdf_types.h`, `qdf/src/qdf_types.c`, `dp/inc/cdp_txrx_cmn_struct.h`: new host PAS mode enums.
- `qcacld-3.0/Kbuild` and `Kconfig`: feature gating.

Original OPAirDrop core interfaces and source files:
- `kernel/wonder/mac80211.c`: Wonder virtual `mac80211` and `ieee80211_register_hw()`, RX, TX.
- `kernel/wonder/wondertap.c` and `kernel/wonder/include/wonder/wondertap.h`: vendor operations interface.
- `kernel/wonder/main.c`: provider platform component lookup and physical interface.
- `kernel/driver/wlan_hdd_wondertap.c`: donor vendor callback implementation.
- `kernel/driver/wma_opairshare_pas_mgmt.h`: donor WMI TX bridge; functions `opairshare_bridge_worker()`, `opairshare_pas_mgmt_xmit()`.
- `kernel/driver/wma_opairshare_awdl_rx_mac_filter.h`: RX filter.
- `kernel/driver/wlan_hdd_opairshare_aux_rx.h`: receive bridge.
- `kernel/source-map.json`: 44 entries, **42 kernel_path mappings plus 2 host-test-only helpers** (`agg-core.h`, `collect-core.h`).
- `kernel/patches/0006-stage3-hdd-ops-lifecycle-ddk.patch`: donor `QDF_PASSTHRU_MODE`, netdev start_xmit, lifecycle skeleton; **written against SM8750 and not directly applicable to SM8475**.
- `module/bin/common.sh` and `module/bin/kernel-identity.sh`: SM8750 driver names, module build ID, hardcoded 6.6/coexistence parameters; **must not reuse for Ace 2 until adapted**.
- `module/customize.sh`: installer presently expects Oplus `sun`, existing binary bundle and legacy settings; not an Ace 2 installer.
- `oshare/`, `native/`, `module/` and Mosey service assets: desirable to reuse, but Android 15 hooks and native ABI remain unverified.

## 5. EVERY file introduced or edited on the PR through handoff (13 files)

**Files exist on the head branch.** The generated source patches live in Actions artifacts at this stage, not permanently as an external vendor checkout in the PR.

| Path | Implementation state and meaning |
| --- | --- |
| `platforms/oneplus-ace2/platform.json` | Device, official source ref, read-only interface inventory, non-bypass guardrails. |
| `platforms/oneplus-ace2/README.md` | Platform goals, limitations and rollout milestones. Older introductory line may still say “SOURCE AUDIT ONLY”; check later appended update. |
| `tools/ace2-source-audit.py` | Fails closed if expected public source files/tokens absent; source presence test ONLY. |
| `tools/ace2-build-baseline.sh` | `repo init/sync` official full kernel manifest, source-lock `manifest -r`, optional `ACE2_APPLY_MODE_PATCH=1`, official `waipio gki` build, artifact/report inventory. |
| `tools/ace2-artifact-report.py` | Enumerates `.ko`, SHA-256 and `modinfo` fields and expects WLAN module; does not prove ABI matches actual phone. |
| `.github/workflows/ace2-kernel.yml` | On push, Linux-host C classifier test, source audit, QDF source rewrite, generated `ace2-core-platform.patch` artifact. Separate full `kernel-baseline` job gated by `workflow_dispatch.inputs.full_kernel` OR commit containing `[ace2-full-kernel]`. A passing push is normally only source audit; full job can be SKIPPED. |
| `kernel/ace2/wlan_hdd_opairshare_frame.h` | New C AWDL 802.11 header classifier; rejects malformed/protected/DS frames; classifies Probe Request, Action, Apple LLC/SNAP QoS DATA. Not a radio transmitter. |
| `tests/ace2-frame-test.c` | Native host C assertions for classifier edge cases; green CI is **not** a kernel compile. |
| `tools/ace2-port-core.py` | Strict/idempotent edits to QDF `QDF_PASSTHRU_MODE`, `wlan_op_mode_passthru`, Kconfig `CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE` **default off**, Kbuild CPP flag; copies classifier header to SM8475 WMA tree; works with standalone vendor checkout. |
| `kernel/driver/wma_opairshare_pas_mgmt.h` | Existing donor WMI TX bridge modified with `#ifdef OPAIRSHARE_ACE2_PAS_BRIDGE` and `ace2_awdl_classify()` validation. This donor file is NOT automatically compiled into an Ace 2 driver. |
| `tools/ace2-port-overlays.py` | Transactional 3-way `git merge-file` source port; verifies SHA of original SM8750 ancestor, refuses mismatches, optional **dry-run only** source drift preview, `--write --safe-only` stages compatible subset and explicitly reports blockers, excludes BE-only `dp_be_rx.c` and `hal_be_api_mon.h`. Source merge != compile. |
| `tools/ace2-resolve-core.py` | Targeted **candidate** resolver for SM8475 `target_if_vdev_mgr_rx_ops.c`, `wlan_hdd_tx_rx.c` and `wma_dev_if.c`; includes decisions to retain Lithium originals and selectively add PAS lifecycle/self-peer support. Candidate generation passed CI; C compile and runtime not proven. |
| `.github/workflows/ace2-merge-preview.yml` | Sparse clones original SM8750 at pinned commit and public Ace 2 branch; generates strict compatible partial source patch plus targeted critical conflict-resolution **candidate** patch and reports. It does not package an installable module. |

**Do not mistake** checked-out GitHub Actions temp directories for committed vendor driver source. The PR currently contains tools, donor file adjustment, and source patch generation logic, not a completed SM8475 WLAN driver tree or APK/root module.

## 6. Source overlay merge, detailed blockers

Source-map count originally: **44 entries**, of which **42 real kernel mappings** and 2 host-only helper records.

Strict initial merge status on original ref:
- **23 source paths clean/newly stageable**.
- **17 blocked paths** (mostly recorded SM8750 source SHA not matching actual pinned ancestor).
- **2 SM8750 BE architecture components excluded** (`dp_be_rx.c`, `hal_be_api_mon.h`).

A *read-only* source-drift textual preview found within 17 blockers:
- **11** textual conflicts,
- **5** text-clean previews with unverified original source SHA (still block strict patch),
- **1** missing SM8475 target path `qcacld-3.0/components/dp/core/src/wlan_dp_txrx.c`.

Known blocked/conflicted files:
```
qca-wifi-host-cmn/dp/wifi3.0/monitor/dp_mon_filter.c
qca-wifi-host-cmn/dp/wifi3.0/dp_peer.c
qca-wifi-host-cmn/dp/wifi3.0/dp_rx.c
qca-wifi-host-cmn/dp/wifi3.0/dp_rx_err.c
qca-wifi-host-cmn/dp/wifi3.0/monitor/1.0/dp_rx_mon_dest_1.0.c
qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_rx_ops.c
qca-wifi-host-cmn/target_if/mlme/vdev_mgr/src/target_if_vdev_mgr_tx_ops.c
qcacld-3.0/components/dp/core/src/wlan_dp_txrx.c  # absent in SM8475
qcacld-3.0/core/hdd/src/wlan_hdd_scan.c
qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c
qcacld-3.0/core/hdd/src/wlan_hdd_wmm.c
qcacld-3.0/components/cmn_services/policy_mgr/inc/wlan_policy_mgr_api.h
qcacld-3.0/components/cmn_services/policy_mgr/src/wlan_policy_mgr_get_set_utils.c
qcacld-3.0/components/cmn_services/policy_mgr/src/wlan_policy_mgr_pcl.c
qcacld-3.0/core/wma/src/wma_dev_if.c
qcacld-3.0/core/wma/src/wma_mgmt.c
qcacld-3.0/core/wma/src/wma_utils.c
```

The targeted candidate resolver covers only **three**: `target_if_vdev_mgr_rx_ops.c`, `wlan_hdd_tx_rx.c`, `wma_dev_if.c`. It resolves textual conflict markers and emits a candidate patch; it does not establish correct business logic/compilation. Some other drift-clean code MAY be manually reviewed and safely accepted later; never override an unverified ancestor by default.

The original donor source hash may differ because of a slightly different upstream source snapshot even at the specified commit, or source-map provenance. Determine which before changing safety checks.

## 7. CI and links (observed at handoff, refresh live status!)

Every past GitHub Actions timestamp uses UTC; date here is local UTC+8.

- **Green source-level classifier + QDF source edits:** [run 41331074616](https://github.com/jahn2007/OPAirDrop/actions/runs/41331074616).
- **Green partial Qualcomm patch generation:** [run 41331876609](https://github.com/jahn2007/OPAirDrop/actions/runs/41331876609). Artifacts: `ace2-qualcomm-merge-preview`, `ace2-safe-source.patch`, JSON blocker reports (run-specific artifacts expire).
- **Green critical-file candidate stage:** [run 41332113125](https://github.com/jahn2007/OPAirDrop/actions/runs/41332113125), action reports target_if vdev, HDD TX/RX and WMA dev-if candidates; **NO full kernel compile**.
- **Green latest source-level run observed:** [run 41332197193](https://github.com/jahn2007/OPAirDrop/actions/runs/41332197193) (commit `cd3bc524411580f082b7c0d79a0d14561dc8cf69`).
- **FULL official SM8475 kernel compile:** [run 41331361225](https://github.com/jahn2007/OPAirDrop/actions/runs/41331361225). On last API inspection it was still `in_progress`, job `kernel-baseline` active at `Sync official Ace 2 kernel and compile baseline modules`. **Outcome UNKNOWN as of handoff**. Source-audit job in same run succeeded. Do not assume success/failure; fetch the new result and logs in the next chat.
- Another queued/pending full/source run [41332191597](https://github.com/jahn2007/OPAirDrop/actions/runs/41332191597) had no completed jobs when last observed; check again.

Important distinction: Most green `ace2-kernel.yml` executions were `source-audit` success with `kernel-baseline` **skipped**. No trustworthy full WLAN build result was observed by the conversation's end. The `ace2-merge-preview.yml` green result is patch generation only.

### CI bugs already found and fixed in earlier commits

- `kernel/source-map.json` contains two helper records without `kernel_path`; initial script KeyError fixed by skipping them.
- Bash `--preview-base-drift` command initially double-escaped a trailing slash; fixed.
- Kbuild source anchor initially used literal `\\n` instead of actual newline escape; fixed.
- Git sparse checkout blocked staging of newly created AWDL header; fixed with `git add --sparse`.
- A donor header had a blank EOF line; staged diff-check normalized or otherwise made pass.
- Targeted source conflict resolver's vdev timer duplicate check was overbroad; fixed.
- **Future**: inspect full workflow logs and compiler errors before deciding architecture. CI smoke tests can pass despite severe linker, KMI, runtime and firmware incompatibilities.

## 8. Concrete commands and tool entrypoints

All development compiles on GitHub Actions; below are examples for inspecting checked-out sources in CI, not requests for user to install local tools.

### Source audit (already working)

```bash
python3 tools/ace2-source-audit.py \
  --source /path/to/android_kernel_modules_and_devicetree_oneplus_sm8475 --json
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 \
  -o /tmp/ace2-frame-test tests/ace2-frame-test.c
/tmp/ace2-frame-test
```

### Source preparation (read-only first, then changes only to an isolated CI checkout)

```bash
python3 tools/ace2-port-core.py --source /path/to/ace2-vendor --dry-run
python3 tools/ace2-port-core.py --source /path/to/ace2-vendor
python3 tools/ace2-port-overlays.py \
  --donor . --sm8750-base /path/to/SM8750-original \
  --ace2 /path/to/ace2-vendor --report-dir /tmp/ace2-merge --preview-base-drift
python3 tools/ace2-port-overlays.py \
  --donor . --sm8750-base /path/to/SM8750-original \
  --ace2 /path/to/ace2-vendor --report-dir /tmp/ace2-merge/staged \
  --write --safe-only
python3 tools/ace2-resolve-core.py \
  --conflict-root /tmp/ace2-merge/conflicts \
  --target-root /path/to/ace2-vendor \
  --report /tmp/ace2-merge/critical-candidate-report.json \
  --write
```

**Caveat:** the conflict-root needs to be generated by `--preview-base-drift` first. For future CI, do not automatically promote partial, candidate or text-clean patches to real releases without resolving remaining dependencies and compiling. Audit applicability after changing the donor WMI header or base snapshot.

### Full kernel source build

See `tools/ace2-build-baseline.sh`, `ace2-kernel.yml`. The script runs `repo init` using `oneplus_ace2_v.xml`, `repo sync -c`, `repo manifest -r`, optional `ACE2_APPLY_MODE_PATCH=1`, and `kernel_platform/oplus/build/oplus_build_kernel.sh waipio gki`. Requires large runner disk and toolchain. It does **not** automatically take the independent three-way donor overlay patch yet.

### Reproducibility and identities

At minimum, collect:
- `uname -r` exact device release; running kernel build ID and `/proc/version` if user later authorizes device inspection.
- Official manifest component commit SHAs (`repo manifest -r`).
- `Module.symvers`, kernel config, module `vermagic`, `.note.gnu.build-id`, linked provider symbols, native module names and dependencies.
- Running vendor WLAN firmware capabilities (NOT merely C declarations) at a later **authorized** stage.
- An uninstall/rollback path that leaves stock Wi-Fi operational.

## 9. The *next implementation steps*, prioritized and test-gated

1. **Inspect live PR head/Actions and full kernel run #41331361225 NOW.** If still running or fails, inspect logs and fix build prerequisites (manifest availability, storage, prebuilts, toolchain, `Kconfig` definitions). Make baseline build reproducible. Do not claim `source-audit` green as kernel compile green.
2. **Bring actual vendor WLAN PAS/NDI lifecycle across:** QDF host enum, HDD netdev registration/open/stop, WMI vdev creation & NDI mapped backend, correct START/UP/STOP/DELETE response ownership, self peer/peer map/AST. Use SM8475 APIs; no MLO/BE references. Re-evaluate currently prepared `ace2-resolve-core.py` candidates for compile correctness.
3. **Wire actual Wonder `wondertap_ops` provider:** vendor callback registration from correct device location, build Wonder/mac80211 Linux 5.10, map physical interface, ensure init and teardown work safely and no deadlock. Avoid hardcoding SM8750 provider names.
4. **RAW TX**: full 802.11 AWDL Action/Probe/QoS frame, radiotap parsing, `wlan_mgmt_txrx_mgmt_frame_tx`, `WMI_MGMT_TX_SEND_CMDID`, explicit WMI `frame_type=DATA` for QoS, memory ownership, completion and backpressure. Avoid normal `wma_tx_packet` `cdp_tx_non_std` 802.3 conversion. Make firmware capability errors visible, fail closed.
5. **RAW RX & ACK**: use QCA6490/Lithium Monitor RX callbacks, preserve full 802.11 frames and timestamps/radiotap, configure MAC RX filters and obtain firmware success responses; verify that host RX drop guards do not discard frames. Hardware ACK remains unknown without authorized real testing. Native aggregation/REO optimization is deferred.
6. **Compile fully** on exact SM8475 5.10 vendor kernel. Resolve EVERY resulting KMI/CRC, missing symbols or build flag conflict. Produce `.ko` and metadata artifacts; make install step inaccessible unless hardware identity/ABI checks pass. Never borrow `qca_cld3_peach_v2.ko`, or rename it to `wlan.ko`.
7. **Userspace ColorOS 15**: test/package Mosey provider/FFI/server compatibility, LSPosed API 102 OShare hooks and device UI, real send/receive/file lifecycle. Preserve existing OShare + Wonder instead of re-writing AWDL unnecessarily. Root package must work with APatch, strict SELinux and recovery, and disable/revert reliably.
8. **Release gate**: After owner explicitly permits tests, evaluate discovery and **real bidirectional** iPhone/macOS file transfer with SHA256, reject/cancel, repeat/timeout, Wi-Fi restoration; inspect firmware assertions and OTA ACK failures. If firmware fundamentally blocks NDI RAW TX/ACK, consider another viable backend or explicitly report impossibility on current stock firmware. Only then mark GitHub release **working**. Pre-test CI artifacts must be clearly named experimental/noninstallable.

Suggested milestone naming:
- **M0** source-check and reproducible stock kernel full build;
- **M1** complete modified WLAN + Wonder + provider build with correct ABI;
- **M2** hardware verified real AWDL discovery and bidirectional small-file transfer;
- **M3** ColorOS 15 OShare UX/installer/rollback complete;
- **M4** stable release and performance optimization.

## 10. Non-negotiable project safety, quality and disclosure constraints

- **No phone tests now** without new permission. Earlier passive monitor observations can be cited, but they are NOT AirDrop tests.
- No “compiled successfully” statement without compiler link artifacts and logs. A successful source audit, candidate merge or GitHub ZIP packing is NOT a driver build, firmware test or successful AirDrop.
- No forced kernel module insertion on wrong ABI/phone/stock kernel; no boot partition flash, firmware patching, regulatory bypass, root security weakening or unsafe Wi-Fi replacement for the sake of a green CI.
- Restore normal Wi-Fi state after AirDrop exit/failure; STA disconnect during active AirDrop is permissible.
- Preserve `main` existing SM8750 supported release flow; all Ace 2 changes on isolated branch with device gating.
- No local SDK/NDK/compilers on user's computer; GitHub Actions automatically build and publish artifacts when legitimately ready.
- Protect secrets/signing materials (GitHub Secrets, no logging/committing private keys). Do not upload private Wi-Fi SSIDs, MACs or device logs without consent.
- Keep explanations and UX in Chinese suitable for technically experienced user; user asks actual code changes, not merely next-step suggestions.
- Keep this doc and PR Conversation continuously updated after future significant changes: **head SHA, CI run, exact result, artifacts, blocked path, next unblocked action**.

## 11. Development chronology from this conversation

1. **Prior hardware phase:** rooted Ace 2, QCA6490 monitor interface could be created; STA disconnected; user accepted Wi-Fi interruption. No proven AWDL injection.
2. **Architecture clarification:** UI impersonation alone cannot transmit AirDrop; AWDL software stack vs actual IEEE 802.11 TX/RX and ACK.
3. **Viability analysis:** choose **plan B**: reuse OShare/Mosey/Wonder, only adapt minimal RAW TX/RX host driver; remain flexible if better end-to-end route exists.
4. **User's directive:** directly finish repo as a working application, all builds/releases via GitHub Actions, no phone tests until permission.
5. **Repository branch created:** `feat/oneplus-ace2-sm8475`; PR #1 opened draft, Issues unavailable/disabled.
6. **Platform inventory:** `platform.json`, source audit; official SM8475/NAN/monitor/WMI source verified.
7. **Official baseline build job:** script and Actions added; full kernel job launched, no final successful result observed.
8. **Cross-platform patching:** transactional strict 3-way source overlay tool, 42 mappings, 23 viable vs 17 blocked and 2 BE-only excluded; source-drift read-only preview; GitHub Actions generated safe partial patch.
9. **New AWDL classifier:** hardware-independent C frame validation added, host test passed; optional Kconfig/PAS host enum staging produced real official-source diff. Existing SM8750 WMI bridge augmented behind Ace 2 compile guard, but not yet connected as an Ace 2 WLAN build.
10. **Three critical conflict candidates:** targeted preservation of SM8475 older APIs and selective donor PAS logic; PR Action generated separate candidate patch and passed source-level checks.
11. **This request:** owner explicitly requested storing the **entire relevant conversation and development state in PR #1** so that another conversation can resume from URL alone. This file, PR description and a detailed PR Conversation comment constitute the persistent handoff.

## 12. Completion definition — no shortcuts

Real native AirDrop is considered complete only when:
- Ace 2 rooted ColorOS 15 can install compatible module/APK without compromising stock WLAN, and uninstall/disable cleanly;
- stock iPhone/Mac AirDrop sees this phone and the ColorOS OShare UI sees Apple devices;
- **both** phone→Apple and Apple→phone transfers occur directly without cloud/QR/manual IP, end-to-end bytes and SHA256 match, UI accept/reject/cancel works;
- repeated sessions, errors and Wi-Fi restoration operate reliably;
- released binaries are built by GitHub Actions from tracked inputs, device/ABI safe, accurately labeled as tested.

Until then call it “candidate port”/“source work”/“experimental CI artifact”, NEVER “Ace 2 可用版”.

---

### References / read first
- [This PR, discussion, changed files and Actions](https://github.com/jahn2007/OPAirDrop/pull/1)
- [Platform constraints and code updates](https://github.com/jahn2007/OPAirDrop/blob/feat/oneplus-ace2-sm8475/platforms/oneplus-ace2/README.md)
- [Original engineering architecture](https://github.com/jahn2007/OPAirDrop/blob/main/docs/TECHNICAL.md)
- [Original SM8750 AWDL low-level record](https://github.com/jahn2007/OPAirDrop/blob/main/docs/SM8750-AWDL.md)
- [Original build instructions](https://github.com/jahn2007/OPAirDrop/blob/main/docs/BUILD.md)
- [Ace2 official manifest](https://github.com/OnePlusOSS/kernel_manifest/blob/oneplus/sm8475/oneplus_ace2_v.xml)
- [Ace2 official vendor WLAN tree](https://github.com/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8475/tree/oneplus/sm8475_v_15.0.0_ace_2/vendor/qcom/opensource/wlan)

**Handoff accuracy:** snapshots of task status above were verified via connected GitHub API on 2026-11-02 UTC+8; an Actions job may have progressed since. When the head branch changes, obtain its latest commit ID rather than relying on the historical SHA above.

## 13. 2026-11-02 resumed development — verified baseline failure and code updates

- PR #1 remained an open Draft; starting head was `c3f9580f506799975413209af68b4769748d0187`.
- Rechecked full kernel Actions run [41331361225](https://github.com/jahn2007/OPAirDrop/actions/runs/41331361225): **completed / failure**. Source-audit succeeded; kernel-baseline failed. Official manifest sync, PAS QDF staging, and many kernel C compilation steps completed. The compiler reached `LTO vmlinux.o`, then the hosted runner received a shutdown signal and exited 143. This is **not proof of a specific C/ABI failure** and not a successful baseline build. An earlier `mktemp` warning referred to the absent `out/target/product/taro/tmp` directory; it did not immediately stop compilation.
- Modified `kernel/ace2/wlan_hdd_opairshare_frame.h` and `tests/ace2-frame-test.c`: explicitly reject unsupported More Fragments, nonzero fragment index, and Order/HTC frames; retain valid 802.11 Retry frames; Action management frame now requires at least two bytes of body. This is a host-side frame classifier change, not firmware TX/RX support.
- Modified `tools/ace2-build-baseline.sh`: create vendor taro temporary build directory, capture separate stdout/stderr logs and exit diagnostics, and retain crash/interrupt summaries where a runner allows teardown.
- Modified `.github/workflows/ace2-kernel.yml`: syntax-check all current Ace 2 Python port tools.
- Commits in this continuation: `d9996463`, `cceb746e`, `861dfc46`, `cae12f4a`. Check live head and subsequent Actions independently.
- **Build limitation:** these commits use the normal source-audit path; a green push does not mean the gated full-kernel job ran. Full-kernel compile and correct 5.10 KMI/ABI remain unverified.
- **Still blocked:** SM8475 PAS/NDI lifetime and WMI RAW 802.11 TX integration, Lithium monitor RX, Wonder/provider build, system integration, APK/root module, and user-authorized hardware transfer verification. No Apple AirDrop transfer is claimed.
- Next engineering priority: reproducible standalone modified WLAN + Wonder compile, isolated from the extremely heavy whole-GKI LTO run; resolve native SM8475 source conflicts with the actual compiler diagnostics rather than promoting candidate text merges. Keep device installation/release gated.


## 14. 2026-11-02 — continued SM8475 WMA/HDD native integration

This development session started from the previously recorded head `30bace3ee888b50537bf60febbe2ba3d9738ef68`. Latest source-audit on that commit was [41415849293](https://github.com/jahn2007/OPAirDrop/actions/runs/41415849293) **success**; full kernel job was skipped.

Implemented and committed this continuation:

- `tools/ace2-port-wma-hook.py`: strict, repeatable real-source editing of original SM8475 `core/wma/src/wma_data.c`; inserts `wma_opairshare_pas_mgmt.h` immediately **after** the original `wma_tx_packet()`, gated on both `OPAIRSHARE_ACE2_PAS_BRIDGE` and `DRIVER_PASSTHRU_MODE`. Requires the actual donor bridge header to have been staged. Host tests `tests/test_ace2_wma_hook.py` fail closed on drift, missing header or duplicates.
- `tools/ace2-port-hdd-tx.py`: guards and rewrites the original SM8475 `hdd_hard_start_xmit()` only within `QDF_PASSTHRU_MODE`: pass the skb to `opairshare_pas_mgmt_xmit`, return `NETDEV_TX_BUSY` without consuming skb when the native bridge signals backpressure, and drop PAS frames if the bridge refuses them instead of reinterpreting radiotap as STA Ethernet. Ordinary STA path unchanged. Unit tests in `tests/test_ace2_hdd_tx.py`.
- `kernel/driver/wma_opairshare_pas_mgmt.h`: fixes Ace 2-specific Retry/Power-Management/More-Data-bit handling during packet type dispatch without rewriting the skb (commit `802f79f5`).
- `tools/ace2-port-core.py`: the previously disabled bridge Kbuild flag now supplies **both** Ace 2 and `DRIVER_PASSTHRU_MODE` defines when the candidate option is explicitly enabled.
- `.github/workflows/ace2-merge-preview.yml`: includes `wma_data.c` in sparse checkout; stages both WMA native include and the targeted HDD send dispatch; preserves unresolved cross-generation conflicts and candidate reports. The initial new workflow run [41416726952](https://github.com/jahn2007/OPAirDrop/actions/runs/41416726952) failed only because the sparse checkout did not yet contain `wma_data.c`, then was corrected. [41417286191](https://github.com/jahn2007/OPAirDrop/actions/runs/41417286191) completed **success**, including all three previous critical conflict candidates and new HDD TX hook, **source-level only**.
- `tools/ace2-stage-candidate.sh` and `tools/ace2-build-baseline.sh`: can now assemble pinned SM8750/SM8475 source candidates in the **fully synced** official kernel tree, then request a *compiler* attempt with `WLAN_CFG_OVERRIDE=CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE=y`. Source base remains SHA-checked; only the three explicit conflict candidates are promoted. SM8750 clone is outside uploaded reports.
- `.github/workflows/ace2-kernel.yml`: `workflow_dispatch` input `candidate_port` plus commit trigger `[ace2-candidate-kernel]`. Normal source-audit runs test HDD/WMA staging with no new phone operations; kernel build is explicitly gated.
- `platforms/oneplus-ace2/README.md` updated with setup and limits.

**Important:** The WMA/HDD code is staged in official source but has NOT yet passed a complete Ace 2 WLAN compiler/link test. It does not create a PAS netdev or provide a working Wonder provider. The remaining blocked Lithium DP/WMA/HDD mappings, firmware behavior, RX, mac80211/Wonder, ABI, ColorOS userspace and real Apple interoperability still require development.

Next: inspect the new Actions candidate build diagnostics and resolve each actual C/Kbuild/API failure; only then progress to Wonder, RX and firmware. Continue keeping the PR as Draft and without phone tests.


## 15. 2026-11-02 — recovery of CodeLinaro compiler checkout failures

- The experimental compile Action [#41417985517](https://github.com/jahn2007/OPAirDrop/actions/runs/41417985517) ended **failure**, before compilation: official repo manifest sync returned `Cannot initialize work tree for kernelplatform/prebuilts-master/clang/host/linux-x86`. Runner disk had 109 GB free **before** sync; that does not establish remaining space/IO/transport state at checkout.
- A second preceding candidate [#41418079340](https://github.com/jahn2007/OPAirDrop/actions/runs/41418079340) likewise ended **failure**, but its failed project was the official pinned GCC worktree `kernelplatform/prebuilts/gcc/linux-x86/host/x86_64-linux-glibc2.17-4.8`. Both are repo synchronization errors; neither run reached modified WLAN C compilation.
- Official manifest `OnePlusOSS/kernel_manifest`, branch `oneplus/sm8475`, `oneplus_ace2_v.xml` pins Clang `0fc3d01a780023469b7acc18c56a9cf5099a6d6c` and GCC `c9f87ae369034b4942536a1c5bd62e4cd1d828e3`. Do not substitute an arbitrary host compiler.
- Added `tools/ace2-sync-kernel.sh`, invoked from `tools/ace2-build-baseline.sh` immediately after `repo init`. It reduces initial synchronization to `-j2`, sets `--retry-fetches=3`, and, ONLY for those two exact known manifest compiler checkout failures, retries the corresponding checkout serially (`-j1`, at most two tries) before re-running full sync. Limits full-sync passes to three. It never uses `--force-checkout`, `--force-sync`, substitutes compilers, flashes, or changes the phone. Unknown repository failures stop immediately.
- Every attempt and preflight/failure diagnosis is preserved in `$ACE2_BUILD_ROOT/reports/repo-sync-*.log` and `repo-sync-diagnostics-*.txt`; the artifact uploader runs `if: always()`. After successful sync, both toolchain HEAD revisions must match the official manifest pins. These checks do NOT establish working AirDrop.
- Added mocked source synchronization regressions in `tests/test_ace2_sync_kernel.py` covering Clang checkout, GCC checkout, consecutive checkout failures, permanent failure, unknown failure, and a wrong Clang SHA; wired into source-audit Actions.
- This is a **proposed recovery** for the exact observed failure class, not a proven upstream fix. The first *new* full candidate run must be examined for real sync completion, then real compiler diagnostics. Do not claim a kernel or AirDrop release based on source-audit success.


## 16. 2026-11-02 — native SM8475 HDD staging blocker fixed

The new [full-kernel candidate run 41425700917](https://github.com/jahn2007/OPAirDrop/actions/runs/41425700917) **failed**, but it first successfully completed the official `repo sync` and validated **both manifest-pinned Clang and GCC HEADs**, proving the previous compiler worktree errors did not reproduce on this run. The full kernel never compiled: the stage script aborted at `tools/ace2-port-hdd-tx.py:76` with `Unexpected SM8475 HDD TX anchor or partial hook`.

Root cause: `tools/ace2-resolve-core.py` wrote a three-way merged `wlan_hdd_tx_rx.c` based on the SM8750 donor, which had a different `hdd_hard_start_xmit()` layout and a separate `hdd_hard_start_xmit_passthru()`. The new minimal hook had been written for the **original SM8475** HDD path and (correctly) refused to overwrite that incompatible merged file.

Resolution:
- `tools/ace2-resolve-core.py` still parses the exact expected HDD merge conflict but now **preserves the original SM8475 HDD file** and records `native-sm8475-hdd-preserved`. The other two tightly scoped conflict candidates remain unchanged.
- `tools/ace2-stage-candidate.sh` explicitly asserts that the resolver did not transplant the SM8750 HDD implementation; then applies the fail-closed `tools/ace2-port-hdd-tx.py` hook to that native SM8475 source.
- `.github/workflows/ace2-kernel.yml` runs the HDD hook in `--dry-run`, `--write`, repeat-write modes against **real** OnePlusOSS SM8475 vendor source in source-audit CI, confirming the native `adapter->vdev` dispatch and no `hdd_hard_start_xmit_passthru` donor path.
- [Source-audit run 41431949597](https://github.com/jahn2007/OPAirDrop/actions/runs/41431949597) and [merge-preview run 41431880033](https://github.com/jahn2007/OPAirDrop/actions/runs/41431880033) **passed**. These are source-level checks only.
- A fresh actual full-kernel candidate attempt [41432075404](https://github.com/jahn2007/OPAirDrop/actions/runs/41432075404) was triggered by commit `06ccc1fb87a6944f9d359de37e2e0f6861e13c36`. The source-audit job passed. The full-kernel job was still running at the time of writing; check its final result separately.

No kernel module, AirDrop usability, or successful Apple transfer is claimed. Remaining future compilation, linker, firmware, Wonder, RX, ABI, and runtime integration blockers still require actual validation. No device action or release.

## 17. 2026-11-02 — consolidated build-chain review after costly full-run termination

Full candidate [Actions #41432075404](https://github.com/jahn2007/OPAirDrop/actions/runs/41432075404) synchronized both pinned toolchains and completed source staging, then compiled many GKI objects and reached `LTO vmlinux.o`. The GitHub runner subsequently received a shutdown signal; the log is **not** evidence of an SM8475 WLAN C compiler diagnostic or a completed QCACLD module. Before the kernel compile, the public OnePlus wrapper also printed `vendor/oplus/kernel/prebuilt/vendorsetup.sh: No such file or directory`. We audited both the OnePlusOSS `kernel_platform/oplus/build/oplus_build_kernel.sh` wrapper and its actual `kernel_platform/build/android/prepare_vendor.sh` entrypoint.

### Corrected as one coordinated batch

1. **Build exit propagation** — `tools/ace2-run-vendor-build.sh` calls the published `prepare_vendor.sh waipio gki` directly, reconstructing its documented Android board environment. The legacy wrapper sourced a nonexistent vendor setup file and piped the real build through `tee` without `pipefail`; it could hide a build failure. The new helper preserves `PIPESTATUS[0]`, always writes `kernel-build.log` and `build-invocation.txt`, and rejects a candidate if the WLAN Kbuild override was never consumed. `tools/ace2-build-baseline.sh` calls the tested helper.
2. **Diagnostic LTO** — candidate builds default to the official supported `LTO=none` option, solely for quick C/API diagnostics; explicit `ACE2_DIAGNOSTIC_LTO=thin|full` is possible. Non-candidate baseline behavior is unchanged. A no-LTO candidate **cannot** prove production kernel ABI, CFI or real-device compatibility and MUST NOT be published or installed.
3. **Kbuild make-time evaluation** — `tools/ace2-port-core.py` now inserts `ccflags-$(CONFIG_OPAIRSHARE_ACE2_PAS_BRIDGE)` **after** the published `WLAN_CFG_OVERRIDE` eval loop. The earlier location after profile inclusion and before override evaluation meant conditional `ccflags` could expand while the opt-in variable was empty, silently disabling the PAS code. Structural preflight now validates this ordering.
4. **Early source validation** — `tools/ace2-preflight-candidate.py` requires a unique native HDD dispatch, WMA bridge include, required guard macros, PAS QDF enum, Kbuild override and define order, all local donor WMA helper headers, and no conflict markers in critical source files. It is invoked by both `tools/ace2-stage-candidate.sh` and the lightweight `ace2-merge-preview.yml`.
5. **No false-green CI** — critical candidate resolution in the merge-preview workflow is no longer `continue-on-error`, and expensive `kernel-baseline` has `needs: source-audit`. A failed unit/preflight job therefore blocks the full build. Source-audit runs isolated shell/vendor build tests plus preflight tests; it does not require downloading the full GKI.
6. **Artifact identity** — `tools/ace2-artifact-report.py` requires `wlan.ko` (the published QCACLD Kbuild's `MODNAME=wlan`), not a path merely containing the string `wlan`. It reports `qcacld_wlan_found` and does not imply AirDrop firmware readiness.
7. **Fast regression tests** — `tests/test_ace2_vendor_build.py` exercises masked pipeline failures, missing official entrypoint, omitted WLAN Kbuild, supported diagnostic LTO and illegal LTO; `tests/test_ace2_preflight_candidate.py` covers missing headers, failed source guards and incorrect hook structure; `tests/test_ace2_artifact_report.py` rejects unrelated WLAN-like module names.

Source staging/host tests are *not* proof of compiled drivers. The candidate is still subject to unknown SM8750-to-SM8475 API/firmware incompatibilities and 17 unresolved cross-generation overlay mappings (not all are promoted). No release, module installation, or real two-way AirDrop has occurred. Do not treat a successful `LTO=none` compiler probe as sufficient for a phone build.

Next: check the latest fast source and merge-preview CI; only after they pass trigger **one** candidate diagnostic compile to expose real WMA/HDD/compiler errors without multi-minute full LTO, capture exact errors and repeat targeted fixes before any production ABI build.

## 2026-11-02 — holistic pipeline failure review (GKI CFI/KMI)

- Latest examined expensive candidate run: [41441241834](https://github.com/jahn2007/OPAirDrop/actions/runs/41441241834), head `05a7d598`. Official repo sync **passed** with the exact pinned Clang/GCC. Candidate overlay staging and preflight **passed**. GKI built through `vmlinux`, `arch/arm64/boot/Image.lz4`, and `Module.symvers`; **failed** during official ABI symbol-list comparison because `__cfi_slowpath` was missing. This was not a proof of a failed qcacld C compile or a completed WLAN module.
- Audited the entire invoked pipeline: source synchronization and manifest pins; donor merge guards; native HDD and WMA hook staging; QDF/Kbuild override; preflight; official build wrapper; ABI comparison; module artifact reporting. The candidate build was explicitly forcing `ACE2_DIAGNOSTIC_LTO=none`, inconsistent with the CFI symbol expected by the official kernel KMI. For a validation build, disabling LTO makes a stock CFI ABI comparison unrepresentative.
- `tools/ace2-run-vendor-build.sh`: now defaults candidate diagnostics to `LTO=thin`, permits `full`, and **fails closed** on `none` instead of bypassing ABI checks or silently deleting the `__cfi_slowpath` requirement. Emits an explicit CFI/KMI warning if the symbol is still missing, and distinguishes GKI completion from an independently verified `wlan.ko`.
- `.github/workflows/ace2-kernel.yml`: sets diagnostic LTO to `thin` rather than `none`. This retains LTO behavior but does NOT prove stock ABI, and does NOT promise a faster full compile; runner resource and time limits remain potential blockers.
- `tests/test_ace2_vendor_build.py`: updated default-LTO expectation and added regression proving no-LTO is rejected without launching the vendor build. Lightweight source audit passed at [41443973530](https://github.com/jahn2007/OPAirDrop/actions/runs/41443973530) after the test update.
- The post-build artifact reporter still requires an actual `wlan.ko` and rejects GKI-only output. Cross-generation source unresolved mappings, target firmware, passthrough vdev life cycle, and on-device AirDrop remain **unverified**.
- **Do not run another expensive kernel build solely because source-level CI is green**. Check this review and the next complete build's results first. No installable module or AirDrop release is established.

## 2026-11-02 — requested complete deliverable: WLAN compiler gate and next integrated test

The user has authorized continuing software development toward a **working native bidirectional AirDrop release**, not accepting green source-check jobs as a finished product. This does not by itself provide connected phone hardware or verify firmware behavior.

**Actual engineering changes in this continuation:**
- `tools/ace2-build-wlan.sh`: explicit QCACLD external-module build against `kernel_platform/common` and prepared output `kernel_platform/out/msm-waipio-waipio-gki/gki_kernel/common`, consuming the matching `Module.symvers`, using manifest-contained Clang and the native QCA6490 Lithium profile (`CONFIG_CNSS_QCA6490=y`). Candidate explicitly enables the PAS bridge via `WLAN_CFG_OVERRIDE`. Rejects missing/stale `wlan.ko`, bad ELF, non-AArch64 ELF, missing or mismatched `vermagic`, unknown toolchains, missing symbol dependencies and nonzero make exit. This is a compiler probe only, **not device-validated**.
- `tools/ace2-build-baseline.sh`: follows the vendor GKI build with actual external WLAN build for explicit candidate runs, rather than assuming GKI kernel success means WLAN success.
- `tools/ace2-compile-pipeline.sh`: records separate GKI and WLAN results. If the GKI official KMI check is known to fail solely with `__cfi_slowpath` **after** `Module.symvers` exists, it collects WLAN compiler diagnostics without ever marking the overall build successful. Unknown build failures remain fatal before WLAN.
- `tests/test_ace2_build_wlan.py` and `tests/test_ace2_compile_pipeline.py`: fast mocked coverage of kernel-output requirements, module identity/ABI, QCA6490 flags, missing PAS override, unknown compiler, make errors, stale/missing module and KMI diagnostic continuation. The ordinary `ace2-kernel.yml` source-audit job now runs both suites plus shell parsing.
- The initial new source-audit succeeded at [41446810183](https://github.com/jahn2007/OPAirDrop/actions/runs/41446810183), updated integration tests at [41447247022](https://github.com/jahn2007/OPAirDrop/actions/runs/41447247022), and updated vermagic tests at [41447399229](https://github.com/jahn2007/OPAirDrop/actions/runs/41447399229). These runs **skip** the expensive kernel job. They verify control logic, not actual driver compilation.
- External symbol dependencies may still require additional vendor `Module.symvers` entries; `ACE2_WLAN_EXTRA_SYMBOLS` is an explicit, validated list. Do not invent or silently substitute missing symbol tables.

**Next acceptance requirements before a release:**
1. Candidate Actions must compile an actual `wlan.ko` (and pass the stock GKI KMI check) with the exact QCA6490 API and driver config. Inspect genuine C errors; do not patch arbitrary vendor APIs without source evidence.
2. Port PAS/NDI vdev CREATE/START/STOP/DELETE, self peer, error rollback, WMI TX completion and Monitor RX into the native Lithium driver; qualify ACK behavior and mandatory regulatory controls.
3. Build native Wonder/Mosey/OShare integration for ColorOS 15, ensuring the package installer selects a target-matched module and never reuses SM8750 artifacts.
4. With explicit device-testing permission and a tested Wi-Fi rollback path, verify native AirDrop discovery + Android-to-Apple + Apple-to-Android small and large file transfer and SHA256 equality, repeat start/stop, error cleanup and Wi-Fi restore.
5. Only then produce and sign a device-scoped distributable through GitHub Actions/Releases. The branch remains Draft; no finished Ace 2 APK/root module is claimed.

