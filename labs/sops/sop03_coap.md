# SOP-03: CoAP Client, Server and Dashboard

- **Serves:** [Lab 3](../lab3.md)
- **Hardware:** 2 ESP32-C6 boards, **S** (server) and **C** (client), and their USB-C cables
- **Firmware:** [`firmware/lab3_coap`](../../firmware/lab3_coap), the same image on both;
  Zephyr as pinned in [setup](../../docs/setup.md)
- **Contracts:** [SoilSense API](../../docs/api.md)

Steps, checks and fixes only; the questions are in the lab. Ports, the Super Mini's USB
console and `ot ping` are in [SOP-01](sop01_radio.md).

## 1. Build, flash and form the network

1. Both boards:

   ```bash
   source ~/zephyrproject/env.sh
   cd firmware/lab3_coap
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore .
   west flash
   west espressif monitor -p /dev/ttyUSB0
   ```

2. Both: `ot factoryreset`. Then form the network on **C** and join S with C's dataset, as
   in steps 2–3 of [SOP-02 §2](sop02_mesh.md#2-form-the-mesh). Leave the TX power alone:
   this firmware starts at +20 dBm.
3. On **C only**, start the CoAP client. On S, note its address:

   ```
   C: uart:~$ ot coap start
   S: uart:~$ ot ipaddr mleid
   fdd7:c9f8:19bb:c91:e661:999e:4a97:3a16
   ```

**Verify:** `ot state` prints `leader` on C and `router` (or `child`) on S.

## 2. Command reference

| Command | Does |
|---|---|
| `ot coap start` / `ot coap stop` | start / stop the OpenThread CoAP client on this board |
| `ot coap get <addr> <path> [con]` | GET; NON unless you add `con` |
| `ot coap put <addr> <path> [con\|non-con] [text]` | PUT with a text payload (no Content-Format) |
| `ot coap observe <addr> <path>` | GET with Observe: 0; notifications print as they arrive |
| `ot coap cancel` | deregister the current observation |
| `ot coap parameters request [default \| <ack_timeout_ms> <num> <den> <max_retransmit>]` | show or set the CON timers for requests |

The shell prints only the payload, as hex, never the response code: S's log has the code.
Paths have no leading `/`.

## 3. GET and time it

```
uart:~$ ot coap get <S-mleid> env/temp
Done
coap response from fdd7:c9f8:19bb:c91:e661:999e:4a97:3a16 with payload: a16174f94df7
```

**Verify:** S logs the other side, with the sizes:

```
<inf> env_temp: GET /env/temp from <C>: 2.05, <t> C, CoAP <n> B (CBOR <hex>), request <n> B
```

Ten GETs, timed. Close the monitor on C's port first: the script drives C's shell over
the same serial port.

```bash
pip install pyserial cbor2                  # once, with env.sh sourced
python tools/coap_client.py --serial /dev/ttyUSB0 --host <S-mleid> --count 10 get /env/temp
```

**Verify:** `Payload (CBOR): {'t': ...}` and `10/10 responses, median RTT ... ms`. The RTT
includes C's serial line; the ping comparison in the lab uses `ot ping <S-mleid> 16 10`.

## 4. Observe

```
uart:~$ ot coap observe <S-mleid> env/temp
coap response from fdd7:... OBS=3 with payload: a16174f94e43
...
uart:~$ ot coap cancel
```

**Verify:** S logs every notification with its reason and running counters:

```
<inf> env_temp: notify (threshold, NON): T=24.56 C, delta=0.53 C, 6s since last, CoAP 19 B [threshold 7, heartbeat 1]
```

## 5. Command the valve

```
uart:~$ ot coap put <S-mleid> act/valve con 1
coap response from fdd7:... with payload: a1617601
uart:~$ ot coap get <S-mleid> act/valve
coap response from fdd7:... with payload: a1617601
uart:~$ ot coap put <S-mleid> act/valve con 0
coap response from fdd7:... with payload: a1617600
```

**Verify:** S's LED is white while the valve is open. A bad payload (`con 7`) gets no
valve change; S's log shows the code.

Make S unreachable, then try:

```
S: uart:~$ ot thread stop
C: uart:~$ ot coap put <S-mleid> act/valve con 1        # start the stopwatch
C: uart:~$ ot coap put <S-mleid> act/valve non-con 1
S: uart:~$ ot thread start                               # wait for it to rejoin
```

**Verify:** the CON PUT ends in `coap receive response error 28: ResponseTimeout`.

## 6. Make S sleep

```
S: uart:~$ ot mode -                    # rx-off-when-idle, minimal device
S: uart:~$ ot pollperiod 1000           # milliseconds
S: uart:~$ ot state
child
```

Ping the sleeping S. The last argument is the timeout in seconds and must exceed the poll
period:

```
C: uart:~$ ot ping <S-mleid> 16 10 1.3 64 40
```

Change the poll period with `ot pollperiod 5000`, then `15000`. **Verify:** S's LED is
yellow and the ping summary prints.

Restore S when you are done: `ot mode rdn`, then `ot pollperiod 0`.

## 7. Run the dashboard

Close the monitor on C's port; the dashboard owns it while it runs.

```bash
pip install flask pyserial                  # once, with env.sh sourced
python tools/dashboard_coap.py --serial /dev/ttyUSB0 --node <S-mleid>
```

**Verify:** `http://localhost:5000` draws the temperature as notifications arrive, and
*Open* turns S's LED white. Stop it with Ctrl-C, then reopen the monitor.

## 8. Extensions

| File in `firmware/lab3_coap` | What it does |
|---|---|
| `src/main.c` | the CoAP service `soilsense` on UDP 5683; the role LED (white while the valve is open) |
| `src/env_temp.c` | `/env/temp`: the simulated sensor, the CBOR encoder, GET and the Observe policy |
| `src/valve.c` | `/act/valve`: PUT and GET, the CBOR and text decoder, the valve state |
| `sections-ram.ld`, `CMakeLists.txt` | collect every `COAP_RESOURCE_DEFINE(..., soilsense, ...)` into the list the server walks |

Resource discovery:

```
uart:~$ ot coap get <S-mleid> .well-known/core
```

Slower CON timers on the client, for a sleepy valve, and back:

```
uart:~$ ot coap parameters request 8000 3 2 4
uart:~$ ot coap parameters request default
```

A new resource `/env/hum`: copy the `COAP_RESOURCE_DEFINE` block and the GET handler from
`env_temp.c` into `src/env_hum.c`, add the file to `CMakeLists.txt`, and encode with
`zcbor_uint32_put()` instead of `zcbor_float16_put()`. The encoder needs
`ZCBOR_CANONICAL` (already set) for a definite-length map (`A1`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ot coap get` prints nothing and S logs nothing | `ot coap start` ran on S too: OpenThread then keeps port 5683 and S's server never sees a request | `ot coap stop` on S |
| `coap receive response error 28: ResponseTimeout` on a GET | Wrong address, or S isn't attached | `ot state` on S; use its `ot ipaddr mleid` |
| No reply although S is attached | A path typo or a leading `/`: S answers 4.04 to a `con` request only | `env/temp`, not `/env/temp` |
| Observe stops after a while | S dropped C after a failed CON heartbeat | `ot coap observe` again |
| `ot mode -` and S never becomes `child` | S was the leader, or C isn't a router | Form the network on C (§1) |
| Pings to the sleeping S time out | The ping timeout is shorter than the poll period | Raise the last `ot ping` argument |
| `coap_client.py` or the dashboard: `could not open port` | A monitor still holds C's port | Close the monitor |
| `coap_client.py --serial`: `no response within 10 s` on every request | S unreachable, or a wrong `--host` | Check with `ot coap get` from the monitor first |
