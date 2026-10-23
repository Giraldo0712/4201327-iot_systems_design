# Lab 8 Lecture: Why Did We Build This? — The Business Viewpoint, Answered With Evidence

**Duration**: 20 min (deliberately short — the rest of the session is final-project work)

**Audience**: Students about to run Lab 8 (Golden Master, chaos script, final DDR)

**Pairs with**: [lab8.md](../labs/lab8.md)

**Follows**: [the session-7 deck](../presentations/07_fleet.md) — students can watch the fleet (telemetry, dashboard, CoAP→MQTT bridge) and were promised that in Lab 8 "watching becomes acting": the chaos script, and a signed OTA pushed back down the egress path.

---

## Learning goals

By the end of this talk, students should be able to:

1. Name the **Business viewpoint** (ISO/IEC 30141 §6.3) as the last of the six viewpoints to become dominant — and explain why it comes *last* here even though the standard puts it *first*.
2. Re-answer the three **Table 3 business concerns** from the [week-1 exercise](../docs/scenario.md#8b-business-viewpoint-exercise-isoiec-30141-section-63) — this time citing the system they actually built, with numbers.
3. Read their own technical decisions as **business capabilities**: OTA is the warranty, telemetry is the SLA, the mesh is the pricing model, open protocols are the exit clause.
4. Treat the chaos script as a **business event**, not a technical exam: every manual reset in the field is a truck roll someone pays for.

---

## Structure at a glance

| Time | Segment | One-line purpose |
|---|---|---|
| 0–5 min | The last lens | The viewpoint tour completes; week-1 callback: "you answered these questions before you'd written a line of firmware." |
| 5–15 min | The three concerns, re-asked | Value chain through *their* components; product vs as-a-service mapped onto *their* architecture; characteristics → Gustavo's decisions, with numbers. |
| 15–20 min | Lab bridge | The chaos script as a contract; DDR §8 Business row; what to hand in. |

---

## Segment 1 — The last lens (0–5 min)

### The tour completes

Extend the lens-history table one final row:

| Lab | Question being held | Lens |
|---|---|---|
| 1–4 | "Where in the stack are we adding code?" | Functional → domain ladder (PED→SCD→ASD) |
| 5 | "How many networks does a packet cross?" | Annex A pattern pair |
| 6 | "Can we trust the system end-to-end?" | Trustworthiness viewpoint |
| 7 | "Who operates and watches the fleet?" | Usage viewpoint + OMD + RAID interchange |
| **8** | **"Why does this system exist — and who pays for it?"** | **Business viewpoint** (+ Construction view in the lab) |

The Business viewpoint is the only one of the six that was never made dominant — until today. Point out the inversion: the standard lists Business *second*, right after Foundational, because in industry the *why* comes before the *how*. The course ran it backwards on purpose. In week 1 you couldn't have answered "why" with anything but speculation; today you can answer it with evidence.

### The week-1 callback

In week 1 they wrote 200–300 words on the three ISO Table 3 concerns ([project scenario §8b](../docs/scenario.md#8b-business-viewpoint-exercise-isoiec-30141-section-63)) — before flashing a single board. Ask someone to recall what they wrote. It will be vague. That's the point:

> **Question for the board:** *"In week 1, the Business viewpoint was a creative-writing exercise. What changed?"* Answer: now every claim can be checked against a system that exists. The Business viewpoint stopped being speculation and became an **audit**.

---

## Segment 2 — The three concerns, re-asked with evidence (5–15 min)

Walk the same three Table 3 concerns from week 1, but demand answers grounded in the built system.

### Concern 1 — "How does the IoT system provide value for a business?"

The value chain is no longer hypothetical — they built every link:

```
moisture reading → CBOR → Thread mesh → OTBR → bridge → broker → dashboard → valve command
  (Lab 1-3)        (L3)     (L2)        (L5)    (L7)    (L7)     (L7)        (L4)
```

The question to press: **where in that chain is value actually captured?** Not at the sensor — a reading nobody acts on is worthless. Value is captured where data becomes a *decision* (the threshold that opens a valve, the alert that sends a field team). Everything upstream of that point is cost; everything from that point on is the product. This is why Gustavo never asked about CBOR — and why he asked about battery life constantly.

### Concern 2 — "What new business models does it enable?"

Week 1 posed "what if GreenField sold irrigation-as-a-service instead of hardware?" Now map that question onto what they built — the as-a-service model isn't a pricing decision, it's a **set of technical capabilities**, and they've built each one:

| As-a-service requirement | The capability they built | Lab |
|---|---|---|
| Uptime SLA | self-healing mesh, auto-recovery (the chaos script *is* the SLA test) | 2, 8 |
| Remote fleet management | telemetry + dashboard + Green/Red status | 7 |
| Fix bugs without site visits | signed OTA over the egress path | 6, 8 |
| Customer data rights | DTLS, data inventory, deletion path (DDR §7) | 6, ethics |
| No vendor lock-in (the *customer's* concern) | Thread + CoAP open standards | all |

The punchline: **OTA is the warranty, telemetry is the SLA, the mesh is the pricing model.** A company that can't push a signed update sells hardware and walks away; a company that can, sells a service and keeps the revenue. The features they built in Labs 6–7 weren't engineering polish — they were the business model.

### Concern 3 — "How do system characteristics influence the business?" — with numbers

The memory of this course should include at least one real calculation. Do this one live (adjust to your nodes' measured numbers):

> A field tech visit to swap batteries costs, conservatively, **~$50** (vehicle + hour of labor) — per visit, regardless of how cheap the battery is. On a 500-node farm:
>
> - Lab 1 firmware (no sleep): batteries die in weeks → battery service alone dwarfs the **~$3–4/node** the ESP32-C6 module costs. The hardware is the *cheap* part.
> - Lab 3 firmware (SED, tuned poll period): months to years of battery → maintenance drops an order of magnitude.
>
> The poll-period engineering from Lab 3 wasn't a power optimization — it was the difference between a viable service business and one that loses money on every farm.

Then the **scalability** check: going from the 3-node pilot to 500 nodes, what changes in *their* architecture? (Mesh: nothing structural — that's what scalability means. Broker: a config line, per Lab 7. The bridge: unchanged.) And the **interoperability** check: Thread and CoAP are open standards, so if GreenField folds, Daniela's hardware still works — they already answered this in the ethics reflection ("if GreenField shuts down in 5 years…"). The ethics question and the business question turn out to be the same question.

> **First-principles question to drop:** *"Gustavo wants to cut cost by shipping without DTLS — 'farmers don't care about encrypted soil moisture.' You're the architect. Answer him in business terms, not security terms."* Expected: the as-a-service model dies — no customer signs an SLA with a vendor that can't protect the actuation path (an attacker who can open valves can flood a crop); GDPR-adjacent liability; retrofitting security after a pilot costs more than building it in. Security objections phrased as cost arguments are answered with cost arguments.

---

## Segment 3 — Lab bridge (15–20 min)

### The chaos script is a business event

Reframe the [lab8.md](../labs/lab8.md) exam: when Samuel cuts the OTBR's power, jams Wi-Fi, floods the mesh, and reboots nodes, he isn't grading firmware — he's simulating six months of field reality compressed into an afternoon. **Every time someone would have to press a reset button, GreenField pays for a truck roll.** "Recovers automatically" is the entire economics of the deployment. The pilot go/no-go is a contract decision, and their binary is the thing the contract rests on.

### What to hand in

1. **Re-answer the week-1 exercise** — the same three §8b concerns, 200–300 words, but now every claim cites the built system (a lab, a measurement, an ADR). Put it in the DDR.
2. **Fill the Business row** of the DDR §8 Viewpoint Analysis table — it has been sitting empty since week 1.
3. Everything else in [lab8.md](../labs/lab8.md): the Golden Master binary, the Construction-viewpoint IoT System Pattern table, the six chaos drills with recorded numbers, the demo video, and the §7 ethics assessment.

### Closing

> *"Seven weeks ago I asked you why this system should exist, and you guessed. Today you can answer with a working mesh, measured battery life, a fleet dashboard, and a binary that survives the chaos script. That's the difference between an engineer and an architect: the engineer can tell you how it works; the architect can tell you why it's worth building. Go finish your Golden Master."*

---

## Instructor checklist

- [ ] Lens-history table completed with row 8: Business viewpoint, the last to become dominant.
- [ ] The inversion named: the standard puts Business *first*; the course saved it for *last* so it could be answered with evidence, not speculation.
- [ ] Week-1 §8b exercise recalled; "speculation → audit" framing landed.
- [ ] Concern 1: the value chain drawn through *their* components; value captured at the decision point, not the sensor.
- [ ] Concern 2: the as-a-service capability table walked; "OTA is the warranty, telemetry is the SLA, the mesh is the pricing model."
- [ ] Concern 3: the truck-roll arithmetic done live with real numbers; scalability and interoperability checked against their architecture; the ethics-question/business-question convergence named.
- [ ] The Gustavo-cuts-DTLS question posed and discussed in business terms.
- [ ] Chaos script reframed as a contract decision; "every reset is a truck roll."
- [ ] Deliverables named: re-answered §8b in the DDR + the Business row of §8 filled.

---

## References for students

- [lab8.md](../labs/lab8.md) — the capstone guide: chaos script, Construction-viewpoint pattern table, deliverables, rubric.
- [Project scenario §8b](../docs/scenario.md#8b-business-viewpoint-exercise-isoiec-30141-section-63) — the week-1 Business Viewpoint exercise you are now re-answering.
- [ddr_template.md](../docs/ddr_template.md) — DDR §8 Viewpoint Analysis (the Business row), §7 ethics assessment, §10 IoT System Pattern.
- ISO/IEC 30141:2024 §6.3 + Table 3 — the Business viewpoint and its three concerns.
- [iso_architecture.md](../docs/iso_architecture.md) — the six-viewpoint overview, for one last read with all six now filled in.
