/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Qualcomm WLAN AWDL frame classification for OnePlus Ace 2.
 *
 * This function deliberately DOES NOT transmit, change the radio channel,
 * bypass firmware restrictions, or mark NDI/passthru support as available.
 * Caller must independently validate vdev, peer, WMI service and regulatory state.
 */
#ifndef OPAIRSHARE_ACE2_FRAME_H
#define OPAIRSHARE_ACE2_FRAME_H
#ifdef __KERNEL__
#include <linux/types.h>
typedef u8 ace2_byte;
#else
#include <stddef.h>
#include <stdint.h>
typedef uint8_t ace2_byte;
#endif

enum ace2_awdl_frame_class {
    ACE2_AWDL_REJECT = 0,
    ACE2_AWDL_PROBE_REQUEST = 1,
    ACE2_AWDL_ACTION = 2,
    ACE2_AWDL_QOS_DATA = 3,
};

static inline enum ace2_awdl_frame_class
ace2_awdl_classify(const ace2_byte *p, size_t n)
{
    /* Native 802.11 frame, WITHOUT a radiotap prefix or FCS. */
    static const ace2_byte apple_llc[] = {
        0xaa, 0xaa, 0x03, 0x00, 0x17, 0xf2, 0x08, 0x00
    };
    unsigned int fc, i;
    if (!p || n < 24 || n > 2304)
        return ACE2_AWDL_REJECT;
    fc = (unsigned int)p[0] | ((unsigned int)p[1] << 8);
    /* Unsupported version, DS flags, protected and fragmented frames. */
    if ((fc & 0x0003) || (fc & 0x0300) || (fc & 0x4000))
        return ACE2_AWDL_REJECT;
    if (fc == 0x0040)     /* Management / probe request */
        return ACE2_AWDL_PROBE_REQUEST;
    if (fc == 0x00d0)     /* Management / action */
        return n >= 25 ? ACE2_AWDL_ACTION : ACE2_AWDL_REJECT;
    if (fc != 0x0088 || n < 34)
        return ACE2_AWDL_REJECT;
    /* 3-address QoS data: 24B MAC header + 2B QoS control + Apple LLC/SNAP */
    for (i = 0; i < sizeof(apple_llc); ++i)
        if (p[26 + i] != apple_llc[i])
            return ACE2_AWDL_REJECT;
    return ACE2_AWDL_QOS_DATA;
}
#endif
