# Lab 1 Lecture: Physical & Link Layers — Why Radio Choice Shapes Everything Above It

**Duration**: ~50 min (delivered before the hands-on lab; Segment 6 can be cut to fit 45)
**Audience**: Students who finished the Lab 0 HTTP and MQTT builds, about to run Lab 1
**Pairs with**: [lab1.md](../lab1.md)

---

## Learning goals

By the end of the lecture, students should be able to:

1. Place their Lab 0 system and the Thread system on the same layered stack, and say which layers change and why.
2. State what any PHY and any MAC are responsible for, and compare Wi-Fi, 802.15.4, BLE and LoRa on those terms.
3. Describe the 802.15.4 PHY (O-QPSK, DSSS, channels) and MAC (CSMA-CA, ACK/retry, 127-byte frame) with numbers.
4. Name the Thread device roles they will see in the lab (leader, router, child) and what Thread adds on top of 802.15.4.
5. Place the PED/SCD boundary and fill the Component Capabilities table for their board.
6. Predict what they will see in the lab (noise floor, RSSI drop with distance, PER threshold) before touching hardware.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–8 min | From Lab 0 to Thread | Same capabilities, new stack; review Lab 0 on the way |
| 8–14 min | ISO/IEC 30141 focus | Where does "the air" end and "the device" begin? |
| 14–24 min | PHY and MAC in general | What every radio has to decide, four radios compared |
| 24–34 min | 802.15.4 PHY + MAC | The radio this course uses, with numbers |
| 34–40 min | Thread on top | Roles and what Thread adds to 802.15.4 |
| 40–44 min | LoRaWAN contrast | Same role, different physics (cut first if short) |
| 44–50 min | Lab bridge | What they'll measure, and the puzzle to seed |

---

## Segment 1 — From Lab 0 to Thread (0–8 min)

### Review questions (3 min)

Quick-fire on what they just built; each answer points at today's topic.

1. *"In the HTTP lab the dashboard needed the node's IP address. In the MQTT lab the node needed the broker's. Why the flip?"* — Who opens the connection. An HTTP server waits to be called; an MQTT client dials out. Constrained nodes usually dial out.
2. *"Why QoS 0 for telemetry but an acknowledged QoS 1 for commands?"* — A lost reading is replaced by the next one; a lost command is not. Reliability is chosen per message type, not per system.
3. *"What kept the MQTT connection alive between publishes, and what did the radio do in the meantime?"* — Keepalive pings over TCP, and a Wi-Fi radio that stayed associated to the AP the whole time. That is the part the battery can't afford.

### Two stacks side by side (5 min)

Draw this on the board and leave it up all session:

```
                Lab 0 (built)                 Labs 1–8 (Thread)
Application     HTTP / MQTT                   CoAP              ← Lab 3
Transport       TCP                           UDP
Network         IPv4 (DHCP from the AP)       IPv6              ← Lab 2
Adaptation      —                             6LoWPAN           ← Lab 2
MAC             802.11 MAC                    802.15.4 MAC      ← today
PHY             802.11 OFDM, 20 MHz           802.15.4 O-QPSK   ← today
Topology        star around the AP            mesh
```

What stays: the sensing and actuating capabilities, the ISO domains, the request/response vs publish/subscribe choice (CoAP offers both: GET and Observe). What changes: every layer below the application, and the reason is the energy budget — ~4.2 mW average for 3 months on 2× AA. Today is the bottom two rows.

> **Teaching hook**: "You already know the top of this stack. The course walks down to the radio and back up, one layer per lab."

---

## Segment 2 — ISO/IEC 30141 focus (8–14 min)

### PED vs SCD, drawn on the board

Two boxes. Left: **PED (Physical Entity Domain)** — the physical world the system observes or affects. Right: **SCD (Sensing & Controlling Domain)** — the devices that bridge physical and digital.

Ask: *"Where does the ESP32-C6 live? Where does the RF link live?"*

- ESP32-C6 chip, antenna, radio → **SCD**
- Radio waves, Wi-Fi interference, vegetation blocking the signal → **PED** (the electromagnetic field is a physical phenomenon)
- The antenna is the boundary: it converts SCD bits into PED waves and back.

This goes into DDR Section 4 after the lab. The standard calls this link **Proximity Networking**.

### Component Capabilities model (Fig 8 / Tables 9-10)

Five categories on the board: **Transducer** (sense/actuate), **Data** (process, store, transfer), **Interface** (network, application, human), **Supporting** (time sync, security, power management), **Latent** (present but unused).

