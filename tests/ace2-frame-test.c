/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "../kernel/ace2/wlan_hdd_opairshare_frame.h"

static void check(void)
{
    unsigned char pkt[64] = {0};
    const unsigned char llc[] = {0xaa,0xaa,0x03,0x00,0x17,0xf2,0x08,0x00};
    assert(ace2_awdl_classify(NULL, 64) == ACE2_AWDL_REJECT);
    assert(ace2_awdl_classify(pkt, 23) == ACE2_AWDL_REJECT);
    assert(ace2_awdl_classify(pkt, 2305) == ACE2_AWDL_REJECT);
    pkt[0] = 0x40;
    assert(ace2_awdl_classify(pkt, 24) == ACE2_AWDL_PROBE_REQUEST);
    pkt[0] = 0xd0;
    assert(ace2_awdl_classify(pkt, 24) == ACE2_AWDL_REJECT);
    assert(ace2_awdl_classify(pkt, 25) == ACE2_AWDL_REJECT);
    assert(ace2_awdl_classify(pkt, 26) == ACE2_AWDL_ACTION);
    pkt[1] = 0x08; /* 802.11 retry is a valid AWDL retransmission */
    assert(ace2_awdl_classify(pkt, 26) == ACE2_AWDL_ACTION);
    pkt[1] = 0x04; /* More Fragments: unsupported */
    assert(ace2_awdl_classify(pkt, 26) == ACE2_AWDL_REJECT);
    pkt[1] = 0x00;
    pkt[22] = 0x01; /* Nonzero fragment number: unsupported */
    assert(ace2_awdl_classify(pkt, 26) == ACE2_AWDL_REJECT);
    pkt[22] = 0x00;
    pkt[0] = 0x88;
    assert(ace2_awdl_classify(pkt, 64) == ACE2_AWDL_REJECT);
    memcpy(pkt+26, llc, sizeof(llc));
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_QOS_DATA);
    pkt[1] = 0x08; /* QoS retransmission */
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_QOS_DATA);
    pkt[1] = 0x80; /* Order/HT-control extends the QoS header */
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_REJECT);
    pkt[1] = 0x00;
    pkt[1] = 0x01; /* To-DS data is not part of our AWDL bridge */
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_REJECT);
    pkt[1] = 0x40; /* protected */
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_REJECT);
    pkt[1] = 0x00;
    pkt[28] = 0x04;
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_REJECT);
    pkt[28] = 0x03;
    assert(ace2_awdl_classify(pkt, 33) == ACE2_AWDL_REJECT);
    pkt[0] = 0x89; /* unsupported 802.11 version */
    assert(ace2_awdl_classify(pkt, 34) == ACE2_AWDL_REJECT);
}

int main(void) { check(); puts("Ace2 AWDL frame classifier: PASS"); return 0; }
