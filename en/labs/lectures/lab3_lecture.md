# Lab 3 Lecture: CoAP — Why HTTP Kills Batteries, and How to Command a Sleeping Valve

**Duration**: ~45 min (delivered before the hands-on lab; Segment 6 can be cut to fit 40)
**Audience**: Students with a working Thread mesh (Lab 2) and the Lab 0 HTTP and MQTT builds behind them
**Pairs with**: [lab3.md](../lab3.md)

---

## Learning goals

By the end of the lecture, students should be able to:

1. Explain in bytes, packets and handshakes why HTTP/JSON is the wrong application protocol for a battery-powered Thread node.
2. Decompose a CoAP message into header, token, options and payload, and predict its size for a given request.
3. Choose CON or NON, and polling or Observe, for a given message (telemetry, command, alarm), and predict how long a CON request waits before giving up.
4. Explain why PUT is safe to retransmit and POST isn't, and why that matters more on a radio than on Ethernet.
5. Encode a small object in CBOR by hand and say why it beats JSON without being a custom binary format.
6. Predict the downlink latency to a sleepy end device from its poll period, and place CoAP (ASD) and the poll mechanism (SCD) in ISO/IEC 30141.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–6 min | Recap + ISO placement | Lab 3 is the first lab that lives mostly in ASD. |
| 6–13 min | Why HTTP kills batteries | Do the arithmetic; map CoAP onto the Lab 0 code. |
| 13–24 min | The CoAP message, CON/NON, methods | Header bytes, reliability without TCP, idempotency. |
| 24–30 min | Observe | Push instead of poll; the uplink energy win. |
| 30–36 min | CBOR and CDDL | The payload layer and the contract. |
| 36–42 min | Downlink to a sleeping valve | Poll period, retransmit timing, duplicates. |
| 42–45 min | Lab bridge | What they'll measure, and the puzzles. |

---

## Segment 1 — Recap + ISO placement (0–6 min)

Open with Daniela's two complaints from the lab brief, on the board:

1. *"Batteries die in 4 days, and the dashboard is stale."*
2. *"The valve moved 14 minutes late, and nobody knew whether it got the command."*

Neither is a radio problem; Labs 1 and 2 fixed the radio and the mesh. Both are about how
the application uses the radio: how long it keeps it on, who decides when to talk, and
what "delivered" means.

### Where Lab 3 lives

Lab 1 sat on the PED ↔ SCD boundary. Lab 2 built the mesh inside the SCD. Lab 3 is the
first lab that lives **mostly in ASD**:

| Today's artifact | ISO/IEC 30141 Functional element |
|---|---|
| The URIs `/env/temp`, `/act/valve` | ASD service identifiers |
| The CBOR payloads + CDDL | ASD data contracts |
| GET / Observe / PUT, CON / NON | ASD interaction patterns |
| UDP + the Thread mesh underneath | SCD communication subsystem (Lab 2) |
| The sleepy valve's parent poll | SCD communication subsystem |

A URI plus a schema is what an "API" means in IoT. The contract students write today is
the one the dashboard team, the border router (Lab 5) and the auditor will read.

**Functional vs management plane** (ISO §6.2.2.3.3), two parallel pipes on the board:

```
Functional plane (today):   app ─ CoAP ─ UDP ─ IPv6 ─ 6LoWPAN ─ 802.15.4
Management plane (Lab 2):   Thread MLE: attach, routing, leader, parent links
```

They share the radio, not the protocol: swap CoAP for MQTT-SN without touching MLE.

> **Optional aside (cut first if short)**: the domain map is one diagram in one viewpoint.
> ISO/IEC 30141 has six viewpoints (Foundational, Business, Usage, Functional,
> Trustworthiness, Construction). Labs 1–4 climb the Functional viewpoint's domains; from
> Lab 5 the lens changes to networking patterns (Table A.4), then Trustworthiness (Lab 6),
> Usage (Lab 7) and Construction (Lab 8).

---

## Segment 2 — Why HTTP kills batteries (6–13 min)

### Do the arithmetic on the board

Students wrote this in Lab 0 (`firmware/lab0_http`):

```c
int len = snprintf(body, sizeof(body), "{\"temperature\": %u.%u}", tenths / 10, tenths % 10);
response_ctx->status = HTTP_200_OK;
response_ctx->headers = headers;          /* Content-Type: application/json */
response_ctx->body = body;
```