Emphasize **latent**. In Lab 0 the C6's Wi-Fi radio was active; in Lab 1 it becomes latent and the 802.15.4 radio becomes active. Same board, different capability table.

> **Teaching hook**: "If next semester the client asks for BLE commissioning, you won't need new hardware — you'll activate a latent capability."

---

## Segment 3 — PHY and MAC in general (14–24 min)

### What each layer is responsible for

- **PHY** turns bits into a waveform on a channel and back. Its knobs: frequency band, channel width, modulation, TX power, receiver sensitivity. The outcome is a trade between data rate, range and energy per bit.
- **MAC** decides who transmits when, frames and addresses the bits, detects corruption (FCS checksum) and recovers losses (ACK + retry). Its knobs: channel access scheme, maximum frame size, addressing, retry policy.

### Four radios on the same axes

Put this table up. Wi-Fi is the anchor because they just used it.

| | Wi-Fi 4 (2.4 GHz) | 802.15.4 (2.4 GHz) | BLE | LoRa / LoRaWAN |
|---|---|---|---|---|
| Where they meet it | Lab 0 | Labs 1–8 (Thread) | phones, wearables | long-range telemetry |
| Band | 2.4 GHz | 2.4 GHz | 2.4 GHz | sub-GHz (915 MHz in the Americas) |
| Channel width | 20 MHz (only 1/6/11 don't overlap) | 2 MHz, 16 channels | 2 MHz, 40 channels | 125–500 kHz |
| Modulation | OFDM, BPSK…64-QAM | O-QPSK + DSSS | GFSK | chirp spread spectrum |
| PHY rate | up to 72 Mbps (1 stream) | 250 kbps | 1 Mbps (2M, coded 125/500k) | ~0.3–22 kbps |
| Channel access | CSMA/CA, AP-centred | CSMA-CA, ACK + retries | scheduled connection events + frequency hopping | ALOHA: send when ready, duty-cycle limited |
| Max frame | ~2300 B (1500 B IP MTU) | 127 B | 27 B (251 B with data-length extension) | tens to ~200 B, by region and data rate |
| MAC address | 48-bit | 64-bit extended / 16-bit short + PAN ID | 48-bit | 32-bit DevAddr |

Three MAC families to name out loud: **contention** (Wi-Fi, 802.15.4: listen, then talk), **scheduling** (BLE connections: agree on when to meet, sleep in between) and **ALOHA** (LoRaWAN: just talk, and accept collisions because traffic is rare).

### Worked example: airtime of one frame

Same question for each radio: how long is the transmitter on?

- **802.15.4**, largest frame: 6 B of preamble/SFD/length + 127 B = 133 B × 32 µs/B = **4.3 ms**.
- **Wi-Fi**, 1500 B at 72 Mbps: ~0.17 ms of data + preamble ≈ **0.2 ms**. More than 10× the payload in 1/20 of the time.
- **LoRaWAN** SF12/125 kHz, 51 B of payload: ≈ **2.8 s**. Under a 1 % duty-cycle rule (EU868) the node must then stay silent for ~4.6 minutes.

Ask: *"Wi-Fi is the fastest by far. Why is it the worst for our battery?"* — Airtime is not the cost that matters. A Wi-Fi node that sleeps has to re-associate and redo DHCP when it wakes, often a second or more of radio-on time to send a few bytes; one that stays associated listens to AP beacons all day. 802.15.4 was built to wake, send one small frame and sleep.

---

## Segment 4 — 802.15.4 PHY + MAC (24–34 min)

### The PHY: why 2.4 GHz + O-QPSK + DSSS

1. **O-QPSK** (Offset Quadrature Phase-Shift Keying) — the Q stream is delayed by half a pulse, so I and Q never change together and the phase never jumps 180°. With 802.15.4's half-sine pulses the envelope is constant. That allows a non-linear power amplifier (70–80 % efficient) instead of a linear one (30–40 %). *About double the battery life for free.* See [O-QPSK](https://www.youtube.com/watch?v=lDSzyEQKE6o).

2. **DSSS** (Direct Sequence Spread Spectrum) — each 4-bit symbol is sent as one of 16 32-chip sequences: 2 Mchip/s carries 250 kbps, 8 chips per bit, ≈ **9 dB of processing gain**. The receiver correlates against the 16 known sequences, so a few corrupted chips still decode to the right symbol. This is why an 802.15.4 link survives next to a much louder Wi-Fi transmitter.

3. **2.4 GHz, channels 11–26** — 16 channels, 2 MHz wide, 5 MHz apart: channel *k* is centred at 2405 + 5·(*k* − 11) MHz. The band is license-free worldwide, which is also why it's crowded.

> Draw the band with Wi-Fi 1/6/11 (20 MHz each) over channels 11–26. Wi-Fi 1 covers 11–14, Wi-Fi 6 covers 16–19, Wi-Fi 11 covers 21–24. Circle 15, 20, 25 and 26: they fall in the gaps. This is the picture to have in mind during `ot scan energy`.

### The MAC: CSMA-CA, ACK/retry, and the 127-byte frame

**CSMA-CA** (unslotted, as Thread uses it), with the real numbers:

1. Wait a random backoff: 0–7 slots of 320 µs (0–2.24 ms).
2. Listen for 128 µs (CCA). Energy above threshold → busy → double the backoff window (up to 0–31 slots) and go to 1.
3. Five busy checks in a row → give up (channel access failure).
4. Clear → transmit.

Ask: *"Ethernet detects collisions (CSMA/CD). Why can't a radio?"* — A half-duplex radio can't hear while it transmits, so it can't detect a collision. It can only avoid one, and learn about it afterwards from a missing ACK.

**ACK and retry**: every unicast frame requests an ACK. No ACK → back off and retransmit. The 802.15.4 default is 3 retries; **OpenThread uses 15**. Upper layers never see most losses. The PER students measure with `ot ping` in the lab is what's left *after* up to 16 attempts — [SOP-01](../sops/sop01_advanced_mac.md) makes them measure the difference.

**The 127-byte frame** — the number to memorize.

```
┌─────────────────────────────────────────────────────────┐
│ 802.15.4 frame: 127 bytes total                         │
├─────┬───────────┬──────────────────────────────┬────────┤
│ MHR │ Sec hdr   │ Payload                      │ FCS    │
│ ~9B │ 0–14B     │ ≤104B (less with security)   │ 2B     │
└─────┴───────────┴──────────────────────────────┴────────┘
```

After MAC header, security and FCS, roughly **80–100 bytes** remain for everything above: IPv6 (a 40-byte header), UDP (8), CoAP, payload. Compare Wi-Fi's 1500 bytes from the table: in Lab 0 nobody counted header bytes. From Lab 2 on, everyone does. This is the problem **6LoWPAN** exists to solve.

### Where this lives in ISO/IEC 30141

- **PHY** → PED boundary (propagation) + SCD (radio hardware)
- **MAC** → SCD (communication subsystem)

---

## Segment 5 — Thread on top of 802.15.4 (34–40 min)

802.15.4 defines only the bottom two layers. Zigbee, Thread and others build different stacks on it. **Thread** adds 6LoWPAN, IPv6 with mesh routing, UDP, **MLE** (Mesh Link Establishment: how devices discover neighbours, attach and measure links) and network-wide security and commissioning. It does not define the application layer; CoAP is the usual choice, and Matter runs on top of Thread.

**Roles** (students will see `leader`, `child` and `router` in `ot state` today):

| Role | Does | Seen in |
|---|---|---|
| Leader | a router that also hands out router IDs and holds network data; exactly one per partition, re-elected if it dies | Lab 1 (Device A) |
| Router | forwards packets for others; up to 32 per network | Lab 1 (Device B, after ~2 min) |
| REED | router-eligible end device: attached as a child, promotes itself when the mesh needs another router | Lab 1 (Device B while `child`) |
| End device / sleepy end device (SED) | talks only to its parent router; an SED keeps its radio off and polls the parent for mail | Lab 4 |
| Border router | bridges the mesh to Wi-Fi/Ethernet and the Internet | Lab 5 |

> **Teaching hook**: "Nobody configured Device B as a router. It joined as a child, saw the network had room for another router, and promoted itself. That self-organization is what Lab 2 stress-tests by unplugging a router mid-ping."

---

## Segment 6 — LoRaWAN contrast (40–44 min)

The physics are in the Segment 3 table. What matters here is what those physics force on the layers above. Same architectural role in ISO/IEC 30141 (PED boundary + SCD comms).

| Axis | Thread (802.15.4) | LoRaWAN |
|---|---|---|
| **Range** | ~30–100 m indoors, ~300 m LoS | 2–15 km rural, 1–3 km urban |
| **Topology** | IPv6 mesh (self-healing, multi-hop) | star-of-stars (devices → gateways → network server) |
| **IP-native?** | yes (IPv6 end-to-end) | no (LoRaWAN frames, translated at the server) |
| **Duty cycle** | essentially unlimited | regulated in some regions: 1 % in EU868 → ~36 s of airtime per hour |
| **Power** | months on AA with frequent reports | years on AA with rare reports |

1. **Duty-cycle rules change the application.** You cannot "just send a reading every 5 seconds" on LoRaWAN in Europe. Which readings matter, how to batch them and how to handle downlink become design decisions.
2. **No IP means no end-to-end CoAP.** LoRaWAN terminates at the network server; the application talks HTTP/MQTT from there. Thread lets a cloud service address a sensor by IPv6. That is a **Functional viewpoint** difference, not just a physical one.

**When would GreenField pick LoRa?** Remote pastures with 10+ km spans. Dense in-field sensing with commands to actuators favours Thread. Hybrids are common.

> **Teaching hook**: "The six domains and the Capabilities table work identically for both. Only the content of the cells changes. That is the point of a reference architecture."

---

## Segment 7 — Lab bridge (44–50 min)

### What they are about to measure

Walk through Parts 2 and 3 of [lab1.md](../lab1.md):

1. **`ot scan energy 500`** — real noise floors per channel. Lower (more negative) = quieter. Idle is around −90 to −100 dBm; −70 dBm means someone is using it. Check the result against the Wi-Fi overlap drawing.
2. **Two-device network** — A becomes `leader`, B `child` then `router`. That is MLE from Segment 5 happening live.
3. **RSSI vs distance** — ~6 dB drop per doubling in free space, *much more* through walls or vegetation. Both are right; the difference is what fade margin covers.

### The puzzle to seed before they start

> *"The ESP32-C6 datasheet says the receiver decodes signals down to about −100 dBm. You'll find packets start dropping when RSSI falls below about −70 dBm. Where did the other 30 dB go?"*

Don't answer. They debate it during the lab and write it up in DDR Question 2. The answer involves the noise floor (you must beat noise, not just sensitivity), fade margin (multipath, obstacles, movement) and the SNR the demodulator needs: minimum RSSI = sensitivity + SNR requirement + fade margin.

### Practical reminders

- Copy the whole dataset from A to B as hex (`ot dataset active -x` → `ot dataset set active …`). Setting channel and PAN ID by hand fails: the network key is random.
- Same `ot txpower` on every board in the room, or the range tables can't be compared.
- `ot ping <addr> 64 100 0.2` — the default count is 1, which is not enough for PER. RSSI comes from `ot neighbor table` (Avg RSSI), read on the *receiving* side.
- Radios off when not testing (`ot thread stop`). Shared spectrum is a shared resource — a **trustworthiness** concern in ISO/IEC 30141.

### What Lab 2 will answer

> *"How do we fit IPv6 into 127-byte 802.15.4 frames?"*

Ask them to skim RFC 6282 (6LoWPAN header compression). The 127-byte ceiling from Segment 4 is the motivation.

---

## Instructor checklist

- [ ] Two-stack drawing (Lab 0 vs Thread) on the board, kept up all session.
- [ ] Four-radio PHY/MAC table visible for Segments 3 and 6.
- [ ] 2.4 GHz band sketch with Wi-Fi 1/6/11 over channels 11–26, gaps circled.
- [ ] 127-byte frame drawn — the hook for Lab 2.
- [ ] One board flashed with `firmware/lab1_radio` for a live `ot scan energy` before students start Part 2.
- [ ] TX power value decided and announced (0 dBm keeps the range test indoors).
- [ ] The −100 dBm vs −70 dBm puzzle posed at the end, left unanswered.

---

## References for students

- [lab1.md](../lab1.md) — the hands-on guide.
- [sop01_advanced_mac.md](../sops/sop01_advanced_mac.md) — ARQ and CSMA-CA experiments on the same firmware.
- [2_iso_architecture.md](../../2_iso_architecture.md) — domain and viewpoint definitions.
- [5_theory_foundations.md](../../5_theory_foundations.md) §1 — O-QPSK, link budget, CSMA-CA in more depth.
- [5_technology_landscape.md](../../5_technology_landscape.md) — stack-by-stack comparison across the course.
- IEEE 802.15.4-2020, Clauses 8 (PHY) and 6 (MAC).
- ISO/IEC 30141:2024, Section 9 + Tables 9-10 (Component Capabilities).
