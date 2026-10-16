# Lab 4 Lecture: Real Sensors — Can You Trust the Reading?

**Duration**: 40 min (delivered before the hands-on lab)
**Audience**: Students with the Lab 3 CoAP node working: `/env/temp` with Observe, `/act/valve` with CON
**Pairs with**: [lab4.md](../lab4.md)

---

## Learning goals

By the end of the lecture, students should be able to:

1. Explain the ISO/IEC 30141 Trustworthiness viewpoint as an audit across every domain, name its seven characteristics, and say which four a real sensor brings into play.
2. Tell resolution, accuracy, noise and response time apart, and read each one off a datasheet and a breath test.
3. Explain how a node rejects faulty data with range and step checks, and why no such check can reject a value that is wrong but believable.
4. Use CoAP's Max-Age, the 5.03 response and Observe's error rule to state a freshness promise, and predict what a client sees when the sensor dies and when the node dies.
5. Explain why a sensor read can fail more often while the radio is busy, and which failures a node should recover from on its own.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–6 min | Recap + a new lens | The sine wave is gone; Trustworthiness is an audit, not a domain. |
| 6–15 min | Integrity: what a real sensor gives you | Resolution, accuracy, noise, response, and the faults to expect. |
| 15–25 min | Availability: freshness and reachability | Max-Age, 5.03, and the two failure signatures. |
| 25–32 min | Reliability and resilience | Reads that fail under radio load; what heals by itself. |
| 32–40 min | Lab bridge | Tasks, reminders, puzzles. |

---

## Segment 1 — Recap + a new lens (0–6 min)

Read Edwin's email from the lab brief. The north-plot node kept answering "24 °C" all
afternoon with its probe pulled out. Every protocol from Lab 3 worked: the GETs were
answered, the Observe heartbeats arrived on time. The system was **available and wrong**.

Lab 3's sensor was a sine wave: always there, always plausible, never late. Today it
becomes a component that can lie, die and lag, and the question changes from "where does
this piece sit on the map?" to "can we trust what it tells us?"

### Trustworthiness is a sheet laid over the map

Labs 1–3 placed pieces on the Functional viewpoint's domain map (PED, SCD, ASD…). The
Trustworthiness viewpoint (§6.6) doesn't add a seventh domain. It's a list of questions
the auditor asks about every domain you already have.

> **Drawing for the board:** the domain map from Lab 3, with a translucent sheet over it
> labelled "Trustworthiness §6.6". The sheet touches PED, SCD and ASD at once. Keep it up;
> Lab 6 adds to it.

The standard names seven characteristics (§6.6.2.3). Put them on the board and circle
today's four:

| Characteristic | Today? | Where it gets answered |
|---|---|---|
| **Integrity** | yes: faulty devices, environmental causes | Lab 4, Part 3 |
| **Availability** | yes: can a client get current data? | Lab 4, Part 4 |
| **Reliability** | yes: do reads succeed consistently? | Lab 4, Part 5 |
| **Resilience** | yes: does the node heal by itself? | Lab 4, Part 5 |
| Confidentiality | no | Lab 6 (DTLS) |
| Integrity: malicious actors | no | Lab 6 (authentication) |
| Safety, compliance | started here (a default for missing data), finished later | Labs 6 and 8 |

The standard's definition of integrity already splits the work between the two labs: data
"not altered by faulty or unauthorized devices, by malicious actors, or by environmental
causes". Today is the first and last causes. Lab 6 is the middle one.

---

## Segment 2 — Integrity: what a real sensor gives you (6–15 min)

### Four words students mix up

| Term | Meaning | How to see it |
|---|---|---|
| **Resolution** | the smallest step the sensor reports | the smallest change between two readings |
| **Accuracy** | how far from the true value it may be | the datasheet; a reference reading |
| **Noise** | how much it wanders when nothing changes | the spread over a still minute |
| **Response time** | how fast it follows a real change | a breath test |

A sensor can have fine resolution and poor accuracy: a cheap sensor printing 0.01 °C
steps around a value that is 2 °C off. The contract must state accuracy, not resolution.

### The bench, measured on the course boards

One breath each, read every 2 s, in the same room:

| Sensor | Resolution | Accuracy (datasheet) | Breath: rise | Speed |
|---|---|---|---|---|
| BMP280 (bare chip) | 0.01 °C | ±1 °C | +5.4 °C | ~1 °C/s; two thirds back in ~16 s |
| DHT22 (plastic case) | 0.1 °C | ±0.5 °C | +3.3 °C | smooth, slower |
| DHT11 (plastic case) | 1 °C | ±2 °C | +4 °C in 1 °C steps | slow |
| DS18B20 (steel probe) | 0.0625 °C | ±0.5 °C | +1.75 °C | ~0.16 °C/s; two thirds back in ~20 s |

Points to land:

