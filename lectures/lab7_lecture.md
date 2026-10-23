# Lab 7 Lecture: Watching the Fleet — Telemetry, the Dashboard & Sending Data to the Internet

**Duration**: 40 min (delivered before the hands-on lab)

**Audience**: Students about to run Lab 7 (telemetry + dashboard + CoAP→MQTT bridge on ESP32-C6)

**Pairs with**: [lab7.md](../labs/lab7.md)

**Follows**: [Lab 6 Lecture](lab6_lecture.md) — students have DTLS securing the channel, and they were promised that **pillar 3 (fleet anomaly-detection) becomes real in the dashboard labs that follow.** This is that lab.

**Builds on**: [the session-5 deck](../presentations/05_border_router.md) — students have the OTBR bridging the mesh to the internet, proved NAT64 reaches the IPv4 internet, and were told *"most IoT cloud architectures put a real HTTP/MQTT broker on the access side instead of trying to make end-to-end IPv6 work — a topic we'll come back to in Lab 7."* Today we come back to it.

---

## Learning goals

By the end of the lecture, students should be able to:

1. Distinguish **telemetry from business data** — different audience, different cadence, different cost — and name the OMD signals (`V_BATT`, `RSSI`, `uptime`) and what each tells an operator.
2. Place this lab on **two structures at once**: the **OMD domain** (a box on the Functional six-domain map) *and* the **Usage viewpoint** (one of the six viewpoints — *who operates and watches*). Explain why these are not the same thing.
3. Explain why **RAID's interchange subsystem** — the half left gray after Lab 6 — is exactly the CoAP→MQTT bridge, and why that is *information fusion* (Table A.3), which Lab 5 deferred here.
4. Articulate the central contrast of the lab: **the local-CLI path** (inside the mesh, one node at a time) vs **sending data to the internet** (off-mesh, fused, any subscriber).
5. Reason about **why a broker on the access side beats end-to-end IPv6 to every consumer**, and decide a broker (local Mosquitto / AWS IoT Core / cloud platform) understanding that **the bridge is the architecture and the broker is a config line.**
6. Build the **anomaly-detection loop** (telemetry → baseline → compare → alert) as the realization of Lab 6's pillar 3, and see that it *closes a §9 Trustworthiness-audit gap* the security lab left open.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–8 min | The lens shifts (again) + RAID's other half | OMD domain + Usage viewpoint together; RAID interchange lights up; pillar 3 becomes real. |
| 8–20 min | Telemetry up close + the detection loop | Business-data vs telemetry; the OMD signals; baseline→alert; security + health are one dashboard. |
| 20–36 min | The big idea: local CLI vs sending to the internet | The two paths drawn; why a broker beats end-to-end IPv6; Mosquitto / AWS / cloud; "the bridge is the architecture." |
| 36–40 min | Lab bridge | Walk Tasks A/B/C/stretch; practical reminders; seed the puzzles; preview Lab 8. |

---

## Segment 1 — The lens shifts, again (0–8 min)

### Callback to last week

Lab 6 ended with a lock on the bytes — DTLS encrypts and authenticates every CoAP record. But we drew a three-pillar table and said only the first was hands-on:

| Pillar | Secures… | Where in the course |
|---|---|---|
| 1. DTLS | the **channel** | Lab 6 — done |
| 2. Signed DFU/OTA | the **code** | previewed Lab 6 → **Lab 8** |
| 3. Fleet anomaly-detection | the **system over time** | **the dashboard labs — today** |

We wrote a deliberate gap into the §9 Trustworthiness audit: *"detection of compromise / node failure — not addressed by DTLS or DFU; realised in the dashboard labs."* **Today we close it.** Pillar 3 stops being a slide and becomes a dashboard with a Green/Red light.

> **Two questions to put on the board:** *"Node 4 went silent overnight. With only Lab 6's firmware, how would Edwin even know — and how long until he knew?"* (Answer: he wouldn't, until a crop died.) *"What is the smallest amount of information that would have warned him?"* (Answer: a battery trend and a heartbeat — that's telemetry.)

### Why we land on a domain *and* a viewpoint at once

Recap the lens history — this is the fourth distinct framing:

| Lab | Question being held | Lens |
|---|---|---|
| 1–4 | "Where in the stack are we adding code?" | Functional → **domain ladder** (PED→SCD→ASD) |
| 5 | "How many networks does a packet cross?" | Annex A **pattern pair** |
| 6 | "Can we trust the system end-to-end?" | **Trustworthiness viewpoint** — cross-cutting |
| **7** | "Who operates and watches the fleet — and how does its data get out?" | **Usage viewpoint** + **OMD domain** + **RAID interchange** |

