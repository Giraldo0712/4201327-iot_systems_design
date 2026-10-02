# Lab 2 Lecture: Network & Routing — Fitting IPv6 Through a 127-Byte Door

**Duration**: 40 min (delivered before the hands-on lab)
**Audience**: Students about to run Lab 2 (Thread mesh on ESP32-C6, `firmware/lab2_mesh`)
**Pairs with**: [lab2.md](../lab2.md)
**Follows**: [Lab 1 Lecture](lab1_lecture.md) — students have seen the 127-byte frame and the RSSI-vs-distance curve.

---

## Learning goals

By the end of the lecture, students should be able to:

1. Explain why IPv6 cannot ride 802.15.4 unchanged, and what 6LoWPAN does about it (IPHC compression + fragmentation).
2. Classify a Thread node's IPv6 addresses (link-local, RLOC, ALOC, ML-EID) and predict which one to use for a given packet.
3. Describe the Thread role model (Leader, Router, REED, End Device, SED) and place each role in the Functional viewpoint.
4. Compute a Thread route from link qualities, and predict how fast the mesh heals when a Router dies (traffic-driven vs timer-driven detection).
5. Contrast Thread's address-based mesh routing with BLE Mesh flooding and Zigbee tree routing — and justify when each wins.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–8 min | Recap + ISO placement | Where Lab 2 lives in the Functional viewpoint; what changed from Lab 1. |
| 8–20 min | Thread stack layer of the week: 6LoWPAN + IPv6 addressing + MLE routing | How an IPv6 packet actually moves across a Thread mesh. |
| 20–32 min | Alternative stacks: BLE Mesh (flood) vs Zigbee (tree) | Same mesh problem, three different answers. |
| 32–40 min | Lab bridge | Preview the tractor test and the address-classification task. |

---

## Segment 1 — Recap + ISO placement (0–8 min)

### Callback to last week

Last week we ended on one slide: **80–100 bytes of payload after the 127-byte frame is done**. And a 40-byte IPv6 header eats half of that. Today we pay that bill.

Quick refresher — the 802.15.4 frame the IPv6 packet has to fit into. The **MHR (MAC Header)** is what eats the first ~9 bytes before any payload:

```
802.15.4 MHR (variable, typically 9–23 bytes)
 0                   1                   2
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 ...
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Frame Control (2B)  | Seq # | Addressing  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                                 │
                                 ▼
           ┌─────────────────────────────────────────────┐
           │ Dst PAN ID (2B) │ Dst Addr (2 or 8B)        │
           │ Src PAN ID (0 or 2B) │ Src Addr (2 or 8B)   │
           └─────────────────────────────────────────────┘
```

| MHR field | Size | Purpose |
|---|---|---|
| Frame Control | 2 B | Frame type, addressing mode, security flag, ACK request |
| Sequence Number | 1 B | For ACK matching and duplicate detection |
| Dst PAN ID | 0 or 2 B | Target PAN (omitted on intra-PAN short-address frames) |
| Dst Address | 2 or 8 B | Short (16-bit) or extended (EUI-64) |
| Src PAN ID | 0 or 2 B | Often compressed away |
| Src Address | 2 or 8 B | Short or extended |

So before IPv6 even appears, the MAC layer has already consumed ~9–23 bytes. **Everything after the MHR is where the IPv6 packet lives.** That's the room we're fighting over.

