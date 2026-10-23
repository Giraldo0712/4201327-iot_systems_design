# SOP-05: Border Router

> **Lab guide:** [Lab 5](../lab5.md). This SOP holds the commands, the wiring and the
> fixes; the questions and the deliverables are in the lab.

The OTBR is two boards acting as one. The **ESP32-S3** runs Zephyr's OpenThread Border
Router ([`firmware/lab5_border_router`](../../firmware/lab5_border_router)): Wi-Fi,
IPv6 routing, NAT64 and the `ot` shell. The **ESP32-C6 RCP** runs
[`firmware/lab5_rcp`](../../firmware/lab5_rcp): only the 802.15.4 radio, driven by the
S3 over a UART with the Spinel protocol.

The S3 must have PSRAM: the boot log prints `Found 8MB PSRAM device`. N8R8 and N16R8
boards work; boards without PSRAM (N4, N8) can't hold OpenThread and Wi-Fi together.

## 1. Wire and flash the two boards

1. Install the S3's compiler once (the C6's RISC-V one is already there from Week 0):

   ```bash
   source ~/zephyrproject/env.sh
   west sdk install -t xtensa-espressif_esp32s3_zephyr-elf
   ```

2. Wire the UART, crossed, plus ground. Power each board over its own USB cable, never
   3V3 or 5 V between them:

   | ESP32-S3 | ESP32-C6 (RCP) |
   |---|---|
   | GPIO5 (TX) | GPIO4 (RX) |
   | GPIO4 (RX) | GPIO5 (TX) |
   | GND | GND |

   Plug the C6 in **before or together with** the S3: a powered S3 feeds the
   unpowered C6 through its RX pin and browns itself out.

3. Flash the RCP. With several boards plugged in, name the port:

   ```bash
   cd firmware/lab5_rcp
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore .
   west flash --esp-device /dev/ttyUSB1
   ```

   **Verify:** nothing. The RCP has no shell; its logs travel to the S3 inside Spinel.

4. Flash the S3 through its **UART** port and open its shell there:

   ```bash
   cd ../lab5_border_router
   west build -p always -b esp32s3_devkitc/esp32s3/procpu .
   west flash --esp-device /dev/ttyACM0
   west espressif monitor -p /dev/ttyACM0
   ```

   **Verify:**

   ```
   uart:~$ ot rcp version
   OPENTHREAD/e4d97681c; Zephyr; ...
   Done
   ```

## 2. Join Wi-Fi and form the Thread network

1. On your phone, set the hotspot to **2.4 GHz** and **WPA2** (iPhone: *Maximize
   Compatibility*; Android: band 2.4 GHz, security WPA2-Personal). Then:

   ```
   uart:~$ wifi connect -s <SSID> -p <password> -k 1
   Connected
   <inf> net_dhcpv4: Received: <otbr-ipv4>
   ```

   **Verify:** `wifi status` shows `State: COMPLETED` and `Band: 2.4GHz`. Write down the
   IPv4 address.

2. Form a new network on your assigned channel (15, 20, 25 or 26):

   ```
   uart:~$ ot dataset init new
   uart:~$ ot dataset channel 25
   uart:~$ ot dataset panid 0x5a17
   uart:~$ ot dataset networkname SoilSense-<team>
   uart:~$ ot dataset commit active
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

   **Verify:** `ot state` goes from `detached` to `leader`. That takes from under half a
   minute to a few minutes: OpenThread looks for an existing partition before founding
   its own.

3. Border routing starts by itself once both sides are up.

   **Verify:**

   ```
   uart:~$ ot br state
   running
   uart:~$ ot nat64 state
   PrefixManager: Active
   Translator: Active
   uart:~$ ot br omrprefix
   Local: fdab:819c:92ef:1::/64
   Favored: 2800:484:9080:855e::/64 prf:med
   uart:~$ ot netdata show
   Prefixes:
   2800:484:9080:855e::/64 paros med a000
   Routes:
   ::/0 s med a000
   fdab:819c:92ef:2:0:0::/96 sn low a000
   ```

   The `paros` line is the OMR prefix the mesh uses; the `/96` route is NAT64. This
   output comes from a home router that delegates a global prefix (`Favored`). A phone
   hotspot delegates none: the OTBR then uses its own `Local` ULA prefix (`fd…`).

4. Copy the dataset for §3, and keep it: the OTBR keeps its Thread settings in RAM, so
   after a reset you paste it back with `ot dataset set active <hex>`.

   ```
   uart:~$ ot dataset active -x
   0e080000000000010000000300001935060004001fffe0...
   ```

## 3. Move S and C onto the OTBR's network

1. Rebuild S (with its sensor overlay) and C from `firmware/lab4_sensors`, exactly as in
   [SOP-04 §2](sop04_sensors.md#2-build-s-and-c). The current firmware adds SLAAC and
   transmits at +20 dBm.

2. On each, forget Lab 4's network and take the OTBR's:

   ```
   uart:~$ ot factoryreset
   uart:~$ ot dataset set active <hex from §2.4>
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

   `ot factoryreset` reboots the board (a Super Mini also drops its USB port: reopen the
   monitor).

   **Verify:** `ot state` → `child`, then `router` within about 2 minutes. On the OTBR,
   `ot child table` and `ot router table` list both.

