# Final Project: The Pitch — Leading with *Why*

**ISO lens:** the **Business viewpoint** (ISO/IEC 30141:2024 §6.3), now as the *starting point* instead of the closing audit.

---

## 1. The inversion

This course ran backwards on purpose. At GreenField Technologies you were hired as engineers into a project that already existed: Gustavo had sold the pilot, Samuel had sketched the architecture, and your job was the *how* — the mesh, the CoAP contract, the DTLS handshake, the Golden Master. The *why* sat in [one week-1 exercise](scenario.md#8b-business-viewpoint-exercise-isoiec-30141-section-63) you answered with speculation and re-answered in [Lab 8](../labs/lab8.md) with evidence.

That order is pedagogical, not professional. In industry the sequence is reversed: nobody funds a Thread mesh because Thread is elegant. Someone first argues that a problem is worth solving, that a customer will pay, and that the economics survive contact with reality (remember the truck-roll arithmetic from the [Lab 8 lecture](../lectures/lab8_lecture.md)). Only then does an architect get budget to decide *how* — and every technical trade-off you spent eight labs making (battery vs. latency, DTLS vs. handshake energy, fail-closed vs. fail-open) is ultimately settled by the business model, not by taste. This is why ISO/IEC 30141 lists Business as the *second* viewpoint, right after Foundational: the standard assumes the *why* exists before the system does.

The final project asks you to work in the professional order for the first time: **lead with the why, and let the system you built serve as the evidence.**

## 2. Two tracks, one deliverable

Pick the system you will pitch:

| Track | Your system | What "demo" means |
|---|---|---|
| **A — GreenField** | The SoilSense system from Labs 1–8 (your Golden Master), optionally extended | Live mesh: formation, dashboard, one chaos-style recovery or the fail-safe valve |
| **B — Bring your own** | An Internet-connected system you built in another course or on your own | Live end-to-end run: device/data source → network → user-facing surface |

The track does **not** change what is graded. The system is the *evidence*; the Business-viewpoint analysis is the *deliverable*. Track B teams: your system must be a real IoT/Internet system you can demonstrate and whose architecture you can defend — you will map it to the standard yourself, without eight labs of scaffolding. That mapping work replaces the extension work Track A teams do.

## 3. The scenario

You are no longer the junior engineer receiving emails from Samuel. You are the founding team presenting to a panel cast straight from Table 3's stakeholders: a **business manager** (the investor — does the model make money?), a **system owner** (the customer — will this run my operation for years without stranding me?), and an **architect** (the auditor — does the system actually support the claims?). The roles are played by your instructor and classmates. They have money and a problem; you have a working system. Convince them the system is worth deploying.

The standard itself states the stakes (§6.3.2.1): businesses "will typically evaluate the costs and benefits of IoT systems to determine whether they align with their strategic goals" — and a good IoT implementation must "lay a strong foundation for years to come." That cost-benefit evaluation *is* your pitch.

A pitch that says "we used CoAP over Thread with DTLS" answers a question nobody on that panel asked. The panel's questions are the §6.3 questions: *what problem, for whom, why now, who pays, what happens at 10× scale, and why won't this strand the customer in five years?* Your architecture appears only where it answers one of those.

## 4. Deliverables

### 4.1 Business Case document (3–5 pages)

The written core. Table 3 specifies exactly two **model kinds** for the business view — a *business model* and a *service blueprint* — so those are your two artifacts, framed by the three Table 3 concerns (the same three from week 1 and Lab 8, now applied as an *origin* story rather than a retrospective):

1. **Value path** (Concern 1): the problem, the customer, and the chain from raw data → insight → action → captured value. Mark the exact link in the chain where money changes hands. Every claim about what the system can do cites your evidence: a measurement, a demo, an ADR (Track A: DDR sections; Track B: equivalent artifacts you provide). Use §6.3.2.1's six business implications as your menu — new revenue streams, operational efficiencies, improved decision-making, enhanced customer experience, disruption of incumbents, new partnerships/ecosystems — and commit to the one or two your system *actually* delivers. A pitch claiming all six delivers none.
2. **Business model** (Concern 2, model kind 1): what you sell — boxes, a service, data, outcomes — and what that choice *demands* of the architecture. If you sell a service, show the SLA-bearing parts (uptime, recovery, remote management) actually exist in your system. If they don't, name the gap and its cost; an honest gap beats an invented capability.
3. **Service blueprint** (model kind 2): one diagram of the service in operation — the customer-visible journey on top (onboarding, daily use, an incident, offboarding/exit) and, beneath the line of visibility, the backstage machinery that makes each step happen (your mesh, dashboard, OTA path, support process, *truck rolls*). This is where "as-a-service" stops being a slogan: every backstage box is either something you built or a cost you are signing up to carry.
4. **Characteristics → consequences** (Concern 3): pick two essential characteristics from the foundational view (scalability, composability, interoperability, …) and trace each to a concrete business decision — pricing, market entry, exit clauses, support cost. With numbers where you have them. This is precisely what the standard says the business view *is*: "text explaining the business implications of the essential characteristics described in the foundational view" (Table 3, Legends).

Close with a **one-page Construction-viewpoint summary**: the IoT System Pattern table ([Lab 8 §2](../labs/lab8.md#2-isoiec-30141-placement)) filled for the system you are pitching. This is the page the architect on the panel reads.

### 4.2 The pitch (15 min + 5 min Q&A)

- **~10 min pitch**: problem → value → business model → why this architecture and no other. Slides optional; clarity mandatory.
- **~5 min live demo**: the system running, end to end. The demo *supports a business claim* made in the pitch — it is not a feature tour.
- **Q&A**: the panel asks §6.3-style questions plus one viewpoint each from the other five. Every team member answers at least one question.

### 4.3 Peer panel duty

Each team also serves on the panel for two other teams, with one assigned question per pitch drawn from a viewpoint card (Business, Usage, Trustworthiness, Functional, Construction). Asking a sharp *why* question is graded participation — it is the skill this project exists to build.

## 5. Grading rubric (100 pts)

**Business case (50)** — Value path concrete and evidence-cited (10) · Business model with its architectural demands made explicit, gaps named honestly (10) · Service blueprint: customer journey + backstage machinery, every backstage box built or costed (10) · Two foundational-view characteristics traced to real business consequences, quantified where possible (10)

**Pitch & demo (20)** — Leads with the problem and the why; architecture appears as justification, not inventory (15) · Demo runs and substantiates a stated business claim (10) · Q&A: defended trade-offs in business terms (5)

**ISO/IEC 30141 alignment (20)** — §6.3 concerns addressed as a viewpoint, not a slogan (10) · IoT System Pattern table complete and matching the demonstrated system (10)

**Panel participation (10)** — Assigned questions asked and engaged seriously.

**Pass/fail gate** — The demo must run. A system that cannot be demonstrated cannot be pitched; reschedule beats vaporware.

## 6. Logistics

| Item | Value |
|---|---|
| Teams | Lab 7–8 teams of 4 (Track B teams may re-form around an existing project) |
| Track declaration + one-paragraph pitch abstract due | ____ |
| Business Case document due | ____ |
| Pitch sessions | ____ |
| Weight in course grade | ____ % |

---

> **Why this is the final exam.** Eight labs taught you that the engineer answers *how it works*. The Business viewpoint — and this pitch — is where you practice the other half: *why it is worth building, and who pays*. The day you can argue both, in front of people holding the budget, you are doing the job the way the industry actually does it.