Here's what those 40 bytes actually look like — the standard IPv6 header as defined by RFC 8200:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Version| Traffic Class |           Flow Label                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|         Payload Length        |  Next Header  |   Hop Limit   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                                                               +
|                                                               |
+                         Source Address                        +
|                         (128 bits)                            |
+                                                               +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                                                               +
|                                                               |
+                      Destination Address                      +
|                         (128 bits)                            |
+                                                               +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                           40 bytes total
```

Ask the class: *"If IPv6 needs 40 bytes just for the header, and we have ~100 bytes total, how do we make this work?"* Do not answer yet. The two possible answers — **compress** or **fragment** — are what 6LoWPAN (RFC 6282 + RFC 4944) provides. Both.

### Where Lab 2 lives in ISO/IEC 30141

Draw the Functional viewpoint boxes on the board. Lab 1 was about the PED↔SCD boundary (radio waves, hardware). Lab 2 moves one step up the stack — the mesh itself lives inside **SCD**, and stable IPv6 addressing starts to touch **ASD (Application & Service Domain)** because that's how applications in later labs will reach devices.

> **Where RAID comes in**: RAID (Resource Access & Interchange) is where *external* consumers reach the IoT system through *authenticated* APIs and brokers — access management + interchange subsystem (Table A.3 prose). Lab 5's Border Router is the *plumbing* that makes outside reach possible (it's an SCD-hosted IoT gateway per Figure A.5), but RAID itself doesn't light up until **Lab 6** (DTLS as access management) and **Lab 7** (dashboard as interchange). Write RAID on the board in gray and keep it gray for three more labs.

### Functional roles — the table we'll fill today

| Thread role | ISO Functional role | Power profile | Radio duty |
|---|---|---|---|
| Leader | Network coordinator | Always on | 100% RX |
| Router | Forwarder | Always on | 100% RX |
| REED (Router-Eligible End Device) | Standby forwarder | Always on | 100% RX |
| End Device (FED) | Leaf, always-on | Always on | 100% RX |
| Sleepy End Device (SED) | Leaf, duty-cycled | Sleep most of the time | ~1% RX (poll interval) |

The **SED** row is the one that matters for the battery budget from Lab 1. Everything else keeps its receiver on and draws tens of mA continuously: 3000 mAh lasts days, not months. Only SEDs hit the 3-month target, which is why routers need mains or solar power.

---

## Segment 2 — Thread stack layer of the week: 6LoWPAN + MLE (8–20 min)

### Part A: 6LoWPAN header compression (IPHC)

First, where does the IPv6 header sit inside an 802.15.4 frame? This is the budget we're fighting:

```
802.15.4 frame (127 bytes max, on the wire)
┌──────┬──────────────────────────────────────────────────────────┬─────┐
│ MHR  │ Payload = 6LoWPAN dispatch + IPv6 hdr + next hdr + data  │ FCS │
│ ~9 B │                     ~116 B                               │ 2 B │
└──────┴──────────────────────────────────────────────────────────┴─────┘
                │
                ▼  zoom into payload with UNCOMPRESSED IPv6 + UDP
        ┌──────────┬─────────────┬─────────────┬─────────────┐
        │ IPv6 hdr │ UDP hdr     │ App payload │             │
        │  40 B    │   8 B       │  ≤ 68 B     │             │
        └──────────┴─────────────┴─────────────┴─────────────┘

                ▼  same payload with 6LoWPAN IPHC + NHC
        ┌───┬───┬─────────────┬───────────────────────────────┐
        │IP │UD │ App payload │  (reclaimed room)             │
        │HC │ P │  ≤ 110 B    │                               │
        │2-6│ 2 │             │                               │
        └───┴───┴─────────────┴───────────────────────────────┘
```

The insight of RFC 6282: **most IPv6 header fields are predictable inside a local link**, so don't send them. To see why, look at what's actually in the 40-byte header:

| Field | Size | Typical value in Thread | Compressible? |
|---|---|---|---|
| Version | 4 bits | Always `6` | Elide — always 6 |
| Traffic Class | 8 bits | Usually `0` | Elide when 0 |
| Flow Label | 20 bits | Usually `0` | Elide when 0 |
| Payload Length | 16 bits | Varies | Elide — derivable from 802.15.4 frame length |
| Next Header | 8 bits | Usually UDP (17) | Flag + use NHC for UDP |
| Hop Limit | 8 bits | Usually 1, 64, or 255 | Encode common values in 2 bits |
| Source Address | 128 bits | Link-local, derived from MAC | Elide — regenerate from L2 src |
| Destination Address | 128 bits | Link-local, derived from MAC | Elide — regenerate from L2 dst |
| **Total** | **40 B** | | **→ as little as 2 B** |

Compression targets, in order of savings:

1. **Addresses (32 bytes → as little as 0).** The 64-bit prefix is either `fe80::` or the mesh-local prefix that every node already holds as context 0, so it is never sent. The 64-bit interface ID is elided when the receiver can rebuild it from the MAC header: link-local IIDs come from the extended MAC address, RLOC IIDs from the 16-bit short address. An ML-EID's IID is random, so its 8 bytes go on the air. Students measure this difference in SOP-02.
2. **Version / Traffic Class / Flow Label (6 bytes → 0–1).** Always IPv6, usually no traffic class, usually no flow label. Compressible to a bitfield.
3. **Hop Limit (1 byte → 0).** Most packets use 64. When they don't, carry it.
4. **Next Header (1 byte → 0).** If the next header is UDP, flag it with one bit and compress UDP too (NHC).

```
Uncompressed IPv6:      40 bytes
Best-case IPHC:         2 bytes   (link-local, derived addresses, common values)
Typical IPHC in Thread: 4–6 bytes
```

Draw this on the board. Students should leave the session knowing the number **2** — the theoretical floor of IPHC — because it is the number that makes the 127-byte frame livable.

> **First-principles question to drop**: *"6LoWPAN compresses headers but not payload. Why?"* Answer expected: headers are predictable (known syntax, local context), payload is arbitrary. Payload compression is the application's job — that's what CBOR does in Lab 3.

### Part B: When compression isn't enough — fragmentation

Compression gets us back the header bytes, but some packets are still > 127 bytes total. Examples: a DTLS handshake record, an OTA firmware block, a large JSON diagnostic. For those, 6LoWPAN fragments.

```
┌──────────────────────────────────────┐
│ Frag-1: FRAG1 hdr (4B) + first chunk │  ─┐
├──────────────────────────────────────┤   ├─ reassembled by receiver
│ Frag-N: FRAGN hdr (5B) + next chunk  │  ─┘
└──────────────────────────────────────┘