3. **Verify** on S:

   ```
   uart:~$ ot ipaddr
   2800:484:9080:855e:a683:e5fc:fe92:bf6   ← OMR: the OTBR's prefix, S's own IID
   fdd7:c9f8:19bb:c91:0:ff:fe00:a001       ← RLOC
   fdd7:c9f8:19bb:c91:e176:7bb0:393c:7fb6  ← mesh-local EID (ot ipaddr mleid)
   fe80:0:0:0:462:934e:69a:7f2f            ← link-local
   ```

## 4. Reach S from the laptop

1. Connect the laptop to the same hotspot. The OTBR announces the OMR prefix on Wi-Fi in
   its Router Advertisements (Route Information Option, RFC 4191).

   **Verify** the route (Linux, `wlan0` may be `wlp3s0`):

   ```bash
   ip -6 route | grep <omr-prefix>
   2800:484:9080:855e::/64 via fe80::2a84:85ff:fe59:cc68 dev wlp3s0 proto ra metric 600
   ```

   No route? Not every OS accepts that option. Add it by hand with the OTBR's Wi-Fi
   link-local address (`net iface` on the OTBR, interface `WiFi`):

   | OS | Command |
   |---|---|
   | Linux | `sudo ip -6 route add <omr>/64 via <otbr-ll> dev wlan0` |
   | macOS | `sudo route -n add -inet6 <omr>/64 <otbr-ll>%en0` |
   | Windows (admin) | `netsh interface ipv6 add route <omr>/64 "Wi-Fi" <otbr-ll>` |

2. Measure, 10 of each:

   ```bash
   ping -c 10 <otbr-ipv4>            # Wi-Fi hop; then `wifi ps off` on the OTBR and repeat
   ping -6 -c 10 <S-omr>             # laptop → OTBR → S
   pip install aiocoap cbor2 flask   # once, in a virtual environment
   python tools/coap_client.py --host <S-omr> --count 10 get /env/temp
   ```

   **Verify:** `10/10 responses, median RTT ... ms` and `Payload (CBOR): {'t': ...}`.

3. The dashboard, for your phone:

   ```bash
   python tools/dashboard_coap.py --host <S-omr>
   ```

   **Verify:** `http://localhost:5000` draws the temperature; from the phone, open
   `http://<laptop-ipv4>:5000` and press *Open*: S's log shows the PUT and its LED turns
   white.

## 5. NAT64 and the OTBR-off test

1. On S:

   ```
   uart:~$ ot ping 8.8.8.8
   Pinging synthesized IPv6 address: fdab:819c:92ef:2:0:0:808:808
   24 bytes from fdab:819c:92ef:2:0:0:808:808: icmp_seq=1 hlim=118 time=65ms
   ```

2. Unplug the S3. On C:

   ```
   uart:~$ ot coap start
   uart:~$ ot coap put <S-mleid> act/valve con 1
   coap response from fdd7:...:7fb6 with payload: a1617601
   ```

   To restore: power the S3, `ot dataset set active <hex>`, `ot ifconfig up`,
   `ot thread start`, `wifi connect ...`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| S3 resets in a loop, `rst:0xf (BROWNOUT_RST)` right after `Found 8MB PSRAM device` | The RCP is wired but unpowered, fed through its RX pin | Plug the C6 in first |
| No `Found ... PSRAM device`, boot stops | An S3 without PSRAM | Use an N8R8 or N16R8 |
| `Wait for response timeout` three times, then `Init() ... Failure` and `exit` | The S3 gets no answer from the RCP | Cross TX/RX, connect GND, check `lab5_rcp` is flashed |
| `RCP is missing required capabilities: tx-security tx-timing` | An RCP built from an older `lab5_rcp` | Pull and rebuild `lab5_rcp` |
| `Connection request failed (AP not found/4)` | Hotspot on 5 GHz, or SSID typo | 2.4 GHz; `wifi scan` lists what the S3 sees |
| `Connected` but no `net_dhcpv4: Received` | WPA3-only hotspot | Switch it to WPA2 |
| `ot state` stays `detached` for a minute or two | Normal on the first start | Wait |
| S or C becomes `leader` of its own network, or stays `detached` | It is restoring its Lab 4 role | `ot factoryreset`, then §3.2 again |
| `disabled` after `ot factoryreset` | Commands sent while it rebooted | `ot ifconfig up`, `ot thread start` |
| S has no OMR address | Firmware from before SLAAC | Pull and rebuild `lab4_sensors` |
| Pings to the OTBR take 100–300 ms and jump around | Wi-Fi power save | `wifi ps off` on the OTBR |
| Laptop has no route to the OMR prefix | The OS ignores the Route Information Option | Add the route (§4.1) |
| Ping to S works, the phone can't open the dashboard | The laptop's firewall | Allow TCP port 5000 |
| `ot ping 8.8.8.8` gets no reply | No IPv4 upstream on the hotspot, or the OTBR isn't `running` | `wifi status`, `ot nat64 state`, `ot br state` |
| After a reset the OTBR has no network | Thread settings live in RAM | `ot dataset set active <hex>` |