About 20 bytes of useful data. What it costs over TCP:

```
TCP handshake           3 packets   SYN, SYN-ACK, ACK
HTTP GET + headers      1 packet    request line, Host, User-Agent, Accept… ~150 B
HTTP 200 OK + headers   1 packet    status line, Content-Type, Content-Length… ~120 B
TCP teardown          2–4 packets   FIN, ACK (each side)
                      ─────────
                      7–9 packets, several hundred bytes, for ~20 B of data
```

Every packet keeps a radio on, at both ends, and every handshake round trip adds a
multi-hop mesh delay. **The radio is the battery.**

CoAP: **one request datagram, one response datagram**, no handshake, no teardown. Same
REST model, roughly a tenth of the airtime.

> **First-principles question to drop**: *"HTTP was designed in 1991 for wired networks.
> Which of its assumptions break on a battery-powered radio mesh?"* Expected: opening a
> connection is cheap; headers are free because bandwidth is plentiful; text is fine
> because parsing is cheap; both ends are always awake.

### Map CoAP onto what they already wrote

CoAP introduces no new mental model, only new bytes. The firmware for today
(`firmware/lab3_coap`) is the structural twin of Lab 0:

| Lab 0 (HTTP / MQTT) | Lab 3 (CoAP) | Same role |
|---|---|---|
| `HTTP_RESOURCE_DEFINE(sensor_resource, iot_service, "/api/sensor", …)` | `COAP_RESOURCE_DEFINE(env_temp, soilsense, { .get = …, .path = … })` | bind a path to handlers |
| `/api/control` (LED) | `/act/valve` (LED as valve) | the actuator |
| `JSON_OBJ_DESCR_PRIM(…)`, JSON text | `zcbor_float16_put(…)`, CBOR bytes | the payload encoder |
| MQTT telemetry at **QoS 0** | **NON** | fire and forget |
| MQTT commands at **QoS 1** | **CON** | acknowledged, retried |
| `mqtt_subscribe("iot/control")` | GET with **Observe: 0** | register for pushes |

Two structural differences:

1. **No broker.** Every node can be client and server; they find each other by IPv6
   address.
2. **No connection.** One datagram per message, no transport state.

---

## Segment 3 — The CoAP message, CON/NON, methods (13–24 min)

### Part A: the message format

The single most important picture of the lecture:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|Ver| T |  TKL  |     Code      |          Message ID           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Token (0–8 bytes)                                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Options (delta-encoded: Uri-Path, Content-Format, Observe…) |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|1 1 1 1 1 1 1 1|   Payload (CBOR)                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Field | Size | Meaning |
|---|---|---|
| Ver | 2 bits | always 1 |
| T | 2 bits | CON, NON, ACK, RST |
| TKL | 4 bits | token length |
| Code | 8 bits | `c.dd`: `0.01` GET, `0.03` PUT, `2.04` Changed, `2.05` Content, `4.04` Not Found |
| Message ID | 16 bits | matches an ACK to its CON; detects duplicates |
| Token | 0–8 B | matches a response to its request (2 B from the OpenThread shell) |

Predict a size together: `GET env/temp` from the shell = 4 (header) + 2 (token) + 4
(`env`: 1 option byte + 3) + 5 (`temp`) = **15 bytes**. Students check it in S's log.

**Two questions students always ask:**

1. *"Why both Message ID and Token?"* The Message ID is for the messaging layer (this ACK
   is for that CON). The Token is for the application (this response is for that
   request). Observe notifications arrive minutes later with new Message IDs but the same
   Token.
2. *"Why delta-encoded options?"* Smaller, and it forces a fixed order so a parser makes
   one pass. (The firmware must append Observe (6), Content-Format (12), Max-Age (14) in
   that order.)

### Part B: CON and NON — reliability without TCP

```
CON: the receiver must acknowledge          NON: no acknowledgement
  Client                    Server            Client                    Server
    | CON MID=0x1234 GET      |                 | NON MID=0x1234 GET      |
    |------------------------>|                 |------------------------>|
    | ACK MID=0x1234 2.05 data|                 | NON MID=0x5678 2.05 data|
    |<------------------------|                 |<------------------------|
       piggybacked response
```

