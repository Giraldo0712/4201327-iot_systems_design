# Lab 6 Lecture: A Lock on the Bytes — DTLS & the Trustworthiness Viewpoint

**Duration**: 40 min (delivered before the hands-on lab)

**Audience**: Students about to run Lab 6 (CoAPS / DTLS-PSK on ESP32-C6)

**Pairs with**: [lab6.md](../labs/lab6.md)

**Follows**: [the session-5 deck](../presentations/05_border_router.md) — students have `/env/temp` and `/act/valve` reachable from outside the mesh through the OTBR, and have seen the forward hook: "anyone who knows the global address can read the sensor and command the valve."

**Builds on**: [the session-3 deck](../presentations/03_coap.md) — students know the CoAP method semantics (GET/PUT/POST), CON reliability, and that `/act/valve` is the safety-critical resource; [the session-4 deck](../presentations/04_sensors.md) — they have met the Trustworthiness viewpoint and audited availability, integrity against faults, reliability and resilience.

---

## Learning goals

By the end of the lecture, students should be able to:

1. Explain why the **lens shifts back from a place on the map to the cross-cutting viewpoint opened in Lab 4** — Trustworthiness (§6.6) is audited across every domain, not added as a seventh domain.
2. Locate where DTLS lands in the **Functional six-domain map**: it is the **RAID access-management** control (Figure A.5) — the domain that has been gray since Lab 1 and finally lights up here, *not* a new "security domain."
3. Decompose a **DTLS-PSK handshake** (~6 flights), and explain why DTLS — not TLS — is the right fit for CoAP-over-UDP.
4. Distinguish the **two security properties** an AEAD cipher delivers — confidentiality (privacy loss if absent) vs integrity/authentication (safety loss if absent) — and map each to a row of the §6.6 audit.
5. Reason about the **energy cost** of the handshake and why **session reuse**, not per-reading handshakes, is what keeps DTLS inside the Lab 3/4 battery budget.
6. Name the **three trustworthiness pillars** a deployed fleet needs — **DTLS** (secure the channel, today's hands-on), **signed DFU/OTA** (secure the *code* on the device), and **fleet anomaly-detection** (secure the system *over time*) — and explain why the last two are realized in the dashboard labs that follow, not in a handshake.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–8 min | The lens shifts (again) + the three pillars | Cross-cutting §6.6; DTLS / DFU-OTA / fleet monitoring as pillars 1-2-3; RAID lights up. |
| 8–20 min | Pillar 1 up close: DTLS PSK handshake, AEAD, two properties | What the lock actually does, flight by flight. |
| 20–36 min | The cost of the lock + pillars 2 & 3 at fleet scale | Handshake energy, STRIDE→fleet threats, key lifecycle, signed DFU/OTA, anomaly-detection loop. |
| 36–40 min | Lab bridge | Preview the three client tests, the sniffer, the handshake table. |

---

## Segment 1 — The lens shifts, again (0–8 min)

### Callback to last week

Lab 5 ended with the OTBR bridging the mesh to the access network. Daniela can see soil temperature from the market. We left a deliberate hole open, and posed it as the Lab 6 question:

> *"Our `/env/temp` and `/act/valve` are now reachable from the public internet. Anyone who knows the global address can read sensor data and command the valve. How do we put a lock on the door without killing battery life?"*

Edward, the security lead, makes the hole concrete:

> *"I parked 50 m from the greenhouse, read every temperature value off the air, then injected a forged packet that opened the valve."*

Two questions to put on the board:

1. *"Which of those two attacks is worse?"* — They're different *kinds* of bad. Reading the data is a **privacy** failure (confidentiality). Injecting the OPEN command is a **safety** failure (integrity/authentication). One DTLS handshake fixes both, but students should feel the distinction — it maps onto two different §6.6 characteristics and two different rubric lines.
2. *"Where exactly is the lock?"* — On the CoAP transport, between UDP and the application. Not in the mesh (Lab 2's network key protects the *link*, not the *application end-to-end*), not in the OTBR (it forwards bytes; it doesn't terminate the CoAP session).

> **Important nuance to pre-empt:** "But the Thread mesh already encrypts everything with the network key!" True — at the **link layer**, hop by hop, with a *network-wide* key. That protects against an outsider with no mesh credentials. It does **not** give you end-to-end application authentication (any node *on* the mesh can forge), and it does **nothing** once the packet leaves the mesh through the OTBR onto Wi-Fi. DTLS is **end-to-end, application-to-application**, and it survives the OTBR boundary because the OTBR just forwards the opaque DTLS records. This is the single most common misconception in the lab — address it in the first five minutes.

### Why we stop asking "which domain is it?"

Recap the lens history out loud, because Lab 6 is the third distinct framing:

| Lab | Question being held | Lens |
|---|---|---|
| 1–4 | "Where in the application stack are we adding code?" | Functional viewpoint → **domain ladder** (PED→SCD→ASD) |
| 5 | "How many networks does a packet cross?" | Annex A **pattern pair** (Table A.3 system + A.4 networking) |
| **6** | "Can we trust the system end-to-end?" | **Trustworthiness viewpoint (§6.6)** — *cross-cutting* |

The key word is **cross-cutting**. The standard is explicit (§6.6): trustworthiness is *not* a domain. You don't draw a "Trustworthiness box" next to SCD and ASD. Instead you take the system you already built and **audit it** against seven named characteristics — availability, confidentiality, integrity, reliability, resilience, safety, compliance. DTLS is one *control* that moves several of those rows from "gap" to "addressed"; it is not the whole viewpoint.

> **Drawing for the board:** the six-domain map from Lab 3, with a translucent sheet laid *over the top* labelled "Trustworthiness — §6.6." The sheet touches every domain. That's cross-cutting. Contrast with Lab 3, where ASD was a discrete box you pointed at.

### RAID finally lights up

Since Lab 1, **RAID** (Resource Access & Interchange) has been gray on the board. Lab 5's lecture was careful: the OTBR is an *SCD-hosted IoT gateway*, **not** RAID — and we promised RAID would light up in Lab 6 (access management) and Lab 7 (interchange). Today is the access-management half.

```
Functional six-domain map (Figure A.5), today's change:

   PED ── SCD ── ASD ── OMD ── UD
                  │
                 RAID  ◄── access-management component
                  │         = the PSK-gated CoAPS endpoint (:5684)
                  │         "who is allowed to exercise the ASD capability?"
              (was gray since Lab 1 — lights up TODAY)
```

So when a student asks "is DTLS a new domain?", the answer is: **no — it realises RAID's access-management function, and it's audited under the cross-cutting Trustworthiness viewpoint.** Two structures, both already in the standard. Don't invent a "security domain."

> **Two-minute caution:** the `/env/temp` and `/act/valve` contracts **do not change** today. Same URIs, same CBOR, same response codes. What changes is the *transport binding* (5683 → 5684, CoAP → CoAPS) and the *access policy* (PSK gate). Students who try to "redesign the API for security" have misunderstood — the bytes are fine; you're wrapping them, not rewriting them.

### The three pillars of a trustworthy fleet — and where each one lives

Trustworthiness is bigger than one handshake. §6.6's seven characteristics, taken seriously across a *deployed* fleet, demand three distinct mechanisms — and this lecture is the chapter that names all three, even though only the first is today's hands-on work. Put this on the board and keep it up all lecture:

| Pillar | Secures… | Mechanism | Where in the course |
|---|---|---|---|
| **1. DTLS** | the **channel** — data in flight | CoAPS / DTLS-PSK (today) | **Lab 6 — hands-on, graded** |
| **2. Signed DFU/OTA** | the **code** — what runs on the device | MCUboot + image signing | Lab 6 stretch → realised in the dashboard/management labs |
| **3. Fleet anomaly-detection** | the **system over time** — is anything wrong, anywhere? | telemetry → baseline → alert | the **dashboard labs** that follow |

Why three and not one? Because each closes a hole the others leave open:

- DTLS stops an attacker **reading or forging traffic** — but does nothing if the *firmware itself* is malicious or stale.
- Signed DFU/OTA stops an attacker **installing bad code** (and lets you patch a vulnerability in the field) — but does nothing to tell you a node is *under attack right now* or quietly dead.
- Fleet anomaly-detection **notices** — failed handshakes spiking, a node gone silent, readings drifting impossibly — but it's only *observation*; it can't prevent, only alert.

> **The arc of the rest of the course:** the next labs are the last ones, and they **jump to building and managing a dashboard.** That dashboard is where pillars 2 and 3 stop being slides and become a system: it's how you *push* a signed update to the fleet and how you *watch* the fleet for anomalies. So treat today as the security *chapter opener* — you build pillar 1 with your hands, and you leave understanding pillars 2 and 3 well enough to recognise them when the dashboard makes them real.

---

## Segment 2 — Pillar 1 up close: DTLS (8–20 min)

### Part A: Why DTLS and not TLS?

Students know TLS from HTTPS (Lab 0). The instinct is "just use TLS." But TLS assumes **TCP** — an ordered, reliable, connection-oriented byte stream. CoAP runs on **UDP**. DTLS (RFC 6347 / 9147) is "TLS adapted for datagrams":

| Problem TLS leans on TCP for | What DTLS does instead |
|---|---|
| In-order delivery of handshake messages | Adds its own sequence numbers + reassembly to the handshake |
| Retransmission of lost handshake bytes | DTLS retransmits **its own** handshake flights (with backoff) |
| A held-open connection | DTLS keeps a *session* (keys), not a socket — fits a sleepy device |
| No replay across a stream | Per-record anti-replay window |

> **First-principles question to drop:** *"CoAP added CON to make UDP reliable (Lab 3). Why doesn't DTLS just rely on CoAP's CON to retransmit the handshake?"* Expected: layering. DTLS sits *below* CoAP — it has to secure the channel before CoAP exists on it. So DTLS retransmits the **handshake** itself; CON retransmits **application requests** once the secure channel is up. Two reliability mechanisms at two layers, doing different jobs.

### Part B: The PSK handshake, flight by flight

The big cost — and the thing the whole energy discussion hangs on — is the handshake. Draw it for **PSK** (the lab's mode; cheaper than certificate mode because there's no chain to send or verify):

```
   Client (Node B / laptop)                 Server (Node A, :5684)
      |  ClientHello                          |   flight 1
      |-------------------------------------->|
      |              HelloVerifyRequest        |   flight 2  (cookie — anti-DoS)
      |<--------------------------------------|
      |  ClientHello + cookie                  |   flight 3
      |-------------------------------------->|
      |   ServerHello, ServerKeyExchange(hint),|   flight 4
      |   ServerHelloDone                      |
      |<--------------------------------------|
      |  ClientKeyExchange(PSK identity),      |   flight 5
      |  ChangeCipherSpec, Finished            |
      |-------------------------------------->|
      |   ChangeCipherSpec, Finished           |   flight 6
      |<--------------------------------------|
      |  ==== session established ====         |
      |  CoAPS GET /env/temp  (encrypted)      |   now the real work
```

Three things students should leave with:

1. **~6 flights, then it's done.** After flight 6 the session exists and *every subsequent CoAP exchange reuses it* — no re-handshake. This is the entire reason DTLS is affordable on a battery node, and it's exactly the lever students tune in Task C.
2. **The HelloVerifyRequest (flights 2–3) is anti-DoS.** Before the server allocates any state, it forces the client to echo a cookie — proving the source address is real. This matters because a sleepy server is a juicy DoS target; the cookie is cheap insurance. (Maps to the §6.6 *Availability* row.)
3. **No certificates on the wire in PSK mode.** The "key exchange" carries a PSK *identity* (a string like `soilsense-pilot`), not a cert chain. Both sides already hold the key; the handshake just proves each side has it and derives session keys. That's why PSK fits a 4 MB flash device — no X.509 parser, no chain validation, no clock for cert expiry.

### Part C: AEAD — two properties from one tag

The lab's cipher is `TLS_PSK_WITH_AES_128_CCM_8`. Decode the name on the board:

```
TLS_PSK_WITH_AES_128_CCM_8
        │        │    │   │
        │        │    │   └─ 8-byte authentication tag (truncated, saves air)
        │        │    └───── CCM = Counter mode + CBC-MAC  → an AEAD mode
        │        └────────── AES, 128-bit key
        └─────────────────── key established via PSK
```

**AEAD = Authenticated Encryption with Associated Data.** One operation, one pass, gives you **both**:

- **Confidentiality** — the AES counter-mode stream hides the CBOR. The sniffer sees ciphertext.
- **Integrity + authentication** — the CCM tag is a MAC over the ciphertext, keyed by the session key. Flip one bit and the tag check fails; forge a whole record without the key and you can't produce a valid tag. The record is dropped **before** CoAP sees it.

> **The teaching hook of the whole lab:** *"Encryption stops Edward reading the data. The MAC stops Edward forging the OPEN command. They are different properties, and the second one is the safety-critical one."* Confidentiality protects Daniela's privacy; integrity/authentication protects her seedlings. A system could have one without the other (a custom XOR cipher gives confidentiality with zero integrity — trivially forgeable). AEAD gives both in one tag, which is why every modern constrained-device suite is AEAD.

> **First-principles question to drop:** *"Why an 8-byte tag (`CCM_8`) instead of the full 16?"* Expected: air time. On a 250 kbps radio every byte costs energy; halving the tag halves that per-record overhead. The trade-off is a slightly weaker forgery bound (2^-64 instead of 2^-128 per attempt) — still astronomically safe for this threat model, and the constrained-device profile (RFC 7925) explicitly recommends it.

### Part D: Where the lock sits in the stack

Tie it back to the stack students built in Labs 1–3:

```
   Layer 7  Application   ── CoAP  (unchanged: /env/temp, /act/valve)
   ─────────────────────  ──────────────────────────────────────────
              DTLS  ◄──────── the lock goes HERE: above UDP, below CoAP
   ─────────────────────  ──────────────────────────────────────────
   Layer 4  Transport     ── UDP
   Layer 3  Network        ── IP / 6LoWPAN
   Layer 2  Data Link      ── 802.15.4 MAC + network-key encryption (link-layer)
```

Two encryption layers, doing different jobs: **802.15.4 link encryption** (Lab 2, hop-by-hop, network-wide key) and **DTLS** (today, end-to-end, application session key). Students should be able to say *why both exist*: the link key keeps strangers off the mesh; DTLS keeps even *mesh members* (and anyone past the OTBR) from reading or forging *application* traffic.

---

## Segment 3 — The cost of the lock + pillars 2 & 3 at fleet scale (20–36 min)

### Part A: What the handshake costs, and why session reuse is the whole game

The handshake is ~6 flights ≈ **200–300 ms of extra radio-on time** the first time a client connects. At ESP32-C6 RX ≈ 75 mA, that's a measurable energy bite. The naive (wrong) implementation re-handshakes on every reading:

```
   WRONG (per-reading handshake):
     every /env/temp reading = handshake (250 ms) + exchange (10 ms)
     → handshake dominates → battery math from Lab 3 destroyed

   RIGHT (session reuse):
     handshake ONCE (250 ms) → then 1000s of exchanges (10 ms each)
     → handshake energy amortised to near zero per reading
```

This is the direct sequel to the Lab 3 poll-period lesson: **a security mechanism has an energy cost, and the engineering is in how often you pay it.** The §6 performance baseline and the Task C "readings per handshake" number are where students show they understood this.

> **First-principles question to drop:** *"The handshake costs 250 ms. The valve is a Sleepy End Device that wakes every 5 s. What happens to the handshake if the session times out between commands?"* Expected: you re-handshake, and on a SED that means waiting for poll cycles for each of the ~6 flights → the handshake can take *seconds*, not 250 ms. The answer is to keep the session alive (DTLS Connection ID / session resumption) or accept the latency for rare commands. This is a real tension, not a solved problem — let students sit with it.

### Part B: STRIDE — the threat-model framing (Task A)

Task A is paper, done **before** code. The scenario: *"attacker with a laptop 50 m from the greenhouse."* Walk the STRIDE letters, but only the ones that bite here:

| STRIDE | Concrete threat in SoilSense | Control |
|---|---|---|
| **S**poofing | Attacker impersonates a sensor / sends as if it were Node A | PSK authentication — no key, no valid session |
| **T**ampering | Attacker flips a byte of a reading or forges the valve command | AEAD tag rejects it (the safety case) |
| **R**epudiation | Can't prove who sent a command | *(partial gap with a shared PSK — note it!)* |
| **I**nfo disclosure | Sniffing `/env/temp` off the air | AES-128-CCM confidentiality |
| **D**oS | Flooding handshakes to exhaust the server | HelloVerifyRequest cookie (flight 2) |
| **E**levation of privilege | — *(mostly N/A at this layer; note it)* | — |

> **Honesty about Repudiation:** a *shared* PSK can't prove *which* device sent a command — any holder of the key could have. This is a real limitation and the cleanest motivation for **per-device keys / certificates** at fleet scale. Students should write it as a documented gap, not pretend DTLS-PSK solves it.

#### From one attacker to a fleet — the threat model grows

Task A's scenario is *one attacker, one laptop, one greenhouse*. That's the right size for the lab, but it hides the threats that actually dominate a deployed fleet. Widen the board for two minutes — these are discussion points, **not** graded work:

| At pilot scale (Task A) | At fleet scale (200+ nodes, three fields) |
|---|---|
| Outsider sniffs/forges from the car park | **Insider node:** one field-replaceable sensor is compromised — and it *holds the shared PSK* |
| One device, physically watched | **Lost / stolen device:** a node walks off; whoever has it can join and command the fleet |
| Firmware you flashed by hand | **Supply chain:** who built the image? who provisioned the key? (the stretch-goal OTA signing is the start of an answer) |

The through-line: **the single shared PSK is the fleet's single point of compromise.** One extracted key (flash dump, JTAG, a discarded node in a dumpster) and *every* node's traffic is forgeable. STRIDE's *Spoofing* and *Elevation of Privilege* — nearly N/A for the one-laptop case — become the headline risks once nodes are field-replaceable and the key is shared. This is the concrete, felt reason the ADR-006 trade isn't academic.

### Part C: PSK vs certificates — the ADR-006 decision

This is the analysis the rubric rewards. Lay out the trade as a table, then let ADR-006 pick PSK for the pilot:

| | PSK (the lab choice) | Certificates (X.509) |
|---|---|---|
| Flash / RAM | Tiny — a key + identity string | X.509 parser, chain, CA store |
| Handshake cost | Cheapest (no signatures) | Heavier (asymmetric crypto) |
| Identity granularity | Shared key = one identity for all holders | Per-device identity, signed |
| Revocation | Rotate the shared key (everyone reflashes/reprovisions) | Revoke one cert (CRL/OCSP) |
| Operates a PKI? | No | Yes — a real operational burden |

> **Teaching hook:** *"PSK is the right call for a 5-node pilot and the wrong call for 5000 nodes. The thing that flips it is revocation: with a shared key, one compromised node means everyone re-keys. ADR-006 should say PSK now, and name the fleet size at which you'd migrate to certificates."* This mirrors the Lab 5 single-OTBR ADR: pick the simple thing for the pilot, document the condition that forces the upgrade.

#### The operational lifecycle — where keys actually break

The cipher choice is the easy part; the *key lifecycle* is what costs an ops team. Walk the four stages and let students see why the pilot quietly punts on three of them:

```
   PROVISION  ──►  ROTATE  ──►  DETECT  ──►  REVOKE
   (get a key      (replace      (notice a    (cut off the
    onto a node)    it on a       key is        compromised
                    schedule)     compromised)   key/device)

   Lab pilot:  hardcoded   ·  never  ·  never  ·  reflash everyone
   Production: Secure       per-      anomaly   revoke one cert,
               Element       policy    monitor   fleet unaffected
```

- **Provision.** The lab hardcodes the PSK in flash — fine for five boards you flashed yourself, indefensible for a contract manufacturer building thousands. Production puts a *per-device* key in a **Secure Element** at manufacture, never in source.
- **Rotate.** This is the management-plane point from §2 made real: rotating keys without reflashing the application is only possible if provisioning was designed for it. A hardcoded PSK has *no* rotation story — you reflash.
- **Detect / Revoke.** You can't revoke what you can't detect, which is the bridge to monitoring (next part). With certificates, revocation is one CRL/OCSP entry; with a shared PSK, "revocation" means re-keying the entire fleet.

> **First-principles question to drop:** *"You ship 200 nodes with one PSK in flash. A node is found in a competitor's lab, key extracted. What is your incident response — concretely, this afternoon?"* Expected, uncomfortably: re-flash or re-provision all 200 nodes, because the one key is now public. That single answer is the whole argument for per-device keys, and it's why fleet operators treat *key provisioning* as a day-one architecture decision, not a Lab 6 afterthought.

> **And the answer to that incident raises the next pillar:** "re-flash all 200 nodes" — *how?* You can't drive to 200 sensors with a USB cable. You need **secure over-the-air update.** That's pillar 2.

### Part D: Pillar 2 — securing the *code* with signed DFU/OTA

DTLS secures the bytes on the wire. It says nothing about whether the *firmware running on the node* is the firmware you shipped. Two failures it can't touch:

1. **A vulnerability ships in v1.0.** You need to push v1.1 to the whole field — over the air, because nobody is visiting 200 sensors. (This is also the incident response from the key-extraction question above.)
2. **An attacker pushes their own image.** If the device installs *any* firmware it's handed, OTA becomes the widest attack surface you own — one malicious update owns the fleet.

The answer to both is **signed device firmware update (DFU/OTA)**:

```
   Build v1.1  ──►  Sign with private key  ──►  Host on update server
                    (imgtool, RSA-2048)              │
                                                      ▼
   Device downloads image  ──►  MCUboot verifies SIGNATURE  ──►  boot v1.1
                                 against the PUBLIC key          (or refuse
                                 baked into the bootloader        & roll back)
```

Three things students should leave with:

1. **Signing is authentication for code, exactly as the MAC was authentication for a packet.** The device boots an image only if it carries a signature made by the holder of the private key. An attacker's unsigned (or wrongly-signed) image fails verification in the bootloader and never runs — the same "reject before it does harm" logic as the DTLS record MAC, moved from the wire to the boot path.
2. **OTA *plus* signing, not OTA *or* signing.** Unsigned OTA is worse than no OTA — you've built a remote-code-execution channel into every node. The signature is what makes the convenience safe.
3. **It's pillar 1's logic, one layer down.** DTLS authenticates each *message*; DFU/OTA authenticates each *firmware image*. Both rest on "the receiver verifies a cryptographic tag against a key it trusts, and rejects on failure."

> **Where this lives in the course:** the [SOP-06 Part B stretch](../labs/sops/sop06_security_ota.md#part-b-secure-ota-updates-optional-stretch--not-graded) walks the mechanics (MCUboot, `imgtool` signing, a v1→v2 update) for students who want hands-on — but it's **not graded today**. The *managed* version — pushing a signed update to a whole fleet and tracking which nodes took it — is a job for the **dashboard labs** that follow. Today you just need to understand *why* an OTA must be signed, and that DTLS doesn't give you that for free.

> **First-principles question to drop:** *"You add OTA so you can patch the field. A student demos it with `esp_https_ota` and no signing — 'it works, the device updated.' What did they just build for an attacker?"* Expected: a remote-code-execution backdoor. Any party who can reach the update endpoint (or MITM it without DTLS, or feed a malicious URL) can install arbitrary firmware. The feature and its safeguard are *the same feature* — ship them together or not at all.

### Part E: Pillar 3 — securing the system *over time* with fleet anomaly-detection

Pillars 1 and 2 are *preventive* — they stop bad things from happening. But §6.6's **Availability**, **Resilience**, and **Safety** are also about what happens *when prevention fails or a node simply dies* — and you can't encrypt or sign your way to those. They're **operational**: you only have them if you're **watching the fleet over time.** A lock with no alarm is half a security system.

#### The detection loop — how you actually notice

Anomaly-detection isn't magic; it's one loop applied per signal, per node, continuously:

```
   TELEMETRY        BASELINE             COMPARE            ALERT
   each node     "what's normal      is this reading     raise it to a
   reports its   for THIS node      outside the         human / dashboard
   own signals   at THIS hour?"     expected band?      (and log it)
   ───────────►  ──────────────►    ──────────────►     ──────────────►
   V_BATT, RSSI,  rolling window /    threshold or         the §6.6 gap
   handshake      learned profile     statistical test     finally closed
   counts, uptime
```

The interesting word is **baseline**. A raw threshold ("alert if RSSI < −90 dBm") catches the obvious, but most fleet anomalies are *relative*: a node that always read −60 dBm and is now at −80 dBm is failing, even though −80 is "fine" in absolute terms. So real fleet monitoring compares each node against **its own recent history** (and against its **peers in the same field** — if one node's battery drops 0.3 V overnight while 40 neighbours are flat, that one node is the anomaly, not the weather). Detection is *telemetry + a notion of normal + a comparison*; the dashboard labs are where "a notion of normal" gets built.

#### The signals worth watching — and what each one tells you

| Signal (telemetry) | Normal | Anomaly means… | §6.6 characteristic |
|---|---|---|---|
| **Failed-handshake rate** | ~0 | Wrong/expired keys in the field — or someone probing keys (an *attack in progress*) | Availability, (Detection) |
| **Replay-window rejects** | 0 | An attacker replaying captured records (the Segment 4 puzzle, live) | Integrity, Resilience |
| **`V_BATT` trend** | slow, smooth decline | Sudden drop = hardware fault; flatline-then-die = a node about to go dark | Availability, Safety |
| **`RSSI` drift** | stable per node | Degrading link — node moving, obstruction, or interference/jamming | Reliability, Resilience |
| **`uptime` resets** | monotonic | Unexpected reboots = crashes, brownouts, or an OTA gone wrong | Reliability, Safety |
| **Silent / dropped node** | regular check-ins | No telemetry at all — dead battery, crash, jamming, or a node *removed* | Availability, Safety |

Two of these are *security* signals (handshake failures, replay rejects), four are *health* signals — and that's the point: **on a fleet, security and reliability monitoring are the same dashboard.** Edwin watching for dead batteries and Edward watching for an attack are looking at the same telemetry stream through different thresholds. Knowing a forged command was *rejected once* is good; knowing *the failed-handshake rate just spiked across 40 nodes in field B* is what lets an operator respond before the attacker finds the one misconfigured device.

> **Hard boundary — this is the dashboard labs' job, not today's.** The actual dashboard, the `V_BATT`/`RSSI`/`uptime` telemetry, the baselines, and the fleet health view are the **OMD / Usage** content of the labs that follow — and those are the last labs, where the course *jumps to building and managing a dashboard.* Lab 6 stops at *naming* detection as the trustworthiness gap the handshake and the signature don't close, so students write it into the §9 audit's **Gaps** column with intent — "detection of compromise / node failure: not addressed by DTLS or DFU; realised in the dashboard labs." Don't build a dashboard in this lecture; build the *reason* the dashboard labs exist.

> **Teaching hook:** *"Pillar 1 locked the door. Pillar 2 made sure only your key opens it. Pillar 3 is the camera in the hallway — it never stops a break-in by itself, but it's the only thing that tells you someone spent all night trying every key, or that the lock on door 37 has been quietly broken since Tuesday."*

---

## Segment 4 — Lab bridge (36–40 min)

### What they are about to do

Walk through [lab6.md](../labs/lab6.md) at high speed:

1. **Task A — STRIDE on paper.** Three concrete threats + controls, before any code. [SOP-06 §A.1](../labs/sops/sop06_security_ota.md#1-basic-threat-model).
2. **Task B — CoAPS up, plain CoAP locked out.** Enable four `sdkconfig` lines, paste the PSK server into Node A's Lab 3 firmware, reflash. Three client tests: plain CoAP on 5683 → **timeout**; correct PSK on 5684 → **2.05 Content**; wrong PSK → **handshake failure** (not a 4.xx). [SOP-06 §A.2–§A.4](../labs/sops/sop06_security_ota.md#2-enable-dtls-in-libcoap).
3. **Task C — Prove it on the air + handshake cost.** Sniff one CoAPS GET → "Encrypted Application Data." Measure handshake time (< 3 s) and confirm session reuse. Fill the four-row table. [SOP-06 §A.5](../labs/sops/sop06_security_ota.md#5-performance-impact-analysis).

### Practical reminders

- **PSK on both sides must match exactly.** Identity *and* key. A one-character mismatch fails the handshake with an opaque mbedTLS error — check this first when "it won't connect."
- **Port 5684, not 5683.** CoAPS is a different port. Plain-CoAP clients pointed at 5684 will fail (no DTLS); CoAPS clients pointed at 5683 will fail (no DTLS server there). Both failures are *expected* and are part of Task B's evidence.
- **The handshake error messages are cryptic.** `-0x7780` (SSL_FATAL_ALERT) usually means PSK mismatch. Have students log the identity the server received.
- **Session reuse is the energy story.** If a student's client re-handshakes per reading, their Task C number will look terrible — that's the teachable moment, not a bug to hide.
- **Don't refactor the API.** `/env/temp` and `/act/valve` stay byte-identical. Only the transport wrapper changes.

### The puzzles to seed

Two this week. Don't answer either.

> *"The 802.15.4 mesh already encrypts every frame with the network key. Edward is a legitimate field technician — he has the mesh credentials. Does the link-layer encryption stop him forging an `/act/valve` OPEN? Does DTLS? Why is the answer different for the two layers?"*

> *"You set DTLS session reuse so you handshake once and stream readings cheaply. Edward captures the whole encrypted session, can't decrypt it, but **replays** yesterday's encrypted 'OPEN valve' record verbatim today. Does it work? What in DTLS stops it — and would a hand-rolled 'encrypt the payload' scheme without that mechanism have stopped it?"*

The first puzzle is the **link-layer-vs-end-to-end** distinction: the network key stops *outsiders*, but Edward is an insider — link encryption does nothing against him, while DTLS authentication (a key he doesn't have) does. The second is **anti-replay**: DTLS records carry sequence numbers inside an anti-replay window, so a verbatim replay is rejected even though it's a "valid" ciphertext. A naive "just AES the payload" scheme has no sequence number → the replay lands → the valve opens. This is *why* you use a real protocol instead of rolling your own.

### What the dashboard labs will answer

The next labs are the last ones, and they **jump to building and managing a dashboard** — which is precisely where pillars 2 and 3 become real:

> *"The data is now encrypted (pillar 1, done). But you can't yet push a signed patch to 200 nodes in the field (pillar 2), and you can't see failed handshakes, replay attempts, or a node that went silent (pillar 3). And hitting 200 separate IPv6 addresses from a phone doesn't scale. Who manages the fleet, and how does the system expose its health?"*

Preview: the lens shifts to the **Usage viewpoint** + the **OMD** (Operation & Management) domain, and RAID's *other* half — the **interchange subsystem** — lights up as the dashboard's API surface. The dashboard is where **managed DFU/OTA** (push a signed update, track who took it — pillar 2) and **fleet anomaly-detection** (the `V_BATT`/`RSSI`/`uptime`/handshake-failure telemetry from Segment 3 Part E, with baselines and alerts — pillar 3) stop being slides and become a system. The lock you built today stays on; the dashboard labs are the *camera in the hallway and the locksmith's van* — turning the §9 audit's Gaps column into something an operator can actually watch and act on.

---

## Instructor checklist

- [ ] Lens history table on the board: domain ladder (1–4) → pattern pair (5) → cross-cutting Trustworthiness (6). "Not a new domain."
- [ ] **Three-pillar table up all lecture: DTLS (channel, today) / signed DFU-OTA (code) / fleet anomaly-detection (system over time).** DTLS is deep + hands-on, but it is explicitly *one* measure, not the whole of trustworthiness.
- [ ] The misconception killed early: link-layer (network key, hop-by-hop, outsiders) vs DTLS (end-to-end, application, insiders + past the OTBR).
- [ ] RAID "lights up" — access-management component placed on Figure A.5; the gray box from Labs 1–5 named.
- [ ] DTLS-vs-TLS table (why UDP changes things).
- [ ] PSK handshake drawn flight-by-flight (~6 flights), with the HelloVerifyRequest cookie called out as anti-DoS.
- [ ] AEAD decoded: `AES_128_CCM_8` → confidentiality + integrity in one tag. The privacy-loss-vs-safety-loss distinction stated explicitly.
- [ ] Session-reuse energy story: handshake once, not per reading. Tie to Lab 3's poll-period lesson.
- [ ] STRIDE table walked; Repudiation flagged as a real PSK gap.
- [ ] Threat model widened from one-laptop to fleet scale: insider node, lost/stolen device, supply chain — shared PSK as the single point of compromise.
- [ ] PSK-vs-certificate trade table; ADR-006 picks PSK for the pilot and names the fleet size that forces certificates.
- [ ] Key lifecycle drawn (provision → rotate → detect → revoke); the pilot punts on three of four; the "node found in a competitor's lab" incident-response question posed.
- [ ] **Pillar 2 — signed DFU/OTA:** the sign→verify→boot flow drawn; "OTA *plus* signing, never OTA alone"; the "unsigned OTA = remote-code-execution backdoor" question posed. Deferred (managed version) to the dashboard labs.
- [ ] **Pillar 3 — fleet anomaly-detection:** the detection loop (telemetry → baseline → compare → alert) drawn; **baseline-relative**, not just fixed thresholds; the signal table walked; security + health are the same dashboard. Written into the §9 audit Gaps column, deferred to the dashboard labs. "A lock with no alarm is half a security system."
- [ ] Both puzzles posed and left unanswered.
- [ ] One live demo: sniffer on a plain CoAP `/env/temp` (plaintext `4e40` visible), then the same reading over CoAPS ("Encrypted Application Data"). This is the moment the lab clicks.

---

## References for students

- [lab6.md](../labs/lab6.md) — the hands-on guide for today.
- [SOP-06: DTLS (CoAPS) & Secure OTA](../labs/sops/sop06_security_ota.md) — the firmware paste, the three client tests, the handshake timing (Part A); secure OTA as an optional stretch (Part B).
- [theory_foundations.md](../docs/theory_foundations.md) — Lab 6: Security & Trustworthiness (STRIDE, DTLS handshake cost).
- [ethics_sustainability.md](../docs/ethics_sustainability.md) — privacy-through-security, GDPR Art. 32.
- [iso_architecture.md](../docs/iso_architecture.md) — the Functional six-domain map (RAID) and §6.2.2.3.3 functional/management separation.
- ISO/IEC 30141:2024 — **§6.6** (Trustworthiness viewpoint, the seven characteristics — the part to actually read); Figure A.5 (RAID access-management component).
- RFC 6347 / RFC 9147 — DTLS 1.2 / 1.3.
- RFC 7252 §9 — Securing CoAP (the DTLS binding, the security modes incl. PreSharedKey).
- RFC 7925 — TLS/DTLS profiles for constrained IoT devices (why `AES_128_CCM_8`, why PSK).
- [Espressif CoAP + mbedTLS PSK example](https://github.com/espressif/esp-idf/tree/master/examples/protocols/coap_server) — the source the SOP is based on.
