# Lab 5 Lecture: The Border Router — Where Four Networks Meet

**Duration**: 40 min (delivered before the hands-on lab)

**Audience**: Students about to run Lab 5 (Zephyr's OpenThread Border Router on an ESP32-S3 with PSRAM, driving an ESP32-C6 as RCP)

**Pairs with**: [lab5.md](../labs/lab5.md)

**Follows**: [Lab 4 Lecture](lab4_lecture.md) — students have `/env/temp` (uplink) and `/act/valve` (downlink) working on the Thread mesh from Lab 3, a real sensor behind `/env/temp` from Lab 4, and the question of what "reachable" means once the client leaves the mesh.

---

## Learning goals

By the end of the lecture, students should be able to:

1. Redraw the SoilSense system using the **two paired patterns from Annex A** of ISO/IEC 30141:2024 — *enterprise system pattern* (Table A.3 / Figure A.5: entities + IoT gateway) and *enterprise networking pattern* (Table A.4 / Figure A.6: proximity / access / services / user) — and locate where the OTBR sits in each.
2. Explain why the OTBR is **two physical boards** (Wi-Fi-only host + 802.15.4-only RCP) and what each one contributes.
3. Trace an IPv6 packet from a mesh node to the public internet, naming the **two address mechanisms** involved: SLAAC on the OMR (off-mesh routable) prefix the OTBR publishes, and **NAT64** through a /96 prefix (RFC 6052).
4. Reason about the **single-OTBR failure mode** — what survives, what doesn't — and articulate the "local-first" property of the SoilSense design.
5. Switch lenses: explain why ISO/IEC 30141 has more than the six Functional domains, and why "the Border Router is RAID" is *actually wrong* per Figure A.5 (the standard places "IoT gateway" inside **SCD**, not RAID — RAID hosts access management + interchange, which lights up in Labs 6–7).

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–10 min | The lens just changed | From domain ladder (Labs 1–4) to the A.3+A.4 pattern pair: entities + networks. |
| 10–22 min | The OTBR up close: two boards, two address translations | What the device actually does, byte by byte. |
| 22–32 min | Single-OTBR failure mode + alternative architectures (LoRaWAN gateway, BLE-via-phone) | What you bought with this choice, what you didn't. |
| 32–40 min | Lab bridge | Preview the four-network walk and Task C's latency table. |

---

## Segment 1 — The lens just changed (0–10 min)

### Callback to last week

Lab 3 solved Edwin's valve complaint: `/act/valve` opens reliably under loss because CON retransmits plus a sane SED poll period get the bytes there. Lab 4 put a real sensor behind `/env/temp` and made the node say when its data is stale. Both contracts are *production-grade inside the Thread mesh*.

But Daniela can't see any of it from the market. This week:

> *"My mesh is an island. How do I let the phone in?"*

Two questions to put on the board:

1. *"How many networks are between Daniela's phone and the soil sensor right now?"* — At least four, depending how you count. Thread mesh, the OTBR's Wi-Fi, the cloud provider's backbone, the carrier network. Each runs different protocols, different MTUs, different addressing.
2. *"Where do all of them meet?"* — One device. That's the lab.

### Why we stop drawing the domain ladder

Brief recap of the Lab 3 aside: ISO/IEC 30141 has **six viewpoints**, not just six domains. The six **domains** (PED / SCD / ASD / OMD / UD / RAID) are *one diagram, inside the Functional viewpoint*. Labs 1–4 climbed that ladder (PED → SCD → ASD), and the framing "Lab N is mostly domain X with a foot in domain Y" worked because every lab added one more application-stack layer to one physical device.

Today is different. Today's deliverable spans **four networks** and **multiple physical devices**, and the question "which domain is the OTBR?" has a clean answer that students often guess *wrong*. The intuitive answer — "RAID, because RAID is about reaching outside the system" — is incorrect by the standard's own Figure A.5: that figure places the **"IoT gateway" box inside SCD**, and the Table A.3 prose confirms it (*"IoT gateways are devices which connect SCD with other domains"*). RAID is a separate domain that fronts the *ASD/OMD capabilities* to outside consumers via access management + interchange — closer to a cloud-side API layer than to a Border Router. So the OTBR is an **SCD-hosted IoT gateway**. RAID stays gray on the board for one more lab.

Even with that fixed, the domain map isn't the most useful framing for the lab. Today's diagram has **four** named networks (proximity / access / services / user) connecting **six** entity domains with an IoT gateway sitting on the seam — that's a different chart from "where does the code live." The standard provides two charts designed exactly for this question, as a pair.

Put the comparison table on the board:

| Question | Useful lens | Why |
|---|---|---|
| "Where do `/env/temp` and `/act/valve` live?" (Lab 3–4) | Functional viewpoint → **domain map** (Figure A.5) | One device, application stack growing upward |
| "What kind of *device* is the OTBR?" (Lab 5) | **Enterprise system pattern** (Table A.3 / Figure A.5) | The standard names "IoT gateway" with its functions |
| "How does Daniela's phone reach `/env/temp`?" (Lab 5) | **Enterprise networking pattern** (Table A.4 / Figure A.6) | Four named networks, packets crossing each in turn |
| "Is it secure end-to-end?" (Lab 6 preview) | **Trustworthiness viewpoint** | Cross-cuts every domain; not a place in the diagram |
| "Who watches the dashboard?" (Lab 7 preview) | **Usage viewpoint** + Table A.5 (usage pattern) | Roles and lifecycle, not topology |

The point: **the standard gives you several charts, and you pick the one that answers the question you're holding.** Don't tag everything as "the domain it lives in" forever — it stops being useful exactly when the question gets architectural. **A.3 and A.4 are designed together** — A.4's information row literally says *"the IoT enterprise networking pattern is using the IoT enterprise system pattern."* You cite them as a pair.

> **Drawing for the board (the new chart):** four boxes left-to-right labeled Proximity / Access / Services / User. The OTBR straddles the proximity/access boundary. S and C are inside Proximity. The phone is inside User. Draw arrows for one full path: S → OTBR (radio side) → OTBR (Wi-Fi side) → hotspot → cloud → carrier → phone.

### Where Lab 5 lives in ISO/IEC 30141 — the A.3 + A.4 pair

**Step 1: read out the IoT-gateway definition from Table A.3 (the enterprise system pattern).** Project it on the board verbatim, because every line lands on the lab:

> *"IoT gateways are devices which connect SCD with other domains. IoT gateways provide functions such as protocol conversion, address mapping, data processing, information fusion, certification, and equipment management."*
> — ISO/IEC 30141:2024 §A.4, Table A.3

Walk down the six function names and tick four of them on the SoilSense OTBR:

| Function (Table A.3) | OTBR concretely does … | Where in the lab |
|---|---|---|
| Protocol conversion | NAT64 (IPv6 ↔ IPv4); none for CoAP itself (same bytes both sides) | SOP-05 §5 |
| Address mapping | SLAAC on the OMR prefix; the NAT64 /96 prefix in the network data | SOP-05 §2–3, §5 |
| Data processing | *(none — the OTBR forwards, doesn't aggregate; Lab 7 problem)* | — |
| Information fusion | *(none — same reason)* | — |
| Certification | Thread commissioning trust anchor (network key, PSKc in the dataset) | SOP-05 §2 |
| Equipment management | `ot` shell: child and router tables, dataset, prefixes | SOP-05 §2–3 |

Four of six. That's the point — **the standard already wrote down what this device does**; the lab is one concrete implementation. Cite this exact mapping in the DDR.

**Step 2: redraw the SoilSense system using Table A.4 / Figure A.6 (the networking pattern).** Four networks, four boxes, OTBR straddling the proximity/access boundary:

```
Enterprise networking pattern (Table A.4 / Figure A.6):
    [Proximity]     [Access]       [Services]      [User]
       │              │               │              │
   Thread mesh    Wi-Fi/Ethernet   Cloud APIs   Phone/Browser
       │              │               │              │
       └──────┬───────┘               │              │
              │                       │              │
            OTBR  ────────────────────┴──────────────┘
        (the "IoT gateway" of Table A.3, sitting on a network boundary)
```

The OTBR isn't *in* a single network — it's **on the boundary between two of them** (proximity and access) and the rest of the chain follows. The standard pre-anticipated exactly this: A.4 (networking) is defined as *using* A.3 (system).

If you place this in the **Functional viewpoint's six-domain map** (Figure A.5): the OTBR is an **SCD-hosted IoT gateway**, *not* a RAID device. Figure A.5 draws the "IoT gateway" box inside the SCD; the Table A.3 prose says IoT gateways *"connect SCD with other domains."* This is the standard's stated home for it. **RAID** (access management component + interchange subsystem) is where authentication and capability-exposure-to-outside-consumers lives — that's a Lab 6 (DTLS as access management) and Lab 7 (dashboard's exposed APIs as interchange) story. The OTBR *extends* SCD outward toward those other domains; it doesn't *become* them. Cite Figure A.5 explicitly in the DDR so this stays straight.

Use the A.3 + A.4 pair as the lab's primary deliverable; the domain-map answer is "SCD, by the standard's own diagram."

> **Two-minute caution about the aside in the Lab 3 lecture:** the aside promised the dominant lens would shift around Lab 5. This is the shift. Don't let students conclude "domains were wrong" — domains were the right lens for Labs 1–4 because the question those labs were holding was "where in the application stack are we adding code?" The question today is "across how many networks does a packet travel, and what crosses each boundary?" — and that question has its own chart. **Same standard, different chart.**

---

## Segment 2 — The OTBR up close (10–22 min)

### Part A: Why the Border Router is two boards

The naive expectation: "buy a board with Wi-Fi *and* Thread, run OTBR on it." That board exists (Nordic nRF7002 + nRF52840 module, some Silicon Labs combos), but the *software architecture* of OTBR is built around the **NCP/RCP model**, not a single-chip stack. Worth a board sketch:

```
   ┌──────────────────────────────┐        ┌────────────────────┐
   │  Host (ESP32-S3, Zephyr)     │        │  RCP (ESP32-C6)    │
   │                              │ UART   │                    │
   │  - OpenThread Border Router  │ Spinel │  - 802.15.4 PHY    │
   │  - NAT64 (software)          │ <───>  │  - 802.15.4 MAC    │
   │  - `ot` CLI (mgmt surface)   │ 460800 │  - Just a "modem"  │
   │  - Wi-Fi / Ethernet driver   │        │  - No CoAP, no app │
   │                              │        │                    │
   │  Wi-Fi  <──>  AP             │        │  Radio  <──>  Mesh │
   └──────────────────────────────┘        └────────────────────┘
        ^                                       ^
        │                                       │
        IPv6 + NAT64 + RA                       IEEE 802.15.4 frames
```

Three things students should leave with:

1. **The RCP is dumb on purpose.** It has no CoAP stack, no IP stack, no application logic. It hands raw 802.15.4 frames up over Spinel/UART and the host does everything else. This means upgrading the host's OTBR is easy (it's the host's firmware); the RCP almost never changes.
2. **The host's CPU does the IPv6 work.** 6LoWPAN decompression, mesh route lookup, NAT64 translation, Router Advertisement on the Wi-Fi side — all on the host. The RCP-C6 just transmits/receives bytes.
3. **One device, from the network's point of view.** The mesh sees one Thread node (the OTBR); the Wi-Fi AP sees one Wi-Fi client (the OTBR). The two MCUs inside are an *implementation detail*. A Raspberry Pi running `ot-br-posix` with a USB RCP is the same architecture with a different host.

> **First-principles question to drop:** *"Why doesn't the RCP just run an IP stack itself and forward via TCP/UDP to the host?"* Expected: latency through the link (Spinel/UART is microseconds; TCP framing would add milliseconds and dropped-packet recovery), and the upgrade story (NCP-mode RCPs *do* run an IP stack; they're harder to update because the host can't see what's wrong). RCP mode is the architecturally cleanest split and what Thread Group standardized on.

### Part B: The two address translations

This is the technical heart of the lecture. Two questions, two answers.

#### B.1 — How does the mesh get an address the outside can reach?

Before the OTBR, every node had only mesh-local addresses (`fd<random>::…`, valid only inside the mesh). Once the OTBR runs, **three things happen**:

```
1. The OTBR publishes an OMR (off-mesh routable) prefix in the Thread
   Network Data, with flags  paros  = preferred, SLAAC, default route,
   on-mesh, stable:
       2800:484:9080:855e::/64 paros med a000     (home router, delegated)
       fdab:819c:92ef:1::/64                      (phone hotspot: the OTBR's own ULA)

2. Every node sees the prefix in the Network Data and builds itself an
   address in it (SLAAC, RFC 4862) with an opaque interface ID. On S:

       2800:484:9080:855e:a683:e5fc:fe92:bf6   ← OMR address (new)
       fdd7:c9f8:19bb:c91:0:ff:fe00:a001       ← RLOC (the ::ff:fe00: form)
       fdd7:c9f8:19bb:c91:e176:7bb0:393c:7fb6  ← mesh-local EID (unchanged)
       fe80::…                                 ← link-local

3. On Wi-Fi, the OTBR sends Router Advertisements carrying a Route
   Information Option (RFC 4191) for that prefix, so laptops on the
   same Wi-Fi learn "OMR prefix via the OTBR".
```

**Two important consequences:**

- **No new resource needed at the OTBR.** The OTBR doesn't proxy `/env/temp`: it publishes a prefix and routes packets. Same bytes, new path.
- **The OTBR is a router, not a proxy.** It forwards IPv6 datagrams; it doesn't terminate connections, parse CoAP or translate JSON↔CBOR. (A CoAP↔HTTP proxy on top is a separate thing, and a Lab 7 topic.)

> **Teaching hook:** "If you've seen a home router hand your laptop an IPv6 prefix, this is the same idea on the 802.15.4 side. The OTBR is an IPv6 router that happens to have an 802.15.4 radio."

#### B.2 — How does an IPv6-only mesh reach the IPv4 internet?

Most of the public internet is still IPv4-only. Thread nodes are IPv6-only. Bridge: **NAT64** (RFC 6146), with an IPv4 address embedded in the last 32 bits of a /96 prefix (RFC 6052). The IETF reserves the well-known `64:ff9b::/96`; OpenThread uses its own ULA /96 unless the network offers one, and publishes it as a route in the Network Data.

Walk through it on the board, with Lab 5's real output:

```
S runs  ot ping 8.8.8.8

1. The shell synthesizes an IPv6 address from the NAT64 route in the
   Network Data (fdab:819c:92ef:2:0:0::/96):
       Pinging synthesized IPv6 address: fdab:819c:92ef:2:0:0:808:808
                                                           └──┬──┘
                                                  8.8.8.8 = 0x08 0x08 0x08 0x08
2. The packet reaches the OTBR, which runs NAT64:
       - src: IPv6 → the OTBR's IPv4 on Wi-Fi (from the hotspot's DHCP)
       - dst: last 32 bits → 8.8.8.8
3. The reply comes back to the OTBR's IPv4; NAT64 reverses the mapping.
```

The NAT table maps `(IPv6 src, port) ↔ (IPv4 src, port)`, the same idea as a home router's NAT44 plus a protocol-conversion step. Task E measures what the whole round trip costs; ask the room beforehand which hop they expect to dominate.

> **First-principles question to drop:** *"NAT64 lets IPv6 reach IPv4. What about the reverse — could an IPv4-only phone reach our IPv6-only sensor?"* Expected: not directly. You'd need **464XLAT** (CLAT on the phone side) or a CoAP↔HTTP proxy that terminates IPv6 on one side and IPv4 on the other. This is why most "IoT cloud" architectures put an HTTP/MQTT broker on the access side, a topic for Lab 7.

### Part C: What the bytes look like crossing the boundary

The crucial property: **the CoAP/CBOR payload doesn't change.** Six bytes for `/env/temp`, four bytes for `/act/valve`, identical on both sides of the OTBR. Draw this:

```
Inside mesh:   [802.15.4 hdr][6LoWPAN/IPHC][UDP][CoAP][CBOR a16174f9...]
                ~10–15 B       ~5 B           8 B   ~12 B   6 B

OTBR Wi-Fi side: [Eth/802.11 hdr][full IPv6][UDP][CoAP][CBOR a16174f9...]
                  ~30 B            40 B       8 B   ~12 B   6 B

                                              └────────┬────────┘
                                              identical bytes, identical app
```

What grew: the **link-layer + IPv6 headers** expanded because Wi-Fi doesn't have 6LoWPAN's IPHC compression. The application payload is byte-identical. This is *why* CoAP is a useful choice for IoT — it doesn't break when it leaves the constrained network. (Contrast: a custom 4-byte binary protocol would need a translator at the boundary. CoAP just routes.)

---

## Segment 3 — Single-OTBR failure mode + alternative architectures (22–32 min)

### Part A: What happens when the OTBR dies

Kill the OTBR (pull power on the host, or `ot thread stop`) and ask what survives:

| What still works | Why |
|---|---|
| C (in-mesh) → S `coap get /env/temp` | All inside Proximity; the OTBR was never on the path. |
| C → S `coap put /act/valve` | Same. Edwin in the field, with a node in hand, can still open the valve. |
| Mesh self-healing if a Router dies | Lab 2 property; OTBR isn't a Router for that purpose. |

| What stops working | Why |
|---|---|
| Daniela's phone reaching `/env/temp` | The Proximity↔Access boundary is gone. |
| S → `ot ping 8.8.8.8` | NAT64 lived on the OTBR. |
| The BR's `ot` CLI / `ot child table` view | Obviously — the host is off. |
| New nodes joining via OTBR-side commissioning | But existing dataset works; you can re-commission from an in-mesh Joiner. |

This is the **local-first property** of SoilSense: **the system degrades gracefully** when the off-mesh path disappears. That's not an accident; it's a consequence of choosing Thread + CoAP. The valve isn't waiting for the cloud to tell it to open — the cloud is just a viewer.

> **Compare to a hypothetical Wi-Fi-only SoilSense** where every sensor connects to AWS IoT directly: if the Wi-Fi router dies, *every sensor* is offline, even C sitting next to S. The mesh + OTBR architecture isolates field failures from cloud failures. This is the single best argument for Thread in this lab and worth driving home.

**Production answer:** **two OTBRs** on the same mesh. Both publish their routes in the Network Data, so when one stops, the mesh keeps the other's. We don't deploy two for this lab (the pilot has one), but ADR-005 should call out the single OTBR as a *pilot* compromise; Lab 8 returns to it.

### Part B: Other gateways — same role, different protocols

The OTBR is one instance of the **gateway pattern**. Other constrained-network stacks solve the same problem differently:

| Stack | The "OTBR equivalent" | Where it sits |
|---|---|---|
| **Thread / 6LoWPAN** (this lab) | OpenThread Border Router | Mesh ↔ IP (transparent, IPv6 native) |
| **LoRaWAN** | LoRaWAN Gateway + Network Server (TTN, ChirpStack) | Mesh-less star ↔ MQTT/HTTP (translates at app layer) |
| **BLE Mesh** | A phone or hub running a "provisioner" + cloud bridge | Mesh ↔ BLE GATT proxy ↔ phone/cloud |
| **Zigbee** | Zigbee Coordinator + bridge (Hue Bridge, SmartThings Hub) | Mesh ↔ HTTP/MQTT (translates at app layer) |
| **Matter (smart-home superset)** | A "Border Router" *that's literally a Thread BR* for the Thread fabric, plus mDNS/IPv6 for the Wi-Fi fabric | Same as Thread, plus discovery |

Two observations students should leave with:

1. **The Thread choice gives you IPv6 end-to-end.** The OTBR is a *network-layer* bridge — no application-layer translation. LoRaWAN, Zigbee, and most non-IP IoT stacks make you translate at the application layer (a LoRa packet has nothing to do with a CoAP request; the gateway's job is to *interpret*, not just *forward*). The Matter story is "IPv6 everywhere," for exactly this reason.
2. **The choice cascades.** Pick LoRaWAN, and your "OTBR" is a Linux box running a network server, and your "API" is whatever HTTP/MQTT contract that network server exposes — *not* CoAP. Pick BLE-via-phone, and your gateway is the user's phone, and the system stops working when the phone is in airplane mode. Pick Thread + OTBR (you did), and your CoAP contract from Labs 3–4 keeps working unchanged on the cloud side.

> **Teaching hook:** "You picked Thread in Lab 1, before you knew what an OTBR was. Today is the day you find out *what you bought*: end-to-end IPv6 with no application-layer translator. That's the difference between SoilSense and a LoRaWAN equivalent. It's not better in every dimension — LoRaWAN reaches 10 km on a battery — but it's structurally different in one important way: the bytes don't change at the boundary."

---

## Segment 4 — Lab bridge (32–40 min)

### What they are about to do

Walk through [lab5.md](../labs/lab5.md) at high speed:

1. **Tasks A–C — build it.** Wire and flash the S3 and its RCP, `wifi connect`, form a network on the assigned channel, and watch border routing start by itself (`ot br state`). Move S and C over with `ot factoryreset` and the dataset, and find the new OMR address in `ot ipaddr`. [SOP-05 §1–3](../labs/sops/sop05_border_router.md#1-wire-and-flash-the-two-boards).
2. **Task D — reach S from outside.** The laptop route the RA installed, the Wi-Fi hop with power save on and off, laptop → S by ping and by CoAP, and the dashboard on a phone.
3. **Tasks E–F — the edges.** `ot ping 8.8.8.8` through NAT64, then unplug the OTBR and open the valve from C. The table in the lab's *What you'll measure* is the headline.

### Practical reminders

- **Hotspot on 2.4 GHz and WPA2.** The S3 has no 5 GHz radio, and a WPA3-only hotspot won't connect.
- **The RCP is a third C6.** S and C keep their Lab 4 roles; plug the RCP in before the S3, or the S3 browns out.
- **Wi-Fi at 5 GHz only will not work.** ESP32, S3, and C6 are all 2.4 GHz. If your AP is dual-band, force the host onto the 2.4 GHz SSID — or run a phone hotspot at 2.4 GHz.
- **`ot factoryreset` before `ot dataset set active`** on S and C. Otherwise a node tries to restore its Lab 4 router role and can found a partition of its own.
- **There is no web UI.** Management is the `ot` shell on the S3's console, same as Labs 2–4, and it has no authentication: whoever holds the USB cable controls the OTBR. Fine for the lab, a production gap to flag in the DDR.

### The puzzles to seed

Two this week. Don't answer either.

> *"You verified `ot ping 8.8.8.8` works from S. You then disconnect the OTBR from Wi-Fi (leave it powered). What stops first, and why is it more than the ping?"*

> *"Daniela wants the dashboard to show data from 200 sensors deployed across three fields. Each field has one OTBR. The dashboard is a phone app, hitting `coap://[<prefix>:ff:fe00:N]/env/temp` for each sensor. What's the first thing that breaks at this fleet size, and why is it a property of the gateway pattern, not of the cloud?"*

The first puzzle is the **NAT64 vs prefix-advertisement** distinction: the ping fails because NAT64 lives on the OTBR's Wi-Fi side, but the laptop also loses S's OMR address, because the route to it came from the OTBR's Router Advertisements on Wi-Fi. Mesh-local addresses keep working inside the mesh.

The second puzzle previews **fleet-scale gateway problems**: a phone hitting 200 distinct IPv6 addresses opens 200 sockets, holds 200 CoAP exchange states, and triggers 200 separate Observe registrations. The gateway pattern doesn't scale to fleets — *that* is what you need a cloud broker / aggregator for, which is exactly Lab 7's territory.

### What Lab 6 will answer

> *"Our `/env/temp` and `/act/valve` are now reachable from the public internet through the OTBR. Anyone on the same Wi-Fi who knows the OMR address can read sensor data and command the valve. How do we put a lock on the door without killing battery life?"*

Preview: the lens shifts *again* — from networking pattern to the **Trustworthiness viewpoint** (cross-cutting, not a domain). DTLS over CoAP, pre-shared keys vs certificates, the energy cost of the handshake, the §9 trustworthiness audit in the DDR. The Border Router stays where it is; we're adding a lock to the bytes, not changing the path.

---

## Instructor checklist

- [ ] Domain ladder → A.3 + A.4 pattern pair transition explained explicitly (segment 1). Don't let students think Labs 1–4 were "wrong."
- [ ] Table A.3 "IoT gateway" quote on the board verbatim; the five-of-six function mapping table walked through.
- [ ] Four-network chart (Proximity / Access / Services / User) drawn on the board with the OTBR straddling Proximity/Access.
- [ ] Two-board OTBR architecture sketch (Wi-Fi-only host + C6 RCP + Spinel/UART) drawn out.
- [ ] SLAAC walk: prefix advertisement → node gets second IPv6 → `ipaddr` shows both.
- [ ] NAT64 worked example: `fdab:819c:92ef:2::808:808` ↔ `8.8.8.8`, and where the /96 comes from.
- [ ] Byte diagram showing identical CBOR payload on both sides of the OTBR.
- [ ] Single-OTBR failure-mode table (what survives, what doesn't) on the board.
- [ ] Comparison row: Thread/OTBR vs LoRaWAN/gateway vs BLE-via-phone vs Zigbee/coordinator.
- [ ] Both puzzles posed and left unanswered.
- [ ] One live demo: the dashboard on a phone, reading S through the OTBR with the same `a16174f9…` bytes C sees in-mesh, and opening the valve. This is the moment the lab clicks.

---

## References for students

- [lab5.md](../labs/lab5.md) — the hands-on guide for today.
- [SOP-05: Border Router Deployment](../labs/sops/sop05_border_router.md) — RCP/host flash and the latency table.
- [theory_foundations.md](../docs/theory_foundations.md) §5 — Border Router, NAT64.
- [iso_architecture.md](../docs/iso_architecture.md) — the Functional viewpoint and the six-domain map (which you now know is one chart among several).
- ISO/IEC 30141:2024 — §A.4 / **Table A.3** / Figure A.5 (IoT enterprise system pattern — names the "IoT gateway" and its six functions); §A.5 / **Table A.4** / Figure A.6 (IoT enterprise networking pattern — proximity / access / services / user); §6.2.2.3.3 (functional/management plane separation).
- RFC 4862 — IPv6 Stateless Address Autoconfiguration (SLAAC).
- RFC 6052 — IPv6 addressing of IPv4/IPv6 translators (/96 prefixes, the well-known `64:ff9b::/96`).
- RFC 4191 — Route Information Option in Router Advertisements.
- RFC 6146 — NAT64.
- [Zephyr's OpenThread Border Router sample](https://docs.zephyrproject.org/latest/samples/net/openthread/border_router/README.html) — what `firmware/lab5_border_router` is built from.
- Thread Specification v1.3 — §5 (Border Router behavior).
