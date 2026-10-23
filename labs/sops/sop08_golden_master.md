# SOP-08: The Golden Master and the Chaos Drills

- **Serves:** [Lab 8](../lab8.md)
- **Hardware:** every node of the team, the OTBR, a laptop on the hotspot
- **Firmware:** [`firmware/lab8_golden`](../../firmware/lab8_golden),
  [`firmware/lab5_border_router`](../../firmware/lab5_border_router) with `autostart.conf`
- **Host:** the Lab 7 fleet stack and bridge ([SOP-07](sop07_fleet.md)),
  [`tools/test_e2e.py`](../../tools/test_e2e.py)

Steps, checks and fixes only; the questions are in the lab.

## 1. Build the Golden Master

The key lives in `secrets.conf`, which git ignores:

```bash
source ~/zephyrproject/env.sh
cd firmware/lab8_golden
cp secrets.conf.example secrets.conf      # then put the team key in it, in quotes
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- -DEXTRA_CONF_FILE=secrets.conf
west flash
```

Super Mini: `-DEXTRA_CONF_FILE="usb_console.conf;secrets.conf" -DEXTRA_DTC_OVERLAY_FILE=usb_console.overlay`.
A sensor overlay goes in `EXTRA_DTC_OVERLAY_FILE` as in [SOP-04](sop04_sensors.md).

**Verify** the boot log; the node rejoins its stored network by itself:

```
<inf> lab8_golden: SoilSense Golden Master v1.0.0
<inf> watchdog: Watchdog armed: 10 s, hardware fallback on
<inf> lab8_golden: Rejoining the stored Thread network
<inf> lab8_golden: Thread role: router
```

and that the key stays out of git:

```bash
git check-ignore -v firmware/lab8_golden/secrets.conf
.gitignore:28:firmware/*/secrets.conf	firmware/lab8_golden/secrets.conf
git grep -n '<team-key>'            # no output
```

The version is in `VERSION`; the limits are Kconfig options (`LAB_RATE_LIMIT_MAX`,
`LAB_RATE_LIMIT_WINDOW_S`, `LAB_FAILSAFE_S`, `LAB_WATCHDOG_S`), set in `prj.conf`.

## 2. The OTBR that comes back