- **The housing is part of the sensor.** The steel probe smooths a breath away; that's
  what you want in soil, where a gust shouldn't count as a change. The bare chip sees
  everything.
- **The sensor shapes the network traffic.** With Lab 3's 0.5 °C Observe threshold, two
  minutes of breath tests on the BMP280 produced 23 notifications; the steel probe would
  have sent a handful. The DHT11's 1 °C steps notify on every step, and a value sitting
  on a step boundary flips back and forth.

### Faults to expect

| Fault | What it looks like | Seen on the bench |
|---|---|---|
| Dead | no answer, the read fails | wire pulled: "No 1-Wire slaves", DHT timeouts |
| Stuck at a limit | the value sits at the edge of the range | DHT11 humidity at 95 %, DHT22 at 100 %, for minutes after a breath |
| Power-on default | a fixed, believable-looking number | DS18B20 reports exactly 85.0 °C after a reset |
| Spike | one reading far from its neighbours | a corrupted bit |
| Environmental | real, but not what you meant to measure | condensation on the humidity element; a hand on the probe |

### Checks the node can make, and the one it can't

`reading.c` rejects a value outside −40 to 85 °C (which also catches the DS18B20's 85.0)
and a value more than 5 °C away from the reading 2 s earlier. Both are cheap and catch
faults.

Then ask the room for the case no check catches: **a value that is wrong but
believable**. 25.5 °C when the truth is 24.1 °C passes every rule. Catching it takes a
second opinion (another sensor, a neighbour, a model of the field), or, when the wrong
value comes from an attacker rather than a fault, proof of who sent it. That last one is
Lab 6.

> **First-principles question to drop**: *"The DHT11 humidity reads 95 % for ten minutes.
> Is that a fault?"* Expected: you can't tell from the value; you can tell from the
> context. It's at the top of the sensor's range, it got there in seconds and it isn't
> moving. A value at the limit of the range is a limit, not a measurement.

---

## Segment 3 — Availability: freshness and reachability (15–25 min)

### The CoAP pieces, already in your contract

Three CoAP features carry the whole freshness story. Students have seen the first two;
today they get a job.

| Feature | Where | Today's job |
|---|---|---|
| **Max-Age** (RFC 7252 §5.10.5) | every 2.05 response | "this value is fresh for N more seconds": 60 s minus the reading's age |
| **5.03 Service Unavailable** (§5.9.3.4) | GET when no reading is fresh | "I'm here, the data isn't"; its Max-Age says when to ask again |
| **Error notification** (RFC 7641 §4.2) | Observe | a non-2.xx notification carries no Observe option and ends the observation |

Plus the Lab 3 **CON heartbeat** every 45 s: the server promises to speak at least that
often, so silence becomes information.

### Two failures, two signatures

Draw both timelines. This is the picture Edwin asked for.

```
Sensor dies, node fine                       Node dies
t = 0    probe pulled                        t = 0    node off the network
t ≈ 6 s  "Sensor lost" (3 failed reads)               (nothing is sent)
         GETs still get the last value,               GET con: C retransmits…
         Max-Age shrinking (54, 39, 24…)              Observe: silence
t ≈ 60 s 5.03 to every observer,             t ≈ 45 s a heartbeat is overdue
         observations end;                   t = 62–93 s GET: ResponseTimeout
         GET → 5.03 "no fresh reading"
```

The client distinguishes the two by **who answers**:

- **5.03**: the node is reachable and says its data isn't available. Send someone to fix
  the sensor.
- **Silence or ResponseTimeout**: the node is unreachable. Check the node, its battery,
  the mesh.

Reachability and data availability are different properties, and a contract that doesn't
separate them gives Edwin the north-plot afternoon.

> **First-principles question to drop**: *"Why not keep answering with the last value and
> a 'stale' flag in the payload?"* Expected: that's a valid design, but every client must
> know to check the flag, and an old client that doesn't will show 24 °C forever. Max-Age
> is the standard place for freshness, and a 5.03 can't be mistaken for a reading. Either
> way, the contract has to say which.

---

## Segment 4 — Reliability and resilience (25–32 min)

### Why a busy radio can break a sensor read

Three ways a sensor talks to the MCU:

| Sensor | Bus | Who keeps the timing |
|---|---|---|
| BMP280 | I²C | bus hardware in the chip |
| DS18B20 | 1-Wire | the CPU, in short slots (under 1 ms each, interrupts off per slot) |
| DHT11/22 | single-wire | the CPU, measuring every pulse of a ~22 ms reply |

When the CPU keeps the timing, anything that interrupts it, such as the radio receiving
a frame, can stretch a pulse and corrupt a bit. The checksum catches it and the read
fails. Locking interrupts for the whole read fixes the sensor and starves the radio for
22 ms: the trade-off students measure in SOP-04 Experiment B.

The lab measures the failure rate with the radio quiet, then with C pinging S ten times
a second. Ask students to predict which sensors suffer before they measure. On the course
bench a DHT22 failed 0 of 60 reads quiet and 11 of 63 (17.5 %) under the pings, while C's
pings lost 1 of 1200: the radio won, the sensor lost. That misses the DDR's < 5 % target,
which is the finding: a reliability gap with a named cause and three remedies (retry,
lock interrupts, a sensor with bus hardware).

### What heals by itself, and what doesn't

The standard asks for "self-monitoring and self-healing techniques". Map them onto the
node:

| After… | Heals by itself? | How |
|---|---|---|
| a failed read | yes | the next read 2 s later |
| a pulled wire, plugged back | yes | the thread keeps retrying; `Sensor back` |
| a 5.03 that ended the observation | **no** | the client must register again |
| a reboot | partly | the Thread dataset is in flash; observers and counters were in RAM |
| a BMP280 missing at boot | **no** | its driver only looks for the chip at startup: reset after fixing |

The "no" rows are the resilience gaps for the §9 audit, and each names who has to act:
the client, or a person.

---

## Segment 5 — Lab bridge (32–40 min)

### What they're about to do

1. **Setup:** wire the sensor to S (3V3 only), build S with its overlay and C without
   one, form the network as in Lab 3, `soilsense stats` on S.
2. **Integrity:** a still minute (resolution, noise), the instructor's reference
   (offset), a breath with Observe running (response, notifications), then `soilsense
   inject` against the checks.
3. **Availability:** pull the data wire and time the 5.03; then `ot thread stop` on S
   and time the ResponseTimeout.
4. **Reliability and resilience:** failure rate quiet vs busy (ping flood), recovery
   after the wire goes back, what survives a reset.
5. **Class table:** one row per pair, one table for the DDR.

### Practical reminders

- **3V3, never 5 V** on the sensor: the data line follows the sensor's supply.
- One 3V3 pin on the board: use the breadboard rails when two things need it.
- The overlay must match the sensor. A DHT11 built as a DHT22 reads garbage.
- Never `ot coap start` on S (Lab 3).
- Breathe *gently* on DHT sensors; a full breath pins the humidity for minutes. Post the
  reference reading on the board before Task 3.2.

### The puzzles to seed

Don't answer either.

> *"A node's sensor fails at 05:59:30. The irrigation rule reads `/env/temp` at 06:00
> and opens the valves if it's above 22 °C. The last good value was 24 °C. What does the
> rule do, and what should it do?"*

> *"Your node reads the DHT22 every 2 s and fails 3 % of reads when the radio is busy.
> Raising the sample period to 10 s cuts the failures per hour by 5. Does it make
> `/env/temp` more reliable?"*

Reference answers (yours, not theirs): (1) at 06:00 the reading is 30 s old: still
inside Max-Age, so the GET answers 2.05 with 24 °C and Max-Age 30, and the valves open on
a value the node can no longer confirm. Whether that's acceptable is a safety decision:
the rule can demand a younger reading (look at Max-Age), or treat "fresh but no longer
updating" as unknown. Until 06:00:30 the contract allows it; that's what Max-Age means.
(2) Fewer failed reads, but the same failure *rate*, and each failure now leaves the
value 10 s staler instead of 2 s; with the 60 s freshness window, three failures in a
row cost half the window. Reliability is the rate; what users feel is freshness.

### What Lab 5 will answer

> *"Today the client was one hop away. When the client is a phone on Wi-Fi, how does it
> reach `/env/temp`, and what new ways are there for 'unreachable' to happen?"*

---

## Instructor checklist

- [ ] Edwin's north-plot story told; "available and wrong" on the board.
- [ ] Domain map with the Trustworthiness sheet over it; seven characteristics, today's four circled.
- [ ] Resolution / accuracy / noise / response defined, bench table shown.
- [ ] Fault catalogue, and the believable-lie case left for Lab 6.
- [ ] Max-Age, 5.03 and the error notification as the freshness contract.
- [ ] Both failure timelines drawn; "who answers" as the distinguishing signal.
- [ ] CPU-timed vs hardware-timed buses; the busy-radio prediction asked.
- [ ] Self-healing table with the "no" rows marked as audit gaps.
- [ ] Both puzzles posed and left unanswered.

---

## References for students

- [lab4.md](../lab4.md) and [SOP-04](../sops/sop04_sensor_integration.md).
- ISO/IEC 30141:2024 §6.6 (Trustworthiness viewpoint; §6.6.2.3 defines the seven characteristics).
- RFC 7252 §5.9.3.4 (5.03) and §5.10.5 (Max-Age); RFC 7641 §4.2 (notifications and errors).
- The datasheet of your sensor: DS18B20, DHT11, DHT22/AM2302 or BMP280.
