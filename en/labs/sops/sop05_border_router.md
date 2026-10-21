# SOP-05: OpenThread Border Router (OTBR) Deployment

> **Lab guide:** [Lab 5](../lab5.md) — read it first; the networking-pattern artifact, tasks, and DDR deliverables live there.
> **This SOP:** RCP flash, OTBR firmware build, commissioning, end-to-end reach test, troubleshooting. Total student-authored C: **zero**. Both firmwares come straight from `$IDF_PATH/examples/openthread/`.

The Thread mesh from [Lab 2](../lab2.md), the `/env/temp` and `/act/valve` servers from [Lab 3](../lab3.md) (with the [Lab 4](../lab4.md) sensor) are prerequisites. ESP-IDF v5.1+ (we tested on v5.5.3). **Additional hardware required for this lab:**

- 1× **Border Router host** — a board with Wi-Fi *and no in-mesh role*. Any of:
  - **ESP32-DevKit** (classic, 2.4 GHz Wi-Fi + BT, no 802.15.4) — *recommended for SoilSense*: it's what most groups already own, and it preserves every ESP32-C6 for in-mesh duty.
  - **ESP32-S3-DevKitC-1** — also works, identical procedure (just `set-target esp32s3`).
  - **ESP32-C6-DevKitC-1** — single-SoC mode is supported but **not recommended** for sustained traffic. The C6 has one RF path shared between Wi-Fi and 802.15.4, so it can't RX on both at once. Espressif themselves discourage this for production. Fine for a quick demo, lossy for the Task C measurement.
- 1× **ESP32-C6-DevKitC-1** dedicated as **RCP** (Radio Co-Processor — *in addition to* Nodes A / B / V from Labs 3–4). The `ot_rcp` example also builds for ESP32-H2 if you have one.
- 3× jumper wires for UART between host and RCP (or use USB-to-USB — see §1 wiring note).
- 2.4 GHz Wi-Fi network the host can join (your laptop's hotspot is fine; the BR host doesn't speak 5 GHz).

**Why two boards.** The host has Wi-Fi but no 802.15.4 radio (or, on a C6, the radio time-shares with Wi-Fi and loses); the RCP-C6 has 802.15.4 but contributes no IP stack — it's a "dumb modem" exposing its radio over UART using the Spinel protocol. The host runs the OpenThread + Border Router application and drives the RCP. Together they form one logical Border Router. This is the same architecture as the openthread.io reference (Raspberry Pi + USB RCP stick) and every off-the-shelf Matter BR (Apple TV, Nest Hub, eero).

> **What this SOP assumes from here on:** **ESP32 host + ESP32-C6 RCP** as the primary path. If your group is using S3 host, every `esp32` target name and pin reference below maps 1:1 — just substitute `esp32s3`.

---

## 1. Flash the Radio Co-Processor (RCP)

The RCP firmware ships in ESP-IDF. No student C.

```bash
cd $IDF_PATH/examples/openthread/ot_rcp
idf.py set-target esp32c6
idf.py build
idf.py -p /dev/ttyUSB_RCP flash       # the C6 you're dedicating as RCP
```

Pick a USB port name that you can keep straight from your other C6 boards — `/dev/ttyUSB_RCP` is a symlink suggestion; use the actual device path on your machine. **Note the port:** the OTBR host needs it.

Once flashed, this board does *nothing visible*. It has no CLI, no LEDs of consequence. It only speaks Spinel-over-UART when the host asks it to. If you `idf.py monitor` you'll see startup logs and then silence — that's correct.

> **Wiring it to the host.** Three jumper wires + a common ground, host-to-RCP UART, per the IDF `ot_br` README:
>
> | Host pin       | RCP-C6 pin     |
> |----------------|----------------|
> | **GPIO 4** (host RX) | **GPIO 5** (RCP TX) |
> | **GPIO 5** (host TX) | **GPIO 4** (RCP RX) |
> | **GND**              | **GND**        |
>
> Cross the data lines: host RX ↔ RCP TX. **Do not** connect 3.3 V or 5 V between boards — power each over its own USB. Pins are set in the example's default Kconfig (`Component config → OpenThread → RCP UART RX/TX pin`); change them only if your board breaks GPIO 4/5 out somewhere awkward.
>
> *Alternative for groups with limited jumper wires:* USB-to-USB also works — plug the RCP-C6 into a second USB port on the host laptop and point the OTBR menuconfig at the RCP's `/dev/tty*` directly. The RCP firmware speaks Spinel over its USB-UART bridge just fine, but you need to tell menuconfig the right device path.

---

## 2. Flash and launch the OTBR host