The decision matrix, on the board:

| Message | Type | Why |
|---|---|---|
| Periodic reading | NON | a lost reading is replaced by the next one |
| Observe notification on change | NON | the next change re-notifies |
| Observe heartbeat | CON | proves the observer is still there (RFC 7641 §4.5) |
| Valve command | **CON** | must arrive, and the client must know it arrived |
| Frost alarm | CON | must arrive |

**The retransmission schedule** (RFC 7252 §4.8), compute it with them:

```
first wait     random in [2, 3] s      ACK_TIMEOUT × [1, ACK_RANDOM_FACTOR=1.5]
retransmit 1   wait doubles: 4–6 s
retransmit 2   8–12 s
retransmit 3   16–24 s
retransmit 4   32–48 s                  MAX_RETRANSMIT = 4
               ───────
last retransmission sent after 30–45 s  (MAX_TRANSMIT_SPAN = 45 s)
client gives up after 62–93 s           (MAX_TRANSMIT_WAIT = 93 s)
```

Students measure this in Task 4.2: unplug the valve, send a CON PUT, time the
`ResponseTimeout`. The same NON PUT fails silently, forever.

> **Trap to call out**: NON doesn't mean "best effort to deliver". It means "don't
> acknowledge at the message layer". Loss is invisible to the sender.

> **Why doubling?** Radio losses come in bursts (a collision, a microwave oven). Waiting
> longer each time gives the channel time to clear; a fixed interval would re-collide.

### Part C: methods and idempotency

| Method | Code | Idempotent? | Safe? | SoilSense use |
|---|---|---|---|---|
| GET | 0.01 | yes | yes | `GET /env/temp`, `GET /act/valve` |
| POST | 0.02 | **no** | no | append an event; never "set state" |
| PUT | 0.03 | **yes** | no | `PUT /act/valve` with `{"v": 1}` |
| DELETE | 0.04 | yes | no | rare on devices |

```
PUT /act/valve {"v": 1}  → valve opens → ACK lost → client retransmits
                         → handler runs again → valve still open ✓

POST /act/valve/toggle   → valve opens → ACK lost → client retransmits
                         → handler runs again → valve closes ✗
```

RFC 7252 lets a server remember recent Message IDs and replay its response to a
duplicate. **The Zephyr CoAP server used in the lab doesn't**: every retransmission
reaches the handler. Students see it in Task 5.3 (S logs `OPEN, no change`). With a
non-idempotent command that log line would be a second valve movement. **Use PUT for
state, POST for events.**

> **First-principles question to drop**: *"CoAP makes UDP reliable with CON. Why not just
> run CoAP over TCP?"* Expected: connection state and keepalives cost RAM and radio time;
> TCP retransmits segments, not requests, so the application can't tell which request
> failed; one lost segment stalls every request behind it.

---

## Segment 4 — Observe (24–30 min)

Polling burns the radio even when nothing changed:

```
Client → GET /env/temp → 24.5 °C     (60 s)
Client → GET /env/temp → 24.5 °C     ← same value, paid for both radios anyway
Client → GET /env/temp → 24.5 °C
```

Observe (RFC 7641) flips who decides: register once, the server pushes.

```
Client → GET /env/temp, Observe: 0  → 2.05, Observe: 5, 24.5 °C   (registered)
                                       (drifts 0.3 °C: no notification)
Server → 2.05, Observe: 6, 25.1 °C  NON                           (moved > 0.5 °C)
                                       (45 s without change)
Server → 2.05, Observe: 7, 25.0 °C  CON  → Client ACK             (heartbeat)
Client → GET /env/temp, Observe: 1                                 (cancel)
```

Points to land:

- **Observe moves "when to talk" from the client (who can't know whether the value
  changed) to the server (who does).** That's the energy win, and it's structural.
- The 0.5 °C threshold is **application policy**; CoAP only supplies the registration,
  the Token and the sequence number. Keep them separate in the code (`env_temp.c` does).
- The sequence number (24 bits, wraps) lets the client drop reordered notifications.
  Observe is **eventually consistent**, not lossless: a lost NON is simply superseded.
- Max-Age (60 s here) says how long a value stays fresh. The heartbeat (45 s) keeps the
  client's copy fresh even on a still day, and as a CON it lets the server discover a
  vanished observer and drop it.

