# SOP-02: Mesh Bring-up and Routing Experiments

- **Serves:** [Lab 2](../lab2.md)
- **Hardware:** 3 ESP32-C6 boards (any mix of DevKitC-1, DevKitM-1 and Super Mini) and
  their USB-C cables
- **Firmware:** [`firmware/lab2_mesh`](../../firmware/lab2_mesh); Zephyr as pinned in
  [setup](../../docs/setup.md)

Steps, checks and fixes only; the questions are in the lab. Shell basics (ports, the
Super Mini's USB console, `ot ping` syntax) are in [SOP-01](sop01_radio.md).

## 1. Build and flash

```bash
source ~/zephyrproject/env.sh
cd firmware/lab2_mesh
west build -p always -b esp32c6_devkitc/esp32c6/hpcore .
west flash
west espressif monitor -p /dev/ttyUSB0
```

On a Super Mini add the USB console options from [SOP-01 §1](sop01_radio.md#1-build-and-flash)
(`usb_console.conf` and `usb_console.overlay` are in this folder too). Then wipe the Lab 1
dataset on every board: `ot factoryreset`.

**Verify:** `ot state` prints `disabled` and the RGB LED is off. The LED follows the role:

| LED | Role |
|---|---|
| off | disabled: Thread not started |
| red | detached: looking for a network |
| yellow | child |
| green | router |
| blue | leader |

## 2. Form the mesh

1. All three, the same TX power: `ot txpower 0` (or the value your instructor announces).
2. On A:

   ```
   uart:~$ ot dataset init new
   uart:~$ ot dataset channel 15            # your ADR-001 channel
   uart:~$ ot dataset commit active
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   uart:~$ ot dataset active -x
   ```

3. On B and C:

   ```
   uart:~$ ot dataset set active <hex from A>
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

**Verify:** A is blue (`leader`); B and C turn yellow (`child`), then green (`router`)
within about 2 minutes. On A:

```
uart:~$ ot router table
| ID | RLOC16 | Next Hop | Path Cost | LQ In | LQ Out | Age | Extended MAC     | Link |
+----+--------+----------+-----------+-------+--------+-----+------------------+------+
| 18 | 0x4800 |       63 |         0 |     0 |      0 |   0 | 7abd07c8af8e615c |    0 |
| 40 | 0xa000 |       59 |         1 |     3 |      3 |   6 | aaa77e92948b985c |    1 |
| 59 | 0xec00 |       40 |         1 |     3 |      3 |   7 | b2f77b15a94107af |    1 |
```

Three rows, A's own included (`Link 0`).

## 3. List the addresses

```
uart:~$ ot ipaddr
fdd7:c9f8:19bb:c91:0:ff:fe00:4800
fdd7:c9f8:19bb:c91:e661:999e:4a97:3a16
fe80:0:0:0:78bd:7c8:af8e:615c
Done
uart:~$ ot ipaddr mleid
uart:~$ ot ipaddr rloc
uart:~$ ot rloc16
uart:~$ ot extaddr
uart:~$ ot ipmaddr
ff33:40:fdd7:c9f8:19bb:c91:0:1
ff32:40:fdd7:c9f8:19bb:c91:0:1
ff02:0:0:0:0:0:0:2
ff03:0:0:0:0:0:0:2
ff02:0:0:0:0:0:0:1
ff03:0:0:0:0:0:0:1
ff03:0:0:0:0:0:0:fc
```

**Verify:** the leader shows one more unicast address than B and C, ending in `fc00`.

## 4. Force a two-hop path

`macfilter rss add-lqi` fixes the link quality a receiver assigns to frames from one
address; the frames still arrive.

```
# On A, with C's extended address (ot extaddr on C):
uart:~$ ot macfilter rss add-lqi <C-extaddr> 1
# On C, with A's:
uart:~$ ot macfilter rss add-lqi <A-extaddr> 1
```

**Verify:** within about a minute, C's row in A's `ot router table` shows `LQ In 1` and
`LQ Out 1`.

Count what B relays:

```
# On B:
uart:~$ ot counters mac reset
# On A:
uart:~$ ot ping <C-mleid> 64 20 0.5
# On B:
uart:~$ ot counters mac                  # read TxUnicast
```

RTTs by ML-EID, one ping run at a time:

```
uart:~$ ot ping <B-mleid> 64 20 0.5
uart:~$ ot ping <C-mleid> 64 20 0.5
```

**Verify:** each run ends in `20 packets transmitted, … Round-trip min/avg/max = …`.

## 5. The tractor test

1. On A, 200 pings, one a second:

   ```
   uart:~$ ot ping <C-mleid> 64 200 1
   ```

2. After about ten replies, **pull B's USB cable**. `ot thread stop` on B does not stand
   in for it: B's radio keeps acknowledging A's frames, so A sees no failed
   transmissions and waits for B's entry to expire instead (104 s on our desk, against
   9 s with B unplugged).

   **Verify:** replies stop, then resume; the summary line counts the lost ones.

3. Plug B back in. Auto-start is off and the dataset is saved, so on B:

   ```
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

   **Verify:** B is green again and C's row in A's router table shows B's router ID as
   Next Hop.

4. When you finish the lab: `ot macfilter rss clear` on A and C, `ot thread stop` on all
   three.

## 6. Count fragments

Clear the filters first (`ot macfilter rss clear` on A and C). The MAC counts frames, the
IP layer counts datagrams:

```
uart:~$ ot counters mac reset
uart:~$ ot counters ip reset
uart:~$ ot ping <B-mleid> 16 10 0.5
uart:~$ ot counters mac                  # TxUnicast
uart:~$ ot counters ip
TxSuccess: ...
TxFailed: ...
RxSuccess: ...
RxFailed: ...
```

Frames per ping = `TxUnicast / TxSuccess`. Repeat with 32, 48, 64, 80, 96, 128, 256, 512
and 1000 bytes, resetting both counters each time, then toward B's RLOC and toward C with
the §4 filters on again. A few extra frames per run are MLE housekeeping: round to the
nearest whole number.

| Size (B) | `TxUnicast` | `TxSuccess` | Frames per ping | RTT avg (ms) |
|---|---|---|---|---|
| 16 | | | | |
| … | | | | |

## 7. Kill the leader

1. On B: `ot leaderdata`. Note `Partition ID` and `Leader Router ID`:

   ```
   uart:~$ ot leaderdata
   Partition ID: 382947794
   Weighting: 65
   Data Version: 136
   Stable Data Version: 189
   Leader Router ID: 40
   ```

2. On B: `ot ping <C-mleid> 64 300 1`. Then pull A's USB cable and note the time.
3. Every 15 s, on B and C: `ot state` and `ot leaderdata`.
4. Plug A back in, `ot ifconfig up`, `ot thread start`, and watch which partition ID
   survives.

**Verify:** one of B or C turns blue; at the end all three boards report the same
partition ID.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Error 13: InvalidState` on `ot thread start` | The interface is down | `ot ifconfig up` first |
| Stuck in `detached` (red) | The dataset doesn't match | Re-export with `ot dataset active -x`, paste the whole string |
| B or C turns blue for a moment | It started before it heard A and formed its own partition | Wait: partitions that hear each other merge within a minute |
| Stuck in `child` (yellow) past 2 minutes | Router promotion waits up to 120 s; or routing disabled | Wait; then check `ot routereligible` is `Enabled` |
| A board joins an old Lab 1 network | Its dataset survived reflashing | `ot factoryreset`, then §2 again |
| C's row never shows LQ 1 | The filter was added with the wrong address, or on one side only | `ot macfilter rss` on A and C lists the entries; use the other board's `ot extaddr` |
| The first ping to a new ML-EID is lost | A is looking up where that address lives (address query) | Not a radio loss: ignore the first reply |
| Healing takes about 100 s | B was stopped with `ot thread stop`, not unplugged | Pull the cable (§5.2) |
| Pings in two terminals inflate each other's RTT | Two ping runs share the channel | One run at a time |
