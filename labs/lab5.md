# Lab 5: Border Router — Bridging the Mesh to the Internet
> - **Talk:** [lab5_lecture.md](../lectures/lab5_lecture.md) · **SOP:** [SOP-05: Border Router](sops/sop05_border_router.md)
> - **Reading:** [theory_foundations.md](../docs/theory_foundations.md) §5 (Border Router, NAT64)

**GreenField Technologies — SoilSense Project** · Phase: Integration · 3 hours

**From:** Daniela (farmer) — *"Standing next to the nodes, your laptop shows me the soil temperature. At the house, on my phone, I see nothing: the mesh is an island. I want my phone to see the field and open the valve. And if that new box dies, the valve must still obey whoever is in the field."*

Today you add the one device that connects the Thread mesh to Wi-Fi: an **OpenThread
Border Router (OTBR)**. No new resource: the same `/env/temp` and `/act/valve` from
Labs 3–4, now reachable from your laptop and your phone, and you measure what the
boundary costs.

| Stakeholder | Their question | How this lab answers |
|---|---|---|
| **Daniela (farmer)** | Can my phone see the field? | Task D: the dashboard on your phone, through the OTBR. |
| **Edwin (Ops)** | If the OTBR dies, does the field still work? | Task F: you kill it and command the valve from inside the mesh. |
| **Samuel (architect)** | What does the boundary cost? | Tasks D–E: the latency the OTBR adds, and NAT64's round trip. |
| **ISO 30141 auditor** | Which networks are chained, and what crosses each boundary? | The four-network walk (Table A.4) in your DDR. |

Unfamiliar terms (RCP, Spinel, OMR, SLAAC, NAT64) are in the [glossary](../docs/glossary.md).

## What you'll measure

Hand in the prediction column before the lab. All RTTs are the average (ping) or
median (CoAP) of 10.

| Quantity | Prediction | Your value | Target |
|---|---|---|---|
| In-mesh RTT, C → S (`ot ping`) | ____ | ____ ms | your Lab 3 value |
| Wi-Fi hop, laptop → OTBR, power save on | ____ | ____ ms | — |
| Wi-Fi hop, laptop → OTBR, power save off | ____ | ____ ms | — |
| Laptop → S, `ping` | ____ | ____ ms | — |
| Laptop → S, CoAP GET `/env/temp` | ____ | ____ ms | < 200 ms |
| OTBR added latency: (laptop → S) − (laptop → OTBR) | ____ | ____ ms | < 100 ms |
| NAT64: S → 8.8.8.8 | ____ | ____ ms | < 200 ms |
| OTBR off: C → S `PUT /act/valve` | ____ | works? ____ | works |

## Tasks

**Per pair:** S and C from Lab 4, a third ESP32-C6 that becomes the radio, an
**ESP32-S3-DevKitC-1 with PSRAM** (N8R8 or N16R8), three jumper wires, and a phone
hotspot on **2.4 GHz with WPA2**. The OTBR is two boards acting as one: the S3 has Wi-Fi
but no 802.15.4 radio, so it drives the C6's radio over a UART (the C6 is the RCP, the
Radio Co-Processor). Pull the course repository first: Lab 4's firmware gained SLAAC.