> **First-principles question to drop**: *"Why doesn't every IoT system use Observe for
> everything?"* Expected: the server keeps state per observer (address, token, sequence);
> push only works if the server can reach the client, which breaks behind NATs and
> firewalls; a sleeping client can't receive pushes at all.

---

## Segment 5 — CBOR and CDDL (30–36 min)

CBOR (RFC 8949) is a binary encoding of JSON's data model: maps, arrays, numbers,
strings, each item prefixed by a type-and-length byte.

```
JSON:  {"t": 24.5}         11 bytes
       7B 22 74 22 3A 20 32 34 2E 35 7D

CBOR:  A1 61 74 F9 4E 20     6 bytes
       │  │  │  └──┴──┴── F9 = half-precision float, 4E 20 = 24.5
       │  │  └── 't'
       │  └── text string, length 1
       └── map, 1 pair
```

Decode `4E 20` on the board: sign 0, exponent `10011` = 19 − 15 = 4, mantissa
`1000100000` = 1 + 1/2 + 1/32 = 1.53125, so 1.53125 × 2⁴ = **24.5**. Half precision
gives about 3 significant digits, enough for a soil sensor; that's a design decision to
write in the contract.

A fuller reading:

| Payload | JSON | CBOR |
|---|---|---|
| `{"id": "soil-07", "t": 24.5, "rh": 67, "ts": 1715000000}` | 49 B compact, 56 B with spaces | 30 B |

Roughly **1.6–1.9× smaller**, and still self-describing: any CBOR library decodes it
without the firmware's source.

**CDDL** (RFC 8610) is to CBOR what JSON Schema is to JSON; it's how the contract is
written down:

```
env-reading = { t: float16 }      ; °C
valve-state = { v: 0 / 1 }        ; 0 = closed, 1 = open
```

> **First-principles question to drop**: *"Why not a hand-rolled binary struct and get
> 3× instead of 1.7×?"* Expected: no schema evolution (adding a field breaks every
> decoder), no tooling, the cloud team needs your firmware changelog to read the data.

### Three protocols, one course

Let students fill this from memory of Lab 0 before revealing it:

| | HTTP (Lab 0) | MQTT (Lab 0) | CoAP (Lab 3) |
|---|---|---|---|
| Transport | TCP | TCP | UDP |
| Fixed header | none (text) | 2 B + topic | 4 B |
| Pattern | request/response | publish/subscribe via broker | request/response + Observe |
| Broker | no | **yes** | no |
| Reliability | always | per message (QoS 0/1/2) | per message (NON/CON) |
| Fits | browsers, Wi-Fi gadgets | cloud fan-out, powered fleets | constrained mesh |

> **Teaching hook**: "Constraints pick the protocol, not preferences. The Wi-Fi side of
> the border router (Lab 5) can keep using MQTT or HTTP. The radio side can't afford to."

---

## Segment 6 — Downlink to a sleeping valve (36–42 min)

### The mailbox

From the Lab 2 role table, the **sleepy end device (SED)**: a child whose radio is off
between polls. Everything addressed to it waits at its **parent router**.

```
poll period = 5 s
t = 0      C sends CON PUT /act/valve to S
t ≈ 0.02   reaches S's parent; parent holds it (S is asleep)
t = 2.5    C's first ACK wait expires → C retransmits; the parent holds that too
t = 5      S wakes, polls: "any mail?" → parent delivers both copies
t ≈ 5.02   S runs the handler twice (open, then "no change"), sends two ACKs
```

Three consequences:

1. **Worst-case downlink latency ≈ the poll period.** The client sees a slow node, not a
   dead one; the parent stands in for it.
2. **A poll period longer than `ACK_TIMEOUT` causes duplicate requests.** Harmless with
   PUT, a second valve movement with a toggle. Fix: raise the client's ACK timeout for
   sleepy destinations (SOP-03 Experiment B).
3. **Uplink is unaffected**: the SED can transmit any time; its Observe notifications go
   straight out.

### The poll-period trade-off

```
average current ≈ (t_on / poll_period) × I_rx + I_sleep
```

| Poll period | Worst-case latency | Radio-on for polling (t_on ≈ 10 ms) |
|---|---|---|
| 1 s | ~1 s | 1 % |
| 5 s | ~5 s | 0.2 % |
| 30 s | ~30 s | 0.03 % |