```bash
cd $IDF_PATH/examples/openthread/ot_br
idf.py set-target esp32        # use esp32s3 if your host is an S3; esp32c6 for single-SoC
idf.py menuconfig
```

In `menuconfig`, enable the **manual** Wi-Fi + Thread bring-up path. Everything else stays default:

```
Component config → OpenThread → OpenThread CLI ESP Extension       [*]   # adds `ot wifi`, etc.
Component config → OpenThread → Enable OpenThread network auto start [ ]  # leave off
Component config → OpenThread Border Router Config → Enable the border router auto start [ ]  # leave off
```

The Spinel UART pins are correct by default (RX = GPIO4, TX = GPIO5 on the host). If you ran a different wiring in [SOP-05 wiring](#wiring-it-to-the-s3-host), change them now under `Component config → OpenThread → RCP UART RX/TX pin`.

Save, exit, build, flash:

```bash
idf.py build
idf.py -p /dev/ttyUSB_HOST flash monitor
```

On the host monitor you'll see OpenThread come up and start talking to the RCP. The line that confirms the radio link is alive:

```
I (4321) OPENTHREAD: Platform UART init done
I (4400) OPENTHREAD: NCP started
```

You will **not** see `BR is started` yet — that comes after you bring up Wi-Fi and form the Thread network manually in §3. The host's Wi-Fi is also not connected yet; the `>` prompt in the monitor is the `ot` CLI, same as Labs 2–4.

> **Note on the web UI.** Some OTBR distributions ship a browser-based GUI (Raspberry Pi `otbr-web`, the separate `esp-thread-br` SDK). The IDF `examples/openthread/ot_br` we're using **does not**. Everything below happens on the `ot` CLI inside `idf.py monitor`. The CLI is what production OTBRs are managed with anyway — the GUI is sugar.

---

## 3. Bring up Wi-Fi and form the Thread network — from the `ot` CLI

Everything in this section is typed at the `>` prompt in `idf.py -p /dev/ttyUSB_HOST monitor`. Three phases: connect Wi-Fi → form Thread network → start the BR.

### 3.1 Join the home / lab Wi-Fi

```
> ot wifi connect -s <SSID> -p <password>
ssid: <SSID>
psk: <password>
...
I (13741) esp_netif_handlers: sta ip: 192.168.x.x, mask: ..., gw: ...
wifi sta is connected successfully
Done

> ot wifi state
connected
Done
```

Write down the IPv4 the host got — it's the address the laptop will use as a route gateway. (The OTBR has no HTTP server on it, so you won't open this in a browser.) 2.4 GHz Wi-Fi only; the ESP32 / ESP32-S3 / ESP32-C6 BR hosts all share this limit.

### 3.2 Form a fresh Thread network

Same workflow as [SOP-02](sop02_6lowpan.md), now on the BR:

```
> ot dataset init new
Done

> ot dataset panid 0xCAFE          # non-default PAN ID; pick your own
Done

> ot dataset channel 15            # or whatever your room uses; avoid 25–26 if Wi-Fi is on chan 11
Done

> ot dataset networkname SoilSense-OTBR
Done

> ot dataset commit active
Done

> ot ifconfig up
Done

> ot thread start
Done
```

Wait ~10 seconds, then confirm:

```
> ot state
leader
Done
```

The BR is now the Thread network Leader. It is **not yet** publishing a global IPv6 prefix to the mesh — that happens in §3.3.

### 3.3 Start the Border Router (publish prefix + NAT64)

```
> ot br init 1 1                   # init BR functionality; arguments are interface index + nat64 enable
Done

> ot br omrprefix
Local: fd<six hex>::/64
Done
```

The "OMR prefix" (Off-Mesh Routable) is the global-ish IPv6 prefix the BR will advertise to the mesh nodes via Router Advertisement. Once any node joins, every node gets an additional IPv6 address with this prefix — that's the address external clients use to reach `/env/temp`.

Verify:

```
> ot br state
running
Done

> ot netdata show
Prefixes:
fd<...>::/64 paros med <RLOC>      # the OMR prefix — paros flags = SLAAC + on-mesh + default route + stable
Routes:
fd<...>::/64 s med <RLOC>
Done
```

If `Prefixes:` is empty, run `ot br init 1 1` again. If the line is present but missing the `aros` flags, the prefix won't be auto-configured by the joining nodes — re-run `ot br init`.

### 3.4 Copy the dataset

Before commissioning Node A and Node V, grab the dataset hex blob the nodes will need:

```
> ot dataset active -x
0e08000000000001000035060004001fffe002083333222211110000...
Done
```