Rebuild the Border Router with its settings in flash ([SOP-05 §1](sop05_border_router.md#1-wire-and-flash-the-two-boards) for wiring and ports):

```bash
cd firmware/lab5_border_router
west build -p always -b esp32s3_devkitc/esp32s3/procpu . -- -DEXTRA_CONF_FILE=autostart.conf
west flash --esp-device /dev/ttyACM0
```

Store the hotspot and the network you formed in Lab 5, once:

```
uart:~$ wifi cred add -s <SSID> -k 1 -p <password>
uart:~$ ot dataset set active <hex from SOP-05 §2>
```

**Verify:** press reset and touch nothing. The log shows `Connecting to the stored Wi-Fi
network` and `Rejoining the stored Thread network`; within two minutes `wifi status` says
`COMPLETED`, `ot br state` says `running` and `ot br omrprefix` shows the same prefix as
before, so the nodes keep their OMR addresses.

## 3. Rate limit and fail-safe

1. **Burst.** From another node's shell, twelve GETs on one session:

   ```
   uart:~$ coaps get <node-omr> env/temp 12
   DTLS handshake: 1107 ms
   2.05, payload a16174f94e57, RTT 23 ms
   ... (8 in all)
   4.29, payload (none), RTT 23 ms
   ... (4 in all)
   ```

   **Verify** on the target: `<wrn> rate_limit: 4.29 to <peer>: over 8 requests in 10 s,
   retry in 10 s`. The 4.29 carries Max-Age = the seconds left in the window.

2. **Fail-safe.** Open a node's valve: `coaps put <node-omr> act/valve 1` from another
   node. Then cut it off: power off every other Thread device, or, on the target, deny
   every neighbour in `ot neighbor table`:

   ```
   uart:~$ ot macfilter addr add <ext-mac>        # once per neighbour
   uart:~$ ot macfilter addr denylist
   ```

   **Verify** on the target, with timestamps:

   ```
   [00:15:09.524] <inf> lab8_golden: Thread role: leader
   [00:15:39.556] <wrn> valve: FAILSAFE: no neighbour for 30 s with the valve open: closing it
   ```

   Thread needs about two minutes to declare the neighbours gone (the node forms its own
   partition); `LAB_FAILSAFE_S` counts from there. Undo with `ot macfilter addr disable`,
   `ot macfilter addr clear`.

## 4. The chaos drills

Hands off: watch the dashboard and the logs; only the drill's own action touches hardware.
Note the wall time of each action.

| # | Drill | Action | Pass |
|---|---|---|---|
| 1 | Cold start | All off. Power the nodes first, the OTBR last (its C6 before its S3) | Every node green in < 120 s after the last plug |
| 2 | Blackout | Unplug the OTBR for 10 min, then plug it back | Nodes keep a mesh meanwhile (`coaps get` between two nodes); every node green < 120 s after the OTBR returns |
| 3 | Parent loss | Power off the router a node depends on (`ot neighbor table`, best RSSI) | The node re-routes; with no neighbour left, §3's fail-safe fires |
| 4 | Flood | Run §5 while the bridge runs | No reboot; the dashboard keeps updating |
| 5 | Random reboots | Reset each node once, 30 s apart; on one, `health stall` | Every node back on the dashboard unaided; the stalled one resets in 10 s |
| 6 | Soak | 12 h unattended | Uptime only grows; `hsfail` flat |

`health stall` blocks the system workqueue; the watchdog resets the node:

```
<wrn> health: Stalling the system workqueue
rst:0xc (SW_CPU),boot:0xc (SPI_FAST_FLASH_BOOT)
<inf> lab8_golden: SoilSense Golden Master v1.0.0
```

## 5. The e2e suite and the pentest

1. From the laptop, with the Zephyr virtual environment (it has `cryptography`) and
   `cbor2`:

   ```bash
   python tools/test_e2e.py <node-omr> --psk <team-key> [--valve <valve-omr>]
   ...
     PASS  DTLS session: handshake 338 ms
     PASS  stress (20 paced GETs): 20/20 served, latency min/avg/max 59/123/194 ms
     PASS  burst -> 4.29: first 4.29 at request 9

   10 passed, 0 failed
   ```

2. **Wrong network key.** On a spare board (save its dataset first with
   `ot dataset active -x`):

   ```
   uart:~$ ot thread stop
   uart:~$ ot ifconfig down
   uart:~$ ot dataset init active
   uart:~$ ot dataset networkkey 00112233445566778899aabbccddeeff
   uart:~$ ot dataset commit active
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

   **Verify:** after `detached` it becomes `leader` of a partition of its own:
   `ot neighbor table` is empty and `ot partitionid` differs from the team's. Restore with
   `ot dataset set active <saved hex>`.

3. **Wrong DTLS key.** `python tools/coap_client.py --host <node-omr> --psk wrong get /env/temp`
   while the dashboard is open. **Verify:** *failed handshakes* turns red at the node's
   next report.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No DTLS key: copy secrets.conf.example ...` at build | `secrets.conf` missing or not passed | §1: copy it, add `-DEXTRA_CONF_FILE=secrets.conf` |
| `malformed string literal` at build | The key in `secrets.conf` isn't in double quotes | `CONFIG_LAB_PSK="<team-key>"` |
| The OTBR comes back without Wi-Fi | No stored credentials | `wifi cred list`; §2 again |
| The OTBR comes back on a new network | It was built without `autostart.conf` | Rebuild as in §2 |
| A node's `failed handshakes` rises during a blackout | Handshakes cut off by the outage count as failures | Expected; note the count before and after the drill |
| The e2e burst gets no 4.29, or the stress test fails | The bridge shares the laptop's rate-limit slot | Stop the bridge during §5.1, or raise `LAB_RATE_LIMIT_MAX` |
| `FAILSAFE` never fires | The node still hears a neighbour, or the valve was closed | `ot neighbor table` must be empty; `coaps get <node-omr> act/valve` |
| The node resets every 10 s | A monitored loop blocks: sampler or system workqueue | The log line before `rst:`; nothing slow in a CoAP handler |