Students put the ESP32-C6 datasheet's RX and sleep currents into this in their energy
estimate. The point: manual valve control is human-paced. 5 s is invisible to Daniela;
1 s costs several times the battery for nothing anyone notices.

**When polling isn't fast enough:** Thread 1.2 added **CSL (Coordinated Sampled
Listening)**: parent and child agree on a periodic listen window, so the parent transmits
at a known time instead of waiting for a poll. Mention it so nobody leaves thinking
"sleepy = seconds of latency, deal with it".

> **First-principles question to drop**: *"Why not always poll every second?"* Expected:
> battery, and channel occupancy that grows with the fleet. Constraints pick the
> parameter.

---

## Segment 7 — Lab bridge (42–45 min)

### What they're about to do

1. **Setup:** flash `firmware/lab3_coap` on two boards; C forms the network and runs
   `ot coap start`, S is the field node.
2. **Uplink:** `ot coap get <S> env/temp`, decode against the contract; Observe for 5 min
   and count threshold vs heartbeat notifications against 300 polls.
3. **Downlink:** `ot coap put <S> act/valve con 1` (LED white), idempotency, then CON vs
   NON with S gone: time the `ResponseTimeout`.
4. **Sleepy valve:** `ot mode -`, three poll periods, ping latency; at 5 s, watch the PUT
   arrive twice.

### Practical reminders

- **Never `ot coap start` on S.** OpenThread would take port 5683 from S's server.
- The shell sends text, so the valve accepts `0`/`1` as text; real clients send CBOR with
  Content-Format 60. Both are in the contract.
- The shell doesn't print response codes. S's log does; keep both monitors visible.
- The ping timeout must exceed the poll period, or Task 5.2 reports loss that isn't.

### The puzzles to seed

Don't answer either.

> *"The temperature drifts 0.4 °C per minute for an hour, then jumps 1 °C in one second.
> How many notifications does the server send in that hour? How stale can the client's
> value get?"*

> *"A 50-valve field polls every 30 s, and the dashboard opens all valves at 06:00 with
> CON and default timers. Count the retransmissions per valve before the first one
> wakes, and think about what that does to the channel."*

Reference answers (yours, not theirs): (1) the drift needs 75 s to reach 0.5 °C, but the
45 s heartbeat fires first and resets the baseline, so the threshold never triggers during
the drift: about 80 heartbeats in the hour, plus one threshold notification for the jump.
The client's value is at most 45 s old and at most ~0.3 °C behind. Without the heartbeat
it would have received one notification every 75 s. (2) With a 30 s poll and a 2–3 s first wait, three retransmissions
(after ~2.5, ~7.5 and ~17.5 s) can go out before a valve wakes: up to 4 copies of each
command queued at the parents, 200 frames instead of 50, all at the same minute. Raise
`ACK_TIMEOUT` for sleepy destinations, and stagger the commands.

### What Lab 4 will answer

> *"The temperature has been a sine wave all along. What changes when the readings come
> from a real sensor: noise, calibration, sampling cost, and what to put in the contract
> about accuracy?"*

---

## Instructor checklist

- [ ] HTTP vs CoAP arithmetic on the board (7–9 packets vs 2).
- [ ] CoAP header bitmap with the five fixed fields; the 15-byte GET predicted.
- [ ] CON/NON matrix and the retransmission ladder (45 s span, 93 s give-up).
- [ ] PUT vs POST-toggle under a lost ACK.
- [ ] CBOR `{"t": 24.5}` decoded byte by byte, including `4E 20`.
- [ ] SED mailbox timeline with the duplicate PUT.
- [ ] One live demo: `ot coap get` and `ot coap put … con 1` from a client board, with the server's log visible.
- [ ] Both puzzles posed and left unanswered.

---

## References for students

- [lab3.md](../lab3.md) and [SOP-03](../sops/sop03_coap_basic.md).
- [5_theory_foundations.md](../../5_theory_foundations.md) §4 — CoAP in more depth.
- RFC 7252 (CoAP; read §3 message format and §4 reliability), RFC 7641 (Observe), RFC 8949 (CBOR), RFC 8610 (CDDL).
- ISO/IEC 30141:2024 — Functional viewpoint, §6.2.2.3.3.