Copy this single long hex line. §4 pastes it on each node.

---

## 4. Re-commission Node A and Node V onto the OTBR-formed mesh

The Lab 3–4 boards are still running their existing CoAP server firmware (`/env/temp` on Node A; `/act/valve` on Node V). You don't reflash them — you only move them to the new network using the dataset hex you copied in §3.4.

On each of Node A and Node V:

```
> dataset clear
Done
> dataset set active <paste the hex from §3.4>
Done
> ifconfig up
Done
> thread start
Done
```

After 30–60 s, `state` on each should report `child` or `router` (Node V is MTD/SED → `child`, Node A is FTD → `router`). Confirm from the BR's CLI that they joined:

```
> ot child table       # Node V (SED) appears here
| ID  | RLOC16 | Timeout | Age | LQ In | ...
+-----+--------+---------+-----+-------+...
|   1 | 0xc401 |   240   |  12 |     3 | ...
Done

> ot router table      # Node A (FTD) appears here
| ID | RLOC16 | Next Hop | ...
+----|--------|----------+...
| 50 | 0xc800 |   self   | ...
| 12 | 0x3000 |    50    | ...        ← Node A
Done
```

This is the CLI equivalent of the topology view a GUI would draw. Take a screenshot of the monitor showing both tables for your DDR.

Node B (the CLI client from Labs 3–4) — your call. If you want to keep an in-mesh client around for the Task C baseline measurement, re-commission it the same way. Otherwise leave it on the old network and skip the in-mesh baseline.

---

## 5. Confirm global addresses on the nodes

On Node A (after it joined):

```
> ipaddr
fd<otbr-mesh-local>::1                  ← mesh-local EID, only valid inside the mesh
fd<otbr-global-prefix>::ff:fe00:0001    ← global, derived from the prefix the OTBR advertised
fe80::1234:5678:9abc:def0               ← link-local, normal
```

You should see **at least two non-link-local** addresses now (mesh-local + global), where Lab 3/4 you only saw one. The second one — the global — is what an external client (your laptop, on Wi-Fi) targets.

`ipaddr mleid` still returns the mesh-local one (unchanged from Lab 3/4).

Do the same on Node V. Both nodes should report a global address with the **same prefix** the OTBR advertised in §3.

---

## 6. Task C — measure the OTBR's added latency

### 6.1 In-mesh baseline (reproduce the Lab 3 number)

From Node B's CLI (assuming you kept it on the OTBR-formed mesh):

```
> coap start
> coap get fd<...>::A /env/temp        ← Node A's mesh-local address
```

Time 10 round-trips. Median should match your Lab 3 baseline within ±20 ms.

### 6.2 Through the OTBR — from your laptop on Wi-Fi

The laptop already has the OTBR's global prefix routed to it because the OTBR sent a Router Advertisement on its Wi-Fi side. Confirm:

```bash
ping6 -c 3 fd<otbr-global-prefix>::ff:fe00:0001     # Node A's global IPv6
```

You should get replies. If not, see Troubleshooting.

Now hit the CoAP server from the laptop using the project's existing Python client:

```bash
python tools/coap_client.py --host "fd<otbr-global-prefix>::ff:fe00:0001" get /env/temp
```

The 6-byte CBOR comes back, identical to what Node B saw in §6.1 — same `a16174f9....` bytes. Time 10 round-trips. The delta vs §6.1 is the OTBR's added cost.

### 6.3 NAT64 — Thread sensor pings the IPv4 internet

NAT64 is enabled by default in Espressif's ot_br with the `64:ff9b::/96` prefix. From Node A's CLI:

```
> ping 64:ff9b::8.8.8.8
```

