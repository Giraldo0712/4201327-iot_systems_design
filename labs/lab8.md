# Lab 8: The Golden Master — Survive the Chaos Script, Then Say Why It Exists
> - **Talk:** [lab8_lecture.md](../lectures/lab8_lecture.md) · **SOP:** [SOP-08: The Golden Master and the chaos drills](sops/sop08_golden_master.md)
> - **Reading:** ISO/IEC 30141:2024 §6.3 (Business viewpoint, Table 3) and §6.7 (Construction viewpoint, Table 12) · your week-1 Business exercise

**GreenField Technologies — SoilSense Project** · Phase: Production release · 2 sessions

**From:** Samuel (Senior Architect) — *"The pilot starts Monday, and the contract has a
go/no-go gate. I'll flash your binary on three nodes and run the chaos script: cut the
Border Router's power, reboot nodes at random, flood them with requests, hang the
firmware. If the system recovers by itself, we ship. If I press a reset button once, we
fail: in the field, that press is a truck roll."*

No new features: you freeze Labs 1–7 into a release, the Golden Master, and prove it
recovers without a hand on it. Then you close the DDR by answering, with evidence, the
question week 1 could only guess at: why should this system exist?

| Stakeholder | Their question | How this lab answers |
|---|---|---|
| **Samuel (architect)** | Does it survive the chaos script untouched? | Task C: six drills, hands off, timed on the dashboard. |
| **Edwin (Ops)** | Will I be rolling trucks? | Auto-recovery, a watchdog, rate limiting and a valve that fails closed. |
| **Edward (Security)** | Did the hardening survive integration? | Task D: the e2e suite and a mini pentest. |
| **Gustavo (product)** | Is it a go, and does it sell a service? | Task E: the Business viewpoint, re-answered with numbers. |
| **Daniela (farmer)** | If GreenField disappears, does my farm still water? | The blackout drill, and the open protocols underneath. |
| **ISO 30141 auditor** | Are all six viewpoints covered? | DDR §8 complete, and the §10 IoT system pattern. |

## What you'll measure

Hand in the prediction column before the drills.

| Quantity | Prediction | Your value | Target |
|---|---|---|---|
| Cold start: power on in the worst order → every node green | ____ | ____ s | < 120 s |
| Blackout: the OTBR back → every node green | ____ | ____ s | < 120 s |
| Valve open, node cut off → valve closed | ____ | ____ s | < 180 s |
| Firmware hangs → the node back on the dashboard | ____ | ____ s | < 120 s |
| e2e stress: GETs served, average latency | ____ | ____ % / ____ ms | ≥ 80 % |
| Burst: the first 4.29 arrives at request | ____ | ____ | your limit + 1 |
| Soak: hours run, unplanned reboots | ____ | ____ h / ____ | ≥ 12 h / 0 |

## Tasks

**Per team:** the Lab 7 fleet: every node, the OTBR, the laptop with the fleet stack and
the bridge.

