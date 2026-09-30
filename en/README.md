# IoT Systems Design Course

ESP32-C6 • Zephyr • OpenThread • ISO/IEC 30141:2024

You'll build a wireless sensor network end to end — radio waves to dashboard — and
document it the way a professional engineer does. Eight labs, working in pairs.

The project: you're a Junior IoT Systems Engineer at **GreenField Technologies**,
building soil monitoring for small farms. Full briefing in
[1_project_scenario.md](1_project_scenario.md).

> Lost on a term? [glossary.md](glossary.md) explains every one in plain English.

---

## Week 0 — do this before Lab 1

- [ ] **[0_0_setup.md](0_0_setup.md)** — install Zephyr, build Hello World on the C6
- [ ] **[1_project_scenario.md](1_project_scenario.md)** — the company, the stakeholders, your role
- [ ] **[2_iso_architecture.md](2_iso_architecture.md)** — the ISO/IEC 30141 framework we design against

Then Week 1 is networking fundamentals
([0_1_networking_recap.md](0_1_networking_recap.md)) plus two warm-up builds of the
same minimal IoT system, first over
[HTTP](0_2_Minimal_IoT_Implementation_http.md), then over
[MQTT](0_3_Minimal_IoT_Implementation_mqtt.md) — so you can compare
request/response against publish/subscribe before choosing anything. Labs 1–8 start
in Week 2.

---

## The 8 labs

| Lab | What you'll do | Technical focus | ISO domains |
|-----|----------------|-----------------|-------------|
| [1](labs/lab1.md) | Measure how far your radio reaches and what blocks it | RF characterization, 802.15.4 | SCD |
| [2](labs/lab2.md) | Get the sensors talking over IPv6 | 6LoWPAN, Thread mesh | SCD |
| [3](labs/lab3.md) | Design a lightweight protocol for sensor readings | CoAP, CBOR | ASD |
| [4](labs/lab4.md) | Read real temperature/moisture and ship it over the mesh | Sensor integration | ASD, SCD |
| [5](labs/lab5.md) | Bridge the mesh to Wi-Fi and the Internet | Border router | SCD |
| [6](labs/lab6.md) | Encrypt the traffic, update firmware wirelessly | DTLS, OTA | OMD, RAID |
| [7](labs/lab7.md) | Build the interface the farmer actually looks at | Dashboard, telemetry | UD, ASD |
| [8](labs/lab8.md) | Integrate everything into one working system | System integration | All 6 |

Each lab opens with a stakeholder email setting the week's mission, explains the
*why* from first principles, then gives you tasks and deliverables. Stuck on the
how? Every lab has a step-by-step guide in [labs/sops/](labs/sops/).

**Phases:** 1–2 feasibility · 3–4 network design · 5–6 integration and security ·
7–8 deployment. Pairs for Labs 1–6 (two boards per pair); two pairs merge into
teams of 4 for Labs 7–8 to build a bigger mesh.

---

## What you deliver

Not lab reports — engineering artifacts.

**Design Decision Record (DDR)** — one living document per team, updated every lab.
It maps your work to the six ISO domains, records design choices, and holds your
performance measurements. Template: [3_deliverables_template.md](3_deliverables_template.md),
worked example: [3_deliverables_tutorial.md](3_deliverables_tutorial.md).

**Architecture Decision Records (ADRs)** — standalone justifications for the big
calls. "Why CoAP instead of MQTT?" with the alternatives you considered and what it
cost you.

**Performance reports** — evidence you met the operational requirement, e.g. "mesh
healing under 60 s". Baselines are in [references.md](references.md).

**Stakeholder summaries** — the same system explained to whoever is asking: Samuel
(architect) wants technical depth, Gustavo (product) wants cost and value, Edwin
(operations) wants deployment and troubleshooting, Edward (security) wants threat
mitigation, Daniela (farmer) wants it to work in her field.

---

## Assessment

| Component | Weight |
|-----------|--------|
| Lab implementations — does it work, does it meet the baselines | 50% |
| DDR quality — architectural thinking, ISO mapping, ADRs | 30% |
| Final integration — end-to-end system, all six domains | 15% |
| Participation | 5% |

We assess architectural understanding, not just whether the code compiles.

---

## Stack

ESP32-C6 DevKitC · Zephyr · OpenThread (Thread mesh) · CoAP · CBOR · DTLS with
AES-128-CCM.

> **Migration in progress.** Setup, the Lab 0 builds and Lab 1 are Zephyr. Labs 2–8
> still document ESP-IDF v5.1+ while they're being ported — follow the setup guide, and
> each lab will say which framework it expects.

---

## Where to look when you're stuck

| | |
|---|---|
| Unfamiliar term | [glossary.md](glossary.md) |
| Command or baseline lookup | [references.md](references.md) |
| Step-by-step implementation | [labs/sops/](labs/sops/) |
| Why does this work this way | [5_theory_foundations.md](5_theory_foundations.md) |
| What else exists in this space | [5_technology_landscape.md](5_technology_landscape.md) |
| ISO/IEC 30141 questions | [2_iso_architecture.md](2_iso_architecture.md) |
| Privacy, compliance, sustainability | [4_ethics_sustainability.md](4_ethics_sustainability.md) |

---

_Based on ISO/IEC 30141:2024 "Internet of Things (IoT) — Reference Architecture"._