You should see replies. Failures here usually mean the OTBR's upstream DNS64 isn't resolving (Espressif's ot_br implements NAT64 *translation*, but if you used a literal IPv4-mapped IPv6 form the request still needs to leave the AP — your home router has to actually route IPv6 out, which not every consumer router does). If your AP is IPv6-only at the WAN, this works; if it's IPv4-only at the WAN, you may see "no route". That's an interesting fact for your DDR §5, not a failure of the lab — record what happened.

---

## 7. (Optional) End-to-end from outside the LAN

**Not required for the lab.** If you want to demonstrate the full four-network walk (Daniela on her phone, off your Wi-Fi) you have two options:

- **Tailscale / ZeroTier / Tunnel:** put the laptop CoAP client on a tunnel; the phone joins the tunnel; the CoAP path is laptop-routed. Simple, doesn't expose anything publicly.
- **Public CoAP test server as the "cloud":** modify Node A to *also* be a CoAP client that POSTs to `coap.me` periodically. Wireshark on the OTBR side will show the packets leaving via NAT64.

Either way, the bytes on the wire are still the same `/env/temp` CBOR. The boundary between "services" and "user" networks (Table A.4) is below the application — the OTBR doesn't care.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ot netdata show` lists no prefix, or the prefix lacks `aros` flags | You skipped `ot br init 1 1` in §3.3, or it ran before `thread start` settled. Re-run `ot br init 1 1`, wait 5 s, run `ot netdata show` again. |
| `ipaddr` on Node A shows only mesh-local + link-local (no global) | The node joined the mesh *before* the prefix was advertised. `ifconfig down; ifconfig up; thread start` on the node to re-SLAAC. |
| Laptop `ping6` to the global address times out | (1) The OTBR is not advertising a default route — check **Network → Settings → Default Route**, must be ticked. (2) Your laptop's Wi-Fi has IPv6 disabled; turn it on in network settings. (3) Your AP filters IPv6 RAs — try a phone hotspot instead. |
| `coap get` from the laptop returns "no route to host" but `ping6` works | The CoAP client is binding the wrong source interface. Pass `--bind-iface` (or set `IPV6_BOUND_IF` env var) to force the Wi-Fi interface. |
| `ping 64:ff9b::8.8.8.8` from Node A → "Error 13: No route to host" | NAT64 prefix not installed. Check `ot br nat64state` on the BR — both `Translator` and `PrefixManager` should be `Active`. If they aren't, re-run `ot br init 1 1` (second `1` is the NAT64 enable flag). If your AP has no IPv4 upstream, NAT64 will install but won't reach Google — try a phone hotspot. |
| RCP not detected by host (`NCP not responding`, `Spinel: failed to send command`) | Three usual causes, in order: **(1) TX/RX swapped** between host and RCP — swap the two data wires; **(2) GND not connected** — add the third wire; **(3)** `Spinel UART device`/RX/TX pins in menuconfig don't match how you wired. On Linux, `dmesg \| tail` after plugging shows the device path. |
| Node A's old `dataset` from Lab 3 prevents joining | `dataset clear` *before* `dataset set active`. The CLI doesn't overwrite the existing dataset automatically. |
| `state` stays `detached` on Node A after re-commissioning | Channel mismatch — the OTBR auto-picks a channel that may differ from your Lab 3 dataset. The `dataset set active <hex>` *includes* the channel; if you typed it instead of pasted, retype carefully or paste again. |
| `ot wifi connect` fails or `ot wifi state` says `disconnect` | Wrong SSID/password, or the AP is 5 GHz-only. The ESP32 / S3 / C6 are all 2.4 GHz only. Try a phone hotspot on 2.4 GHz to isolate. |

---

## Verification checklist (what to put in your DDR)

- [ ] BR-side **CLI topology**: `ot child table` and `ot router table` outputs on the BR's monitor showing Node A as a router and Node V as a child. Screenshot of the monitor counts.
- [ ] Node A `ipaddr` output, annotated: which line is mesh-local, which is global. Same for Node V.
- [ ] Task C three-row latency table from [lab5.md §4](../lab5.md#task-c--end-to-end-reach-and-the-latency-it-costs-the-headline-number) with all rows filled.
- [ ] Evidence that the local mesh survived an OTBR kill — from Node B (in-mesh), a `coap put` to Node V's *mesh-local* address still landed after the OTBR was stopped. (`ot thread stop` on the BR host, or just pull its USB.)

---

## Appendix — Optional: putting the dashboard back in (stretch goal)

**Not required for the lab.** The Lab 3 dashboard appendix decoded notifications from Node B's monitor stream. Now that the OTBR exposes a routable address for `/env/temp`, you can run the dashboard **on your laptop** instead of pulling notifications from a serial pipe — it makes CoAP look ordinary (over Wi-Fi).

```bash
pip install aiocoap flask
python tools/dashboard_coap.py --remote "fd<global-prefix>::ff:fe00:0001" --resource /env/temp --observe
```

Open `http://localhost:5000`. Same Chart.js view as Labs 0 / 0.5 / 3. What changed: the dashboard now subscribes via CoAP Observe *over Wi-Fi → OTBR → Thread* — three networks of Table A.4 in one path. This is the configuration we make first-class in Lab 6 once DTLS is added.

> **Why we keep this optional in Lab 5:** the lab's headline is the **boundary** and its **latency cost**, not the visualization. The `ot child table` / `ot router table` output and the Task C latency table answer the rubric. Dashboard is for the demo, not the grade.