### Task A — Freeze the Golden Master
- Build [`firmware/lab8_golden`](../firmware/lab8_golden) for every node
  ([SOP-08 §1](sops/sop08_golden_master.md#1-build-the-golden-master)). It is the Lab 7 node
  plus: the DTLS key read from a `secrets.conf` that git ignores, a version stamp, Thread
  rejoined at boot, per-client rate limiting, a fail-safe valve and a watchdog. Read each
  in the source and say what failure it answers.
- Rebuild the OTBR with its autostart option and store the hotspot and the Thread
  network in its flash ([SOP-08 §2](sops/sop08_golden_master.md#2-the-otbr-that-comes-back)).
- **Evidence:** every node's boot line `SoilSense Golden Master v1.0.0`, and proof that the
  key is not in git (`git check-ignore` and `git grep` output).

### Task B — The actuation path
- Burst requests at a node and find where it starts answering 4.29; then open a node's
  valve and cut the node off from every neighbour
  ([SOP-08 §3](sops/sop08_golden_master.md#3-rate-limit-and-fail-safe)).
- Decide ADR-008: the fail-safe delay (too short closes the valve on every mesh hiccup;
  too long floods the field), the rate limit (too tight blocks your own bridge), and where
  the key should live in production.
- **Evidence:** the 4.29 responses, and the node's `Thread role` and `FAILSAFE` log lines
  with their timestamps: how much of the delay is Thread's, how much is yours?

### Task C — The chaos drills
- Run the six drills hands off, watching only the dashboard and the logs
  ([SOP-08 §4](sops/sop08_golden_master.md#4-the-chaos-drills)): cold start, blackout,
  parent loss, flood, random reboots with one firmware hang, and the overnight soak.
- **Evidence:** the measurement table filled in, a dashboard screenshot per drill, and
  the overnight uptime curve.

### Task D — The e2e suite and the mini pentest
- Run [`tools/test_e2e.py`](../tools/test_e2e.py) against a node from the laptop
  ([SOP-08 §5](sops/sop08_golden_master.md#5-the-e2e-suite-and-the-pentest)). Every test
  that passes also proves the OTBR path.
- By hand: a board with the wrong Thread network key tries to join; a wrong DTLS key
  probes a node while you watch the dashboard.
- **Evidence:** the suite's summary, the intruder's `ot state`, the dashboard during the
  probe.

### Task E — Why this system exists
- Re-answer the [week-1 Business exercise](../docs/scenario.md#8b-business-viewpoint-exercise-isoiec-30141-section-63):
  the same three concerns of Table 3, 200–300 words, but every claim cites the built
  system: a lab, a measurement, an ADR.
- Fill the IoT system pattern (Table 12) from what you flashed, and record a two-minute
  demo: the mesh forming, the dashboard, one drill recovering, the valve failing closed.
- **Evidence:** the business case, the pattern table, the video.

## ISO/IEC 30141 mapping

The tour ends with the two viewpoints never made dominant. The **Business viewpoint**
(§6.3, Table 3) asks why the system exists and who pays: the standard lists it second,
before the how; the course left it for last so you could answer with evidence. The
**Construction viewpoint** (§6.7) asks what was actually built: Table 12, the IoT system
pattern, filled from the binary you shipped, not the one you meant to build.

| IoT system pattern (Table 12) | Your SoilSense |
|---|---|
| IoT components and devices | ____ |
| Digital network | ____ |
| Primary capabilities: observation, control | ____ |
| Secondary capabilities: processing, transfer, storage | ____ |
| Interfaces: network, human, application | ____ |
| Supplemental: security, orchestration, management | ____ |

## Deliverables

Update [your DDR](../docs/ddr_template.md), final version:

- **§2 Lab log, *To Samuel*:** the drill numbers and your go/no-go, argued like an
  architect.
- **§3 ADR-008, hardening the Golden Master:** the fail-safe delay, the rate limit and
  the key's home, with your drill numbers.
- **§4 ISO mapping, final sweep:** every component placed; no gray boxes left.
- **§5 First principles:**
  1. Why does the valve fail closed?
  2. Why is availability a business property?
  3. Why is "no new features" a feature in the last week?
- **§6 Performance:** cold start, blackout recovery, stress ratio and latency, soak.
- **§7 Ethics, the final assessment:** the data inventory (what SoilSense collects,
  where it goes, how Daniela deletes it) and four questions: if GreenField shuts down in
  five years, does Daniela's farm still water? What could you stop collecting? Who
  benefits and who might be disadvantaged? What would you change with ethics as a day-one
  requirement?
- **§8 Viewpoints:** all six rows; the Business row is the Task E answer.
- **§9 Trustworthiness audit, final:** availability and safety now carry the drills; the
  signed firmware update (pillar 2) is either done or a documented gap with a plan.
- **§10 Construction:** the Table 12 pattern above.

## Grading (100 pts)

| | pts |
|---|---|
| **Technical execution** — six drills hands off, with numbers (20) · Golden Master built: key out of git, version, rate limit and fail-safe shown (10) · e2e suite passing and the demo video (10) | 40 |
| **ISO/IEC 30141** — §8 with all six rows and the evidence-based Business row (10) · §10 pattern matching the binary (10) · §4 and §9 final sweep, pillar 2 honest (10) | 30 |
| **First principles** — Q1 (6) · Q2 (7) · Q3 (7) | 20 |
| **Communication** — ADR-008 with numbers (5) · the go/no-go to Samuel (5) | 10 |
| **Ethics (pass/fail)** — the four questions answered; the valve shown failing closed; the data inventory with a deletion path | ✓ |

## Resources

ISO/IEC 30141:2024 §6.3 and §6.7 · RFC 8516 (4.29 Too Many Requests) ·
[Zephyr task watchdog](https://docs.zephyrproject.org/latest/services/task_wdt/index.html) ·
[final project](../docs/final_project.md): the pitch, led by the why.
