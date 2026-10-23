# SOP-01: Radio Bring-up and Link Measurements

- **Serves:** [Lab 1](../lab1.md)
- **Hardware:** 2 ESP32-C6 boards (DevKitC-1, DevKitM-1 or Super Mini) and their USB-C
  cables; a third board for §6
- **Firmware:** [`firmware/lab1_radio`](../../firmware/lab1_radio); Zephyr as pinned in
  [setup](../../docs/setup.md)

Steps, checks and fixes only; the questions are in the lab.

## 1. Build and flash

1. DevKitC-1 and DevKitM-1 have two USB-C ports: plug into the one labelled **UART**
   (`/dev/ttyUSB0`). The other port flashes too, but shows no console.

   ```bash
   source ~/zephyrproject/env.sh
   cd firmware/lab1_radio
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore .
   west flash
   west espressif monitor -p /dev/ttyUSB0       # Ctrl-] to exit
   ```

2. A **Super Mini** has only the chip's USB port (`/dev/ttyACM0`). Move the console there
   when you build:

   ```bash
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
       -DEXTRA_CONF_FILE=usb_console.conf -DEXTRA_DTC_OVERLAY_FILE=usb_console.overlay
   west flash
   west espressif monitor -p /dev/ttyACM0
   ```

3. A board borrowed from another team keeps its Thread dataset across reflashing. Wipe it
   once: `ot factoryreset`.

**Verify:** press Enter for the prompt, then:

```
uart:~$ ot state
disabled
Done
```

## 2. Scan the channels

```
uart:~$ ot ifconfig up
uart:~$ ot scan energy 500
```

`ot ifconfig up` turns the receiver on; nothing is transmitted. The scan listens 500 ms on
each channel.

**Verify:** one row per channel, 11 to 26 (this scan is from a desk at UNAL):

```
| Ch | RSSI |
+----+------+
| 11 | -102 |
| 12 | -102 |
...
| 17 |  -86 |
...
| 26 | -103 |
Done
```

## 3. Form a two-board network

1. Both boards, with the TX power your instructor announces:

   ```
   uart:~$ ot txpower 0
   uart:~$ ot txpower
   0 dBm
   ```

2. On A, a new network on your channel:

   ```
   uart:~$ ot dataset init new
   uart:~$ ot dataset channel 15
   uart:~$ ot dataset commit active
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   uart:~$ ot dataset active -x
   0e0800000000000100004a0300001235060004001fffe00208b8f9...
   ```

3. On B, paste A's **whole** hex string. It carries the channel, the PAN ID and the random
   network key; typing the channel and PAN ID by hand never gets the key right.

   ```
   uart:~$ ot dataset set active <hex from A>
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

**Verify:** `ot state` prints `leader` on A within seconds. B prints `child`, then
`router` within about 2 minutes.

## 4. Measure RSSI and packet loss

1. Each partner reads the routing locator (RLOC) address, the one containing
   `:0:ff:fe00:`, and sends it to the other:

   ```
   uart:~$ ot ipaddr rloc
   fdd7:c9f8:19bb:c91:0:ff:fe00:4800
   ```

2. 100 pings of 64 bytes, 0.2 s apart (`ot ping <address> [size] [count] [interval s]`).
   One direction at a time:

   ```
   uart:~$ ot ping <partner-RLOC> 64 100 0.2
   ...
   100 packets transmitted, 100 packets received. Packet loss = 0.0%. Round-trip min/avg/max = 14/14.320/39 ms.
   ```

   **Verify:** the summary line. `Packet loss` is your PER.

3. The signal this board received from its neighbor:

   ```
   uart:~$ ot neighbor table
   | Role | RLOC16 | Age | Avg RSSI | Last RSSI | LQ In |R|D|N| Extended MAC     | Version |
   +------+--------+-----+----------+-----------+-------+-+-+-+------------------+---------+
   |   R  | 0xec00 |   9 |      -51 |       -51 |     3 |1|1|1| b2f77b15a94107af |       2 |
   ```

   **Verify:** one `R` row for your partner. Record **Avg RSSI**.

4. When you are done: `ot thread stop` and `ot ifconfig down` on both. **Verify:**
   `ot state` prints `disabled`.

## 5. MAC counters and retries

```
uart:~$ ot counters mac reset
uart:~$ ot ping <partner-RLOC> 64 1
uart:~$ ot counters mac
TxTotal: ...
    TxUnicast: ...
    TxAckRequested: ...
    ...
```

**Verify:** about 35 lines, `TxTotal` first and `RxErrOther` last.

The four lines you need:

| Counter | Counts |
|---|---|
| `TxAckRequested` | unicast frames sent that asked for an ACK |
| `TxRetry` | retransmissions |
| `TxErrCca` | frames dropped because the channel never came clear |
| `RxErrFcs` | frames received with a bad checksum |

Retries per frame, on both boards when the replies matter too:

```
uart:~$ ot mac retries direct 3
uart:~$ ot mac retries direct
3
uart:~$ ot mac retries direct 15         # restore the OpenThread default
```

Two pings at once, for the collision run: start `ot ping <partner-RLOC> 64 200 0.05` on
both boards at the same moment. **Verify:** both summaries print.

## 6. Sniff the channel

Promiscuous mode needs the Thread interface down, so use a third board:

```
uart:~$ ot thread stop
uart:~$ ot ifconfig down
uart:~$ ot channel 15                    # the A–B channel
uart:~$ ot promiscuous enable
```

**Verify:** every frame on the channel scrolls by as a hex dump, here a data frame and
its 5-byte ACK:

```
==============================[RX len=075]==============================
| 69 98 88 17 5A 00 A0 00 | 48 0D 94 02 00 00 01 5C | i...Z...H......\ |
| 06 A9 5A 1C 51 D4 A6 89 | 35 3D D9 33 06 F0 4A 66 | ..Z.Q...5=.3..Jf |
...
==============================[RX len=005]==============================
| 02 00 88 ED 0B          |                         | .....            |
```

Stop with `ot promiscuous disable`. The MAC header fields are little-endian:

```
69 98 | 88  | 17 5A  | 00 A0 | 00 48 | 0D 94 02 00 00 01 | ...
FCF   | Seq | PAN ID | Dst   | Src   | security header   | encrypted payload, MIC
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `west: command not found` | The environment isn't loaded in this terminal | `source ~/zephyrproject/env.sh` |
| The monitor stays blank on a DevKitC-1 or DevKitM-1 | Plugged into the USB port | Use the UART port, `/dev/ttyUSB0` |
| A Super Mini prints nothing | Built without the USB console options | Rebuild as in §1.2, monitor `/dev/ttyACM0` |
| `Detected size(4096k) smaller than the size in the binary image header(8192k)` | A 4 MB board; the build targets the DevKitC's 8 MB | Ignore it: everything fits in 4 MB |
| `Error 13: InvalidState` on `ot thread start` | The interface is down | `ot ifconfig up` first |
| B stays `detached` | The dataset doesn't match | Re-export with `ot dataset active -x` and paste the whole string |
| B joins another team's network, or becomes a leader of its own | A dataset left on a borrowed board | `ot factoryreset`, then §3 again |
| B stays `child` for 2 minutes | Normal: router promotion waits a random time up to 120 s | Wait |
| PER jumps when both partners measure | Pings in both directions collide | One direction at a time |
| A→B and B→A RSSI differ by more than 10 dB | An antenna is blocked by a hand, a laptop or the table edge | Clear both antennas, measure again |