Make the OMD-vs-Usage distinction explicit, because students will blur them. **OMD** is a *box on the Functional six-domain map* — the operation-and-management capabilities (the health telemetry). The **Usage viewpoint** is one of the *six viewpoints* laid over the whole system; its question is **roles and lifecycle**: who is Edwin, who is Gustavo, what's the loop from "node goes silent" to "someone swaps the battery." You implement an OMD capability *and* you read it through the Usage lens. Two structures, both in the standard — don't collapse them into "the operations stuff."

> **Drawing for the board:** the six-domain map with the **OMD** box finally filled in, and — like the Lab 6 trustworthiness sheet — a translucent "**Usage**" overlay labelled *"who watches this?"* The box is the capability; the overlay is the role looking at it.

### RAID's other half lights up

In Lab 6 we lit **RAID's access-management** component (the PSK gate — *who may exercise a capability*). We said RAID had a second half coming. Today it arrives:

```
   RAID — Resource Access & Interchange
   ├── access-management component   ◄── LIT in Lab 6 (DTLS/PSK gate)
   └── interchange subsystem         ◄── LIGHTS UP TODAY
                                         = the CoAP→MQTT bridge
                                         "expose ASD/OMD capabilities to outside
                                          consumers, and FUSE their data"
```

This is the exact thing Lab 5 kept gray. Remember the Table A.3 IoT-gateway functions — the OTBR did four of six, and we explicitly deferred *"data processing"* and *"information fusion"* as *"a Lab 7 problem."* The bridge is that information fusion: it takes per-node CoAP/CBOR readings trapped in the mesh and republishes them, fused, where the outside world can subscribe.

