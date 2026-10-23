# IoT Systems Design — UNAL 4201327

A course about **networked embedded systems**: how a sensor node reaches a radio, a mesh,
an application protocol, a gateway and finally a person, and what each layer costs in
energy, latency and trust. Students build one wireless sensor network on the
**ESP32-C6** with **Zephyr** and **OpenThread**, from the radio up to a dashboard, and
document it against **ISO/IEC 30141:2024**. Every design claim cites a measurement from
the team's own boards. Taught at the Universidad Nacional de Colombia, Sede Manizales.
All course material is in English; classroom delivery is bilingual, and the
[glossary](docs/glossary.md) explains every term.

## Project — GreenField Technologies

Students join **GreenField Technologies**, a fictional agri-tech startup, as junior IoT
systems engineers on **SoilSense**: soil sensors and irrigation valves for small farms
([briefing](docs/scenario.md)). Five stakeholders write the weekly memos: Samuel
(architect), Gustavo (product), Edwin (field operations), Edward (security) and Daniela
(the pilot farmer). The system grows through the semester:

1. A minimal node on Wi-Fi, first over HTTP, then over MQTT (Lab 0).
2. SoilSense nodes in the field: the 802.15.4 radio, a self-healing Thread mesh, CoAP and
   CBOR contracts, and real sensors that say when they can be trusted (Labs 1–4).
3. The mesh joined to the Internet through a Border Router, then secured and updated over
   the air (Labs 5–6).
4. The dashboard Daniela looks at, and the integrated system (Labs 7–8), pitched in the
   [final project](docs/final_project.md).

Deliverables are engineering documents, not lab reports: the **Design & Decision Record
(DDR)**, one per team and updated every lab ([template](docs/ddr_template.md),
[annotated guide](docs/ddr_guide.md)), with ADRs whose rationale is the team's own
measurements.

## Before you start

| You need | Where to review it |
|---|---|
| C on a microcontroller: GPIO, interrupts, a build and flash cycle | A prior embedded-systems course |
| IP addressing, TCP vs. UDP, `ping`, client and server | [Networking recap](docs/networking_recap.md), session 0 |
| A Linux shell (native or WSL2) and Git | [Setup](docs/setup.md) |

Setup: [docs/setup.md](docs/setup.md), done at home before the first lab.

## You will be able to

1. Characterize an 802.15.4 link (noise floor, RSSI and packet loss against distance) and choose a channel and a node spacing from the data.
2. Build a Thread mesh and measure what a hop costs and how long the mesh takes to heal.
3. Write CoAP and CBOR resource contracts, and choose confirmable or not, Observe and the poll period from measured latency and energy.
4. Integrate a real sensor and state, with evidence, when its reading can be trusted.
5. Join the mesh to Wi-Fi and the Internet through a Border Router, and measure what the boundary costs.
6. Secure the traffic, update firmware over the air, and present the data to its user.
7. Document an IoT system against ISO/IEC 30141:2024: domains, viewpoints and ADRs backed by measurements.

## Schedule

One session per lab: a talk, then the lab (2–3 h). Per-lab readings are in
[docs/references.md](docs/references.md) and [docs/theory_foundations.md](docs/theory_foundations.md).

| Session | Talk | Lab | SOP | The DDR gains |
|---|---|---|---|---|
| 0 | [Networking recap](docs/networking_recap.md) · [ISO/IEC 30141](docs/iso_architecture.md) | [HTTP](labs/lab0_http.md) and [MQTT](labs/lab0_mqtt.md): one minimal IoT system, twice | — | Team, boards; request/response vs. publish/subscribe |
| 1 | [deck](presentations/01_radio.md) | [The radio: channel, range, packet loss](labs/lab1.md) | [SOP-01](labs/sops/sop01_radio.md) | ADR-001 channel; PED/SCD map; capabilities table |
| 2 | [deck](presentations/02_mesh.md) | [Thread mesh: addresses, hops, healing](labs/lab2.md) | [SOP-02](labs/sops/sop02_mesh.md) | ADR-002 topology; Thread roles |
| 3 | [deck](presentations/03_coap.md) | [CoAP: reading sensors, commanding valves](labs/lab3.md) | [SOP-03](labs/sops/sop03_coap.md) | ADR-003/004; the API contracts |
| 4 | [deck](presentations/04_sensors.md) | [Real sensors: can you trust the reading?](labs/lab4.md) | [SOP-04](labs/sops/sop04_sensors.md) | Trustworthiness audit, first pass |
| 5 | [deck](presentations/05_border_router.md) | [Border Router: the mesh meets the Internet](labs/lab5.md) | [SOP-05](labs/sops/sop05_border_router.md) | ADR-005; the four-network walk |
| 6 | [script](lectures/lab6_lecture.md) | [Security and OTA](labs/lab6.md) | [SOP-06](labs/sops/sop06_security_ota.md) | Threat model; trustworthiness audit, second pass |
| 7 | [script](lectures/lab7_lecture.md) | [Dashboard and telemetry](labs/lab7.md) | [SOP-07](labs/sops/sop07_telemetry.md) | The User domain |
| 8 | [script](lectures/lab8_lecture.md) | [Integration](labs/lab8.md) | [SOP-08](labs/sops/sop08_consolidation.md) | All six domains; the IoT system pattern |
| — | — | [Final project: the pitch](docs/final_project.md) | — | The Business viewpoint |

