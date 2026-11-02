#!/usr/bin/env python3
"""Insert a minimal SM8475 HDD PAS TX dispatch, preserving all ordinary STA TX.

This is an opt-in *candidate* stage for native QCA6490 WLAN sources. A hooked
netdev is not a working AirDrop interface without PAS vdev creation and
the WMA / firmware RAW TX backend.
"""
import argparse
import json
from pathlib import Path

TARGET = Path("vendor/qcom/opensource/wlan/qcacld-3.0/core/hdd/src/wlan_hdd_tx_rx.c")
ANCHOR = """netdev_tx_t hdd_hard_start_xmit(struct sk_buff *skb, struct net_device *net_dev)
{
	hdd_dp_ssr_protect();

	__hdd_hard_start_xmit(skb, net_dev);

	hdd_dp_ssr_unprotect();

	return NETDEV_TX_OK;
}"""
HOOK = """#ifdef OPAIRSHARE_ACE2_PAS_BRIDGE
/* WMA bridge belongs to the same wlan module; no PAS mode affects STA. */
extern int opairshare_pas_mgmt_xmit(struct sk_buff *skb,
				   struct wlan_objmgr_vdev *vdev,
				   struct net_device *dev);
#endif

netdev_tx_t hdd_hard_start_xmit(struct sk_buff *skb, struct net_device *net_dev)
{
#ifdef OPAIRSHARE_ACE2_PAS_BRIDGE
	struct hdd_adapter *adapter = WLAN_HDD_GET_PRIV_PTR(net_dev);
	int passthru_result;
#endif
	hdd_dp_ssr_protect();

#ifdef OPAIRSHARE_ACE2_PAS_BRIDGE
	if (adapter && adapter->device_mode == QDF_PASSTHRU_MODE) {
		passthru_result = adapter->vdev ?
			opairshare_pas_mgmt_xmit(skb, adapter->vdev, net_dev) : 0;
		if (!passthru_result) {
			/* Never reinterpret a PAS radiotap/802.11 skb as STA Ethernet. */
			dev_kfree_skb_any(skb);
			passthru_result = 1;
		}
		hdd_dp_ssr_unprotect();
		/* BUSY must leave the skb unconsumed (WMA bridge returns 2). */
		return passthru_result == 2 ? NETDEV_TX_BUSY : NETDEV_TX_OK;
	}
#endif

	__hdd_hard_start_xmit(skb, net_dev);

	hdd_dp_ssr_unprotect();

	return NETDEV_TX_OK;
}"""


def stage(root: Path, write: bool) -> dict:
    base = root.resolve()
    path = (base / TARGET).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("Missing official SM8475 HDD source")
    data = path.read_text(encoding="utf-8")
    if data.count(HOOK) == 1:
        if data.count("opairshare_pas_mgmt_xmit(") != 2:
            raise ValueError("Unexpected duplicate bridge call")
        state = "already-staged"
    elif data.count(ANCHOR) == 1 and "opairshare_pas_mgmt_xmit(" not in data:
        state = "staged" if write else "would-stage"
        if write:
            path.write_text(data.replace(ANCHOR, HOOK, 1), encoding="utf-8")
    else:
        raise ValueError("Unexpected SM8475 HDD TX anchor or partial hook")
    return {
        "platform": "oneplus_ace2_sm8475",
        "source": str(TARGET),
        "state": state,
        "hook_compiled": False,
        "pas_vdev_registered": False,
        "firmware_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = stage(args.source, args.write)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