> **Caution to pre-empt:** "Isn't the OTBR the interchange subsystem?" **No.** The OTBR is an *SCD-hosted IoT gateway* — a network-layer router that forwards opaque IPv6 datagrams (Lab 5's whole point). The bridge is an *application-layer* component that parses CoAP, decodes CBOR, and re-emits MQTT/JSON. Router vs proxy — same distinction as a home Wi-Fi router vs a cloud API gateway. Don't retag the OTBR.

---

## Segment 2 — Telemetry up close + the detection loop (8–20 min)

### Part A: Business data vs telemetry — two audiences in one stream

```
   BUSINESS DATA            TELEMETRY (OMD)
   "soil temp = 24.5°C"     "batt=3100mV, rssi=-75dBm, up=3600s"
   for Daniela (farmer)     for Edwin/Gustavo (operations)
   "is my soil OK?"         "is the NODE OK?"
```

The same node produces both. The teaching point: **they have different cadences and different costs.** Daniela's soil temperature matters every reading; the node's uptime drifts over hours. Streaming telemetry at the business-data rate is the classic mistake — it doubles your air time for data nobody reads second-by-second.

### Part B: The OMD signals and what each one tells an operator

| Signal | Normal | An anomaly means… | §6.6 characteristic |
|---|---|---|---|
| **`V_BATT` trend** | slow, smooth decline | sudden drop = hardware fault; flatline-then-die = node about to go dark | Availability, Safety |
| **`RSSI` drift** | stable per node | degrading link — node moved, obstruction, or interference/jamming | Reliability, Resilience |
| **`uptime` resets** | monotonic | unexpected reboots = crashes, brownouts, an OTA gone wrong | Reliability, Safety |
| **Failed-handshake rate** | ~0 | wrong/expired keys — or someone *probing keys* (attack in progress) | Availability, (Detection) |
| **Silent / dropped node** | regular check-ins | no telemetry at all — dead battery, crash, jamming, or *removed* | Availability, Safety |

Two of these are *security* signals, three are *health* signals — and that's the punchline of the whole lab: **on a fleet, security and reliability monitoring are the same dashboard.** Edwin watching for dead batteries and Edward watching for an attack are reading the same stream through different thresholds.

> **First-principles question to drop:** *"Telemetry costs energy on a 250 kbps radio. The valve node is a Sleepy End Device that wakes every 5 s. What's the right report interval for its battery telemetry — and why is it NOT 'every wake'?"* Expected: battery changes over hours; reporting it every 5 s wastes most of the device's radio budget on data that barely moved. Piggyback it on the rare business packets, or report on a multi-minute timer. This is the **Lab 4 poll-period lesson again** — the engineering is in *how often you pay the cost.*

### Part C: The detection loop — how you actually *notice*

Anomaly-detection isn't magic; it's one loop, per signal, per node, continuously:

```
   TELEMETRY        BASELINE              COMPARE             ALERT
   each node     "what's normal       outside the          raise to a human
   reports its   for THIS node        expected band?       / dashboard
   own signals   at THIS hour?"                            (and log it)
   ───────────►  ──────────────►      ──────────────►      ──────────────►
   batt, rssi,    rolling window /     threshold or         the §6.6 gap
   uptime,        peer comparison      statistical test     finally closed
   handshakes
```

The interesting word is **baseline**. A fixed threshold ("alert if RSSI < −90") catches the obvious, but most fleet anomalies are *relative*: a node that always read −60 and is now at −80 is failing, even though −80 is "fine" absolutely. Real fleet monitoring compares each node against **its own history** *and* **its peers in the same field** — if one node's battery drops 0.3 V overnight while 40 neighbours stay flat, *that node* is the anomaly, not the weather.

The lab's minimal realization is honest about this: the **Green/Red status light** is a fixed-threshold detector (batt/rssi/last-seen), and the **silent-node** check is a heartbeat detector. That's enough to *close* the Lab 6 gap — you now have detection. The fancy baseline-relative version is what a production fleet builds on top.

> **Teaching hook (Lab 6 callback):** *"A lock with no alarm is half a security system. Lab 6 was the lock. Today is the alarm — and the same alarm that catches a dead battery catches an attacker trying every key."*

---

## Segment 3 — The big idea: local CLI vs sending to the internet (20–36 min)

### Part A: The two paths, drawn side by side

This is the segment students should remember. Put both paths on the board and label what's inside the mesh:

```
   LOCAL-CLI PATH  (what they already have — the "before")
   ┌─ inside the Thread mesh ─────────────────────────┐
   │  Node B ──coap observe──► Node B CLI log ──tail──►│ Flask dashboard
   └──────────────────────────────────────────────────┘
   • one node at a time   • no fusion   • nothing crosses the OTBR
   • the only "consumer" is whoever is sitting at that serial console

   OFF-MESH EGRESS PATH  (today's graded work — RAID interchange)
   ┌─ proximity (CoAP/CBOR/IPv6) ─┐  ┌translator┐  ┌─ access (MQTT/JSON/IPv4) ─┐
   │ Node ──Observe──►            │  │ bridge   │  │ ──► Broker ──► dashboard  │
   │                              │  │          │  │            ──► phone      │
   │                              │  │          │  │            ──► AWS        │
   └──────────────────────────────┘  └──────────┘  └───────────────────────────┘
   • whole fleet, fused, on one topic   • DATA HAS LEFT THE MESH
   • any authorized subscriber sees it  • this is "information fusion"
```

The bridge is the only new component, and it does exactly one conceptual job: **terminate the mesh protocol on one side, re-emit a broker protocol on the other.** That's the interchange subsystem. Everything else — the broker, the dashboard, the phone — is downstream of a topic.

### Part B: Why a broker on the access side, not end-to-end IPv6?

Students will ask "why not just let the phone talk CoAP to the node directly — we have NAT64?" Walk the reasons:

| Problem with end-to-end IPv6 to every consumer | Why a broker fixes it |
|---|---|
| **Fan-out:** N consumers × M nodes = N×M direct connections, each node serving them | One bridge publishes once; the broker fans out to N subscribers — the node serves *one* consumer |
| **Reachability:** an IPv4-only phone can't reach an IPv6 node (needs 464XLAT / a proxy) | The broker is reachable by ordinary TCP/MQTT from anything |
| **Power:** a battery node answering many direct queries never sleeps | The node pushes once on its own schedule; the broker holds the last value |
| **Decoupling:** every consumer must know every node's address | Consumers know a *topic*, not an address |

> **Callback:** *"In Lab 5 I asked — could an IPv4-only phone reach our IPv6-only sensor? The answer was 464XLAT or a proxy, and I said 'most IoT clouds put a broker on the access side instead — we'll come back to it in Lab 7.' This is it. The broker is why the whole industry doesn't bother making every phone speak IPv6 to every sensor."*

### Part C: The platform decision — and why the broker is a config line

Now the question I get every year: **"AWS? ThingsBoard? What's easiest?"** Lay it out as a table, then deliver the punchline:

| Option | Setup pain | Who runs it | What it gives you | Use it when |
|---|---|---|---|---|
| **Local Mosquitto** | one apt/docker line | you, on a laptop | a raw MQTT broker; topics + last value | **the pilot — the no-pain default** |
| **AWS IoT Core** | account, a Thing cert, TLS | Amazon | managed broker on the *real internet*, rules, fleet mgmt | you want it actually online |
| **ThingsBoard CE** | a heavy Docker stack | you | a full IoT platform: widgets, device mgmt, rules | a polished UI, self-hosted |
| **Azure IoT Hub / etc.** | account + SDK | cloud vendor | same family as AWS | vendor preference |

The **punchline** — write it big: **the bridge is the architecture; the broker is a config line.**

- Every one of these speaks MQTT/JSON, **not** CoAP/CBOR/IPv6. So *every* option needs the same bridge you write today. The cloud doesn't save you the bridge — the bridge is the part that matters.
- Going from Mosquitto to AWS is **three lines**: host, port 8883, `tls_set(...)`. Same code, same topics — your bytes now cross NAT64 to the public internet (the path you proved in Lab 5).
- So the recommendation: **local Mosquitto for the lab** (zero accounts, runs now), **AWS IoT Core as the optional "send it to the real internet" tier** for anyone who wants it, ThingsBoard/full platforms as *discussion* — they buy you a UI and device management, not a different architecture.

> **First-principles question to drop:** *"A vendor demo says 'connect your device to our cloud in one click.' Your device speaks CoAP/CBOR over IPv6 inside a Thread mesh. What is that 'one click' actually hiding?"* Expected: a bridge/gateway exactly like the one you're writing — someone still has to translate the mesh protocol to the cloud's protocol. The cloud hid the bridge; it didn't remove it. Knowing where the bridge is, is knowing where your architecture is.

### Part D: Pillar 2 preview — the egress path runs both ways

The bridge today pushes telemetry *out*. The same egress path is how, in Lab 8, a **managed signed OTA** comes back *in* — Ops publishes "update available, here's the signed image URL," the fleet pulls it, MCUboot verifies the signature (pillar 2 from Lab 6), and the fleet reports the new uptime/version back up the telemetry stream. Don't build it today — just point at where it plugs in: *the dashboard is how you watch the fleet (pillar 3, today) and, soon, how you act on it (pillar 2, Lab 8).*

---

## Segment 4 — Lab bridge (36–40 min)

### What they are about to do

Walk [lab7.md](../labs/lab7.md) at speed:

1. **Task A — the telemetry signals + ADR-007.** Add `rssi`/`batt`/`up`; decide piggyback vs `/sys/health`; pick a report interval. [SOP-07 Part A](../labs/sops/sop07_telemetry.md#part-a--the-telemetry-signals-firmware).
2. **Task B — the local dashboard (the "before").** Extend [`dashboard_coap.py`](../tools/dashboard_coap.py): batt/rssi/uptime panels, a Green/Red light, a fleet table. Walk test → RSSI drops, light goes Red. [SOP-07 Part B](../labs/sops/sop07_telemetry.md#part-b--the-local-dashboard-extend-dashboard_coappy).
3. **Task C — the interchange (the headline).** Local Mosquitto + the CoAP→MQTT bridge → `mosquitto_sub -t 'soilsense/#'` + [`dashboard_mqtt.py`](../tools/dashboard_mqtt.py). Prove the data left the mesh. [SOP-07 Part C](../labs/sops/sop07_telemetry.md#part-c--the-interchange-the-coapmqtt-bridge).
4. **Stretch — AWS IoT Core.** Same bridge, three-line change, real internet. [SOP-07 Part D](../labs/sops/sop07_telemetry.md#part-d-optional-stretch--aws-iot-core-the-real-internet).

### Practical reminders

- **paho-mqtt 2.x** needs `mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)` — the same gotcha as the Lab 0.5 dashboard.
- **Mosquitto anonymous access:** if it refuses connections, add `allow_anonymous true` to a `mosquitto.conf` for the lab.
- **Topic naming:** the bridge publishes `soilsense/<node>/telemetry`; point `dashboard_mqtt.py` at `soilsense/+/telemetry` (the `+` wildcard).
- **The OTBR must be up** for the direct-aiocoap bridge (nodes need global IPv6). No OTBR → use the CLI-tail fallback in [SOP-07 C.1](../labs/sops/sop07_telemetry.md#c1--the-bridge-script).
- **Telemetry is slow data.** If a student streams batt/rssi at the temperature rate, their report-interval analysis (and battery math) will look bad — that's the teachable moment.

### The puzzles to seed — don't answer them

> *"Your bridge publishes every node to one broker on your laptop, and Ops now watches the fleet through that dashboard. In Lab 5's ADR you were proud that the mesh keeps working when the cloud dies — local-first. Did you just re-introduce the single point of failure you avoided? Where does the local-first property actually live now — in the mesh, or in the dashboard?"*

> *"Telemetry says node 4 has gone silent — no check-in for 10 minutes. Is it dead (battery), asleep (it's a Sleepy End Device on a long poll), jammed, or stolen? You get to add exactly one more telemetry signal to disambiguate. Which one, and which cases does it actually separate?"*

The first is the **local-first vs observability** tension: the *mesh* is still local-first (the valve still actuates without the dashboard), but *visibility* now depends on the bridge/broker — and that's a legitimate availability gap to document, not hide. The second forces students to reason about what each signal *distinguishes*: a regular heartbeat separates "asleep on schedule" from "gone"; a last-known-RSSI trend separates "drifted out of range / jammed" from "crashed"; neither cleanly catches "stolen" — which is the honest answer that motivates tamper detection later.

### Forward hook to Lab 8

> *"You can now watch the fleet. But watching isn't fixing. [Lab 8](../labs/lab8.md) is the Golden Master: I flash your binary to three nodes and run the chaos script — cut the OTBR, jam Wi-Fi, flood the mesh, reboot nodes at random — and your system has to recover with nobody touching a reset button. And when a node reports a problem on the telemetry stream you built today, you'll push a signed OTA fix back down the same path. Watching becomes acting."*

---

## Instructor checklist

- [ ] Lens history table extended: domain ladder (1–4) → pattern pair (5) → cross-cutting Trustworthiness (6) → **Usage viewpoint + OMD + RAID interchange (7)**.
- [ ] **OMD-vs-Usage distinction drawn:** OMD = a box on the six-domain map; Usage = a viewpoint overlay ("who watches this?"). Not the same thing.
- [ ] **RAID's interchange subsystem lit up** on Figure A.5; the bridge named as *information fusion* (Table A.3) that Lab 5 deferred. OTBR explicitly *not* retagged.
- [ ] Pillar 3 (anomaly-detection) named as becoming real today; the §9 audit gap from Lab 6 explicitly closed.
- [ ] Business-data-vs-telemetry contrast; the OMD signal table walked; security + health = one dashboard.
- [ ] The detection loop drawn (telemetry → baseline → compare → alert); **baseline-relative**, not just fixed thresholds; the lab's status-light as the honest minimal version.
- [ ] **The two paths drawn side by side: local-CLI (inside the mesh, one node) vs off-mesh egress (fused, any subscriber).** This is the segment they must leave with.
- [ ] Why-a-broker-beats-end-to-end-IPv6 table; the Lab 5 "464XLAT / come back in Lab 7" callback honored.
- [ ] **Platform decision: "the bridge is the architecture; the broker is a config line."** Mosquitto (no-pain, required) / AWS (real internet, optional, 3-line change) / ThingsBoard (discussed). Why even the cloud needs the same bridge.
- [ ] Pillar 2 preview: the same egress path carries a managed signed OTA back down in Lab 8.
- [ ] Both puzzles posed and left unanswered.
- [ ] One live moment: `mosquitto_sub -t 'soilsense/#'` filling with two nodes' telemetry — the instant the data visibly *leaves the mesh*. This is when the lab clicks.

---

## References for students

- [lab7.md](../labs/lab7.md) — the hands-on guide for today.
- [SOP-07: Telemetry, the Dashboard & the CoAP→MQTT Bridge](../labs/sops/sop07_telemetry.md) — the firmware signals (Part A), extending the dashboard (Part B), the bridge + Mosquitto (Part C), AWS IoT Core stretch (Part D).
- [tools/dashboard_coap.py](../tools/dashboard_coap.py) — the local-CLI dashboard you extend. [tools/dashboard_mqtt.py](../tools/dashboard_mqtt.py) — the MQTT subscriber from Lab 0.5 you reuse.
- [the session-5 deck](../presentations/05_border_router.md) — the OTBR, NAT64, and the "broker on the access side" forward hook. [Lab 6 Lecture](lab6_lecture.md) — the three pillars and the §9 audit gap this lab closes.
- ISO/IEC 30141:2024 — the **Usage viewpoint** (roles & lifecycle); **Figure A.5** (RAID, the interchange subsystem); **Table A.3** (the IoT-gateway functions, incl. *data processing* and *information fusion*).
- RFC 7641 — CoAP Observe (the push mechanism the bridge subscribes to).
- [Eclipse Mosquitto](https://mosquitto.org/) — the local broker. MQTT v5 / paho-mqtt 2.x docs.
- [AWS IoT Core — Connecting a device](https://docs.aws.amazon.com/iot/latest/developerguide/connect-device.html) — Thing, certificate, ATS endpoint, MQTT-TLS:8883 (the optional internet tier).