Pairs for Labs 1–6; two pairs merge into teams of four for Labs 7–8.

> **Migration in progress.** Setup, Lab 0 and Labs 1–5 run on Zephyr. Labs 6–8 still
> document ESP-IDF v5.1+ while they are ported; each says which framework it expects.

## Assessment

| Component | Weight |
|---|---|
| Lab implementations, each graded by its rubric: does it work, does it meet the targets | 50 % |
| DDR: architectural reasoning, ISO/IEC 30141 mapping, ADRs | 30 % |
| Final integration: the end-to-end system, all six domains | 15 % |
| Participation | 5 % |

AI tools are allowed and declared in the DDR (tool and what it did). Every measured value
comes from your team's hardware: a number an AI wrote is not evidence.

## Hardware

Per pair: three or more **ESP32-C6** boards (DevKitC-1, DevKitM-1 or Super Mini; mixing
is fine), one temperature sensor (DS18B20, DHT22, DHT11 or BMP280) with a breadboard and
jumpers, and for Lab 5 an **ESP32-S3-DevKitC-1 with PSRAM** (N8R8 or N16R8) as the Border
Router host, with one of the C6 boards as its radio.

## Toolchain

Zephyr is pinned in [west.yml](west.yml) (main of 2026-09-01, `2f0bc11`, Zephyr SDK
1.0.1), with OpenThread from Zephyr's module; the course is validated on that revision
(dates and boards per session in [coursekit.toml](coursekit.toml)). Host tools are
Python 3 (aiocoap, cbor2, Flask, paho-mqtt). Every push builds all the firmware and
checks the documents ([.github/workflows/ci.yml](.github/workflows/ci.yml); locally:
[scripts/build_all.sh](scripts/build_all.sh)).

## References

- **ISO/IEC 30141:2024**, *Internet of Things (IoT) — Reference architecture*. Copyrighted
  and not redistributed here; get it from [ISO](https://www.iso.org/search.html?q=ISO%2FIEC%2030141).
  Its six **viewpoints** (Foundational, Business, Usage, Functional, Trustworthiness,
  Construction) are not the Functional viewpoint's six **domains** (PED, SCD, ASD, OMD,
  UD, RAID): [docs/iso_architecture.md](docs/iso_architecture.md) keeps them apart.
- R. Herrero, *Practical Internet of Things Networking: Understanding IoT Layered
  Architecture*, Springer, 2023.
- The RFCs each lab cites (6282, 7252, 7641, 8949, 4862, 6146, …), the
  [OpenThread CLI reference](https://openthread.io/reference/cli/commands) and the
  [Zephyr documentation](https://docs.zephyrproject.org).
- Lookups during a lab: [docs/references.md](docs/references.md) (cheat sheets, targets),
  [docs/glossary.md](docs/glossary.md), [docs/technology_landscape.md](docs/technology_landscape.md),
  [docs/ethics_sustainability.md](docs/ethics_sustainability.md).

## Repository layout

| Path | What it is |
|---|---|
| [labs/](labs/) | Lab guides (`lab0_http.md` … `lab8.md`) and their SOPs in [labs/sops/](labs/sops/) |
| [presentations/](presentations/) | Talks: Marp decks whose speaker notes are the script, with their figures in `img/` |
| [lectures/](lectures/) | Lecture scripts for the sessions that don't have a deck yet |
| [docs/](docs/) | Course documents: setup, scenario, ISO/IEC 30141 guide, DDR template, glossary, references |
| [firmware/](firmware/) | Zephyr applications, one per lab |
| [tools/](tools/) | Host-side Python: CoAP client, dashboards for HTTP, MQTT and CoAP, OTA server, end-to-end tests |
| [theme/](theme/) | The shared course-kit Marp theme |
| [coursekit.toml](coursekit.toml) | Maps the files to the [course standard](https://github.com/saacifuentesmu/course-kit/blob/main/STANDARD.md); `python3 ../course-kit/tools/coursekit.py lint .` checks them |

---

Maintained by Sam C · Universidad Nacional de Colombia, Sede Manizales.