### Task A — Build the Border Router
- Wire the S3 to the RCP C6 (TX↔RX crossed, plus GND) and flash
  [`firmware/lab5_rcp`](../firmware/lab5_rcp) to the C6 and
  [`firmware/lab5_border_router`](../firmware/lab5_border_router) to the S3
  ([SOP-05 §1](sops/sop05_border_router.md#1-wire-and-flash-the-two-boards)).
- On the S3's shell, `ot rcp version` must answer: that's the S3 talking to the C6.
- **Evidence:** the `ot rcp version` and `ot version` output.

### Task B — Wi-Fi, a Thread network, and border routing
- Join your hotspot (`wifi connect`), then form a new Thread network on the channel
  your instructor assigns (15, 20, 25 or 26: clear of Wi-Fi channels 1, 6 and 11)
  ([SOP-05 §2](sops/sop05_border_router.md#2-join-wi-fi-and-form-the-thread-network)).
- Border routing starts by itself once Wi-Fi is up. Check `ot br state` (`running`),
  `ot br omrprefix` and `ot netdata show`: which prefix does the OTBR advertise to the
  mesh, and with which flags? Is it a global prefix or a ULA (`fd…`)? Why?
- **Evidence:** `wifi status`, `ot state`, `ot br state`, `ot netdata show`.

### Task C — Bring S and C over
- Rebuild S and C from `firmware/lab4_sensors`, then move both onto the OTBR's network
  with its dataset ([SOP-05 §3](sops/sop05_border_router.md#3-move-s-and-c-onto-the-otbrs-network)).
- On S, `ot ipaddr` now shows one more address than in Lab 4. Which one is it, and who
  told S its prefix?
- Measure the in-mesh RTT, C → S, as in Lab 3.
- **Evidence:** the OTBR's `ot child table` and `ot router table`; S's `ot ipaddr`
  annotated (link-local, mesh-local, RLOC, OMR).

### Task D — Reach S from outside the mesh
- Connect your laptop to the same hotspot. Find the route to the OMR prefix on the
  laptop: who installed it? ([SOP-05 §4](sops/sop05_border_router.md#4-reach-s-from-the-laptop))
- Ping the OTBR's Wi-Fi address with power save on, then run `wifi ps off` on the OTBR
  and ping again. Then ping S's OMR address, and time 10 CoAP GETs with
  `tools/coap_client.py --count 10`.
- Run `tools/dashboard_coap.py --host <S-omr>` and open it **on your phone**. Open and
  close the valve from there.
- **Evidence:** the laptop's route, the four RTTs, a photo of your phone showing the
  chart, and S's log line for the valve PUT that came from it.

### Task E — NAT64: an IPv6-only node reaches the IPv4 Internet
- On S: `ot ping 8.8.8.8` ([SOP-05 §5](sops/sop05_border_router.md#5-nat64-and-the-otbr-off-test)). Record the address the shell says it synthesized, and find
  its prefix in `ot netdata show`.
- **Evidence:** the ping output and the NAT64 route line from the network data.

### Task F — Kill the Border Router
- Unplug the S3. From C, `PUT /act/valve` to S's mesh-local address (Lab 3 Task 4.1),
  and retry the laptop's GET. What still works, and what fails, how quickly?
- Plug the S3 back in and restore it (SOP-05 §5). Does it rejoin as leader?
- **Evidence:** C's response to the PUT with the OTBR off, the laptop's error, and S's
  log.

## ISO/IEC 30141 mapping

Labs 1–4 placed code on the Functional viewpoint's domains. Today's question is about
devices and networks, and Annex A answers it with a pair of patterns. **Table A.3**
(enterprise system pattern) names the device: *"IoT gateways are devices which connect
SCD with other domains. IoT gateways provide functions such as protocol conversion,
address mapping, data processing, information fusion, certification, and equipment
management."* Figure A.5 draws the gateway **inside the SCD**: the OTBR is an
SCD-hosted IoT gateway, not RAID (RAID lights up in Labs 6–7). **Table A.4**
(enterprise networking pattern) names the networks it joins:

| Network (Table A.4) | In SoilSense | Address you see |
|---|---|---|
| Proximity | the Thread mesh (S, C, the OTBR's radio) | mesh-local `fd…` and OMR |
| Access | the OTBR's Wi-Fi and your hotspot | the OTBR's IPv4 and IPv6 |
| Services | a cloud endpoint, or your laptop's dashboard | public IPv4 / IPv6 |
| User | Daniela's phone | whatever the carrier gives it |

Score the OTBR against the six functions of Table A.3 with today's evidence: which does
it do, and which is it not doing yet?

## Deliverables

Update [your DDR](../docs/ddr_template.md):

- **§2 Lab log, "To Daniela":** can she see and act from her phone, at what latency, and
  what happens when the OTBR dies (Tasks D and F).
- **§3 ADR-005, one OTBR for the pilot:** decision, Task D–F numbers as rationale, and
  the single point of failure it accepts for off-mesh reach only.
- **§4 ISO mapping:** the Table A.3 quote with your six-function scorecard, and the
  four-network table filled with your addresses. Tag the OTBR an SCD-hosted IoT gateway.
- **§5 First principles:**
  1. Why does a prefix advertisement plus SLAAC make S reachable from outside, with no
     gateway "magic"?
  2. Why is NAT64 needed when Thread is IPv6?
  3. Why are the bytes of `/env/temp` the same on both sides of the OTBR?
  4. Why should a mains-powered gateway turn Wi-Fi power save off, when a battery
     node would do the opposite?
- **§6 Performance:** the rows "Lab 5: OTBR added latency" (< 100 ms) and "Lab 5: NAT64
  RTT" (< 200 ms).
- **§7 Ethics and sustainability:** *sustainability*: Task F's evidence; *security*:
  anyone holding the OTBR's USB cable controls it (no authentication on the shell);
  *privacy*: anyone on the hotspot can now read S and command the valve (→ Lab 6).
- **§8 Viewpoints:** rows for the enterprise system pattern (A.3 / Figure A.5) and the
  enterprise networking pattern (A.4 / Figure A.6).

## Grading (100 pts)

| | pts |
|---|---|
| **Technical execution** — OTBR running with an OMR prefix and NAT64 in the network data (10) · S and C on the OTBR's network with OMR addresses (10) · laptop and phone reach S (10) · OTBR-off test (10) | 40 |
| **ISO/IEC 30141** — Table A.3 scorecard with evidence (10) · four-network walk with your addresses (10) · OTBR placed as SCD-hosted gateway, RAID not over-claimed (10) | 30 |
| **First principles** — Q1–Q4 (5 each) | 20 |
| **Communication** — ADR-005 with numbers (5) · the "To Daniela" log (5) | 10 |
| **Ethics (pass/fail)** — OTBR-off evidence; the shell and privacy gaps flagged | ✓ |

## Resources & next week

ISO/IEC 30141:2024 §A.4 (Table A.3, Figure A.5) and §A.5 (Table A.4, Figure A.6) ·
RFC 4862 (SLAAC) · RFC 4191 (Route Information Option) · RFC 6052 and RFC 6146 (NAT64) ·
Zephyr's [OpenThread Border Router sample](https://docs.zephyrproject.org/latest/samples/net/openthread/border_router/README.html)

**Lab 6:** anyone on the hotspot can now read S and open the valve. Next week puts a lock
on the bytes.