Lose one fragment → the whole datagram is lost. RFC 4944 allows up to 60 s for
reassembly; OpenThread gives up after 2 s. Only the layer above can resend.
```

This is why the Lab 1 foreshadowing matters: **big packets are expensive on lossy radios**. The rule of thumb students should carry forward is "keep application payloads ≤ ~80 bytes after compression and you never fragment." This shapes Lab 3's CoAP/CBOR design.

### Part C: IPv6 addresses a Thread node carries

Students will run `ot ipaddr` in the lab and see 3–4 unicast addresses. They need a mental model for what each one is *for*, not just what it looks like.

| Address | Scope | Used for |
|---|---|---|
| **Link-local** `fe80::/64` | One radio hop | MLE between neighbours; IID = extended MAC with the U/L bit flipped |
| **Mesh-local EID (ML-EID)** `fdxx::/64` | Entire Thread mesh | Stable, device-identifying address for application traffic |
| **RLOC (Routing Locator)** `fdxx::ff:fe00:xxxx` | Entire Thread mesh | Encodes router ID + child ID; *changes* when topology changes |
| **ALOC (Anycast Locator)** `fdxx::ff:fe00:fcxx` | Entire Thread mesh | A role, not a device: `fc00` is whoever is leader |
| **Multicast** `ff02::1`, `ff03::1` | All-nodes (link-local / realm-local) | Broadcast-like behavior over mesh |

The trap: a student pings by RLOC, topology changes, and pings start failing — not because the network broke, but because the RLOC moved. **Application code should always target the ML-EID.** This is a real source of bugs in production Thread deployments.

### Part D: MLE and how the mesh actually routes

**MLE = Mesh Link Establishment**, Thread's signalling protocol (an IETF draft that Thread adopted; it is not an RFC). It runs over UDP on link-local addresses and does three things:

1. **Link measurement** — every received frame updates a per-neighbour RSS average. Link margin = RSS − noise floor, mapped to a **link quality (LQ) of 0–3**. Each side tells the other what it measures, so both know the two-way quality.
2. **Router ID assignment** — the Leader hands out router IDs (6 bits, 0–62) and keeps at most **32** active routers.
3. **Route propagation** — each router's MLE advertisement carries one entry per router: the link quality to it (if a neighbour) and the path cost to it. Distance-vector routing, compressed to a byte or so per router.

The numbers (from the Thread spec, as OpenThread implements them):

```
Link margin > 20 dB → LQ 3 → link cost 1
Link margin > 10 dB → LQ 2 → link cost 2
Link margin >  2 dB → LQ 1 → link cost 4
otherwise           → LQ 0 → no link
Two-way LQ = min(LQ in, LQ out)      Path cost = sum of link costs
```

Draw a 3-node mesh on the board. A–B and B–C are LQ 3 (cost 1 each), A–C direct is LQ 1 (cost 4). Ask: *"What's A's route to C?"* Answer: A → B → C, cost 2, beats the direct cost-4 link. **Hops are cheap, bad links are expensive.** This is exactly the topology students build in Lab 2 Part 3, using `ot macfilter rss add-lqi` to make the A–C link look like LQ 1.

### How fast does the mesh heal?

Two mechanisms detect a dead router:

1. **Traffic-driven:** every unicast frame asks for an ACK and is retried up to 15 times (Lab 1, SOP-01). After **4 consecutive frames** to a neighbouring router go unacknowledged, OpenThread drops that link and recomputes routes immediately.
2. **Timer-driven:** routers advertise on a Trickle timer, every 1 s right after a change and backing off to ~32 s when stable. A neighbouring router that stays silent for **100 s** is dropped even if nobody tried to send to it.

When a link disappears, the routers' advertisement timers reset to the fast end, so the new costs spread across the mesh in seconds.

> Tell students: with a ping running through the dead router, expect recovery within seconds: one lost ping per failed frame, four on each side. On the instructor bench (three ESP32-C6, 0 dBm, one desk) both runs lost exactly 8 pings at 1 ping/s. The 100 s timer is the worst case for a link nobody uses. Edwin's 2 minutes covers both. If they see > 2 min, check that a backup path exists at all (`ot router table`, `Link 1` to the far node).

---

## Segment 3 — Alternative stacks: BLE Mesh & Zigbee (20–32 min)

Same architectural problem (multi-hop delivery over constrained radios). Three different answers.

### BLE Mesh: managed flooding

No routing tables. **Every node that hears a message rebroadcasts it** (with a TTL). The network converges by saturation rather than computation.

- **Pros**: no routing state, trivially self-heals (any relay works), excellent for commissioning-light consumer devices (lights, locks).
- **Cons**: bandwidth scales badly — every packet touches every relay. Latency is bounded by TTL, not by topology. No native IP.
- **When it wins**: small dense networks where you don't care about bandwidth (smart lighting in one building).

### Zigbee: tree + mesh hybrid

Addresses are assigned hierarchically by the Coordinator using a **Cskip** formula. Routing follows the tree by default, falls back to AODV-style mesh discovery when the tree fails.

- **Pros**: deterministic address assignment, simple for small networks.
- **Cons**: tree addressing wastes address space, re-parenting is painful, not IP-native (application framework is proprietary).
- **When it wins**: legacy installations; new designs rarely pick Zigbee over Thread.

### The comparison table — write this on the board

| Axis | Thread (IP mesh) | BLE Mesh (flood) | Zigbee (tree+mesh) |
|---|---|---|---|
| **Routing model** | Address-based, distance-vector | Managed flood, TTL-bounded | Hierarchical tree + reactive mesh |
| **State per node** | Router table (≤32 entries) | None (just replay cache) | Routing + neighbor tables |
| **Scalability** | ~250 devices/network, 32 routers | ~100s but bandwidth dies | ~few 100s |
| **IP-native?** | Yes (IPv6 + 6LoWPAN) | No (custom addressing) | No (ZCL application layer) |
| **Self-heal time** | seconds with traffic; ≤ ~100 s idle | Immediate (next flood) | seconds to tens of seconds (route discovery) |
| **Best fit** | Sensor + actuator fleets needing IP | Dense consumer devices, low traffic | Legacy, specific vendor ecosystems |

### Why Thread won for GreenField

Two reasons, stated plainly:

1. **IP-native end-to-end.** A cloud service or a farmer's phone can address a sensor by its ML-EID. No translation layer, no proprietary gateway protocol. This becomes a decisive advantage once the Border Router is in place.
2. **Routing cost scales with topology, not with traffic.** On a 50-sensor field, BLE Mesh floods would saturate the air; Thread's routers forward only along computed paths.

> **Teaching hook**: "Thread didn't invent anything radical. It stapled IPv6 + 6LoWPAN + distance-vector routing to 802.15.4. The value is in the staple, not the parts." This reinforces the ISO/IEC 30141 message: reference architectures are about integration, not invention.

---

## Segment 4 — Lab bridge (32–40 min)

### What they are about to do

Walk through [lab2.md](../lab2.md) at high speed. Groups need **three boards**, so pairs team up.

1. **Setup (Part 1)** — flash `firmware/lab2_mesh`, form the network on A with `ot dataset init new`, copy the hex dataset to B and C, and wait until both are `router` (up to 2 min).
2. **Address classification (Part 2)** — `ot ipaddr`, classify each address into the table above, and check the two derivations: link-local IID from `ot extaddr`, router ID from `ot rloc16`.
3. **Two hops (Part 3)** — `ot macfilter rss add-lqi` makes the A–C link LQ 1, so A routes to C through B. B's MAC counters prove it. RTT for 1 vs 2 hops.
4. **Tractor test (Part 4)** — ping C from A once a second, unplug B, count the lost pings. Expect seconds.

**Bench reference** (instructor only; three ESP32-C6 on one desk, 0 dBm, 64-byte pings):
1-hop RTT ≈ 15 ms, 2-hop ≈ 31 ms; tractor test 8 pings lost (~8 s) in both runs; B relays
exactly 40 frames for 20 pings; one-frame limit 76 B of ping payload to an ML-EID and 88 B
to an RLOC (SOP-02).

### The puzzles to seed

Two this week. Don't answer either.

> *"Ping a Thread node by its RLOC. Then make it re-attach somewhere else. Ping the same RLOC. What happens, and why is the ML-EID the right address for applications?"*

> *"Thread forgets a silent neighbour after 100 seconds, yet your tractor test will recover in a few. What noticed the failure first? What would happen to a link that carries no traffic?"*

Answer to the second one (for your reference, not theirs): the missing MAC ACKs. Four failed frames remove the link, so failure detection costs nothing extra when traffic flows. An idle link relies on the advertisement timeout, and shortening it means more frequent advertisements from every router: more airtime, more energy, and less room for data. Detection speed is bought with duty cycle.

### Practical reminders

- Same channel, PAN ID and network key on all devices: `ot dataset init new` on A, `ot dataset active -x` to export, paste into B and C with `ot dataset set active <hex>`.
- Link quality is measured by the receiver. `LQ In` (what I hear) and `LQ Out` (what my neighbour hears from me) can differ for the same link.
- Turn radios off when idle. Shared spectrum, shared responsibility — same trustworthiness point from Lab 1.
- `ot dataset init new` draws a random PAN ID, extended PAN ID and network key, so two groups can't merge by accident. A key typed from a handout (`00112233…`) is how they would, and anyone who read the handout could join. That is a trustworthiness point worth making.
- Don't unplug the leader (A) in the tractor test. Leader loss is a different failure with a 120 s timeout; SOP-02 covers it.

### What Lab 3 will answer

> *"We have a mesh that routes IPv6. How do applications talk over it — and why not just use HTTP?"*

Preview: CoAP (RFC 7252) is HTTP's semantics repackaged for constrained networks — UDP, 4-byte headers, native observe/pub-sub. Read the CoAP intro before next class.

---

## Instructor checklist

- [ ] Board ready with the four-address table (link-local / ML-EID / RLOC / multicast).
- [ ] 6LoWPAN compression arithmetic visible (40 → 2 bytes).
- [ ] Link-quality → cost table and the 3-node triangle (LQ 3 / LQ 3 / LQ 1) drawn out.
- [ ] Groups of three boards arranged (pairs team up).
- [ ] A demo mesh running so students see the role LEDs (red → yellow → green, blue for the leader).
- [ ] Thread vs BLE Mesh vs Zigbee comparison table on the board during Segment 3.
- [ ] Live demo of `ot ipaddr` + `ot router table` on a running board before students start Part 1.
- [ ] Both puzzles posed and left unanswered at the end.

---

## References for students

- [lab2.md](../lab2.md) — the hands-on guide for today.
- [SOP-02: 6LoWPAN and Routing Experiments](../sops/sop02_6lowpan.md) — fragmentation threshold and leader loss on the same firmware.
- [2_iso_architecture.md](../../2_iso_architecture.md) — Functional viewpoint and domains.
- [5_theory_foundations.md](../../5_theory_foundations.md) §2–§3 — deeper first-principles on IPHC and mesh routing.
- RFC 6282 — 6LoWPAN IPHC compression (the one to actually read).
- RFC 4944 — 6LoWPAN fragmentation.
- Thread Specification v1.3 — §4 (MLE), §5 (routing).
- ISO/IEC 30141:2024 — Functional viewpoint, Annex on communication patterns.
