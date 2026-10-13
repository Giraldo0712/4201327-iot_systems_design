# SOP-03: CoAP Firmware Tour and Experiments

> **Main Lab Guide:** [Lab 3: CoAP](../lab3.md) — the contracts, tasks and deliverables
> live there.
> **ISO Domains:** ASD (Application & Service), SCD (Sensing & Controlling)
> **Firmware:** [`firmware/lab3_coap`](../../../firmware/lab3_coap), the same image on
> every board.

## 1. What's in the firmware

| File | What it does |
|---|---|
| `src/main.c` | Defines the CoAP service `soilsense` on UDP 5683, drives the role LED (white while the valve is open), and holds two helpers: `response_init()` and `peer_str()`. |
| `src/env_temp.c` | `/env/temp`: the simulated sensor (sampled every second), the CBOR encoder, GET, and the Observe policy (threshold → NON, heartbeat → CON). |
| `src/valve.c` | `/act/valve`: PUT and GET, the CBOR/text decoder, and the valve state. |
| `prj.conf` | OpenThread shell with its CoAP client (`OPENTHREAD_COAP`, `OPENTHREAD_COAP_OBSERVE`), the Zephyr CoAP server (`COAP_SERVER`), zcbor (`ZCBOR_CANONICAL`), the LED. |
| `sections-ram.ld` + `CMakeLists.txt` | Collect every `COAP_RESOURCE_DEFINE(..., soilsense, ...)` into one list the server walks. |

A resource is a path, a handler per method, and optionally a notify callback for
observers. Compare it with Lab 0's `HTTP_RESOURCE_DEFINE`:

```c
static const char *const env_temp_path[] = { "env", "temp", NULL };
COAP_RESOURCE_DEFINE(env_temp, soilsense, {
	.get = env_temp_get,
	.path = env_temp_path,
	.notify = env_temp_notify,
});
```

The CBOR encoder is four zcbor calls; `ZCBOR_CANONICAL` makes the map definite-length
(`A1`) instead of `BF … FF`:

```c
zcbor_map_start_encode(zs, 1) && zcbor_tstr_put_lit(zs, "t") &&
zcbor_float16_put(zs, t) && zcbor_map_end_encode(zs, 1)
```

## 2. Two CoAP stacks, one port

Every board runs the Zephyr CoAP server on port 5683 from boot. The shell's `ot coap`
client lives inside OpenThread, which also wants port 5683. They don't clash because of
how Zephyr hands packets between them: once `ot coap start` binds 5683 inside
OpenThread, OpenThread keeps every packet for that port and stops passing it up to
Zephyr's IP stack. So:

- the board where you ran `ot coap start` is a **client**, and its own server is deaf;
- every other board is a **server**.

`ot coap stop` hands the port back.

## 3. Command reference

| Command | Does |
|---|---|
| `ot coap start` / `ot coap stop` | start / stop the OpenThread CoAP client on this board |
| `ot coap get <addr> <path> [con]` | GET; NON unless you add `con` |
| `ot coap put <addr> <path> [con\|non-con] [text]` | PUT with a text payload (no Content-Format) |
| `ot coap observe <addr> <path>` | GET with Observe: 0; notifications print as they arrive |
| `ot coap cancel` | deregister the current observation (GET with Observe: 1) |
| `ot coap parameters request [default \| <ack_timeout_ms> <num> <den> <max_retransmit>]` | show or set CON timers for requests |

Output: `coap response from <addr> [OBS=<n>] with payload: <hex>`. The shell doesn't
print the response code; S's log does. A request that runs out of retries ends with
`coap receive response error 28: ResponseTimeout`.

## 4. Experiments

### A. Resource discovery

CoAP servers list their resources at `/.well-known/core` (RFC 6690, "link format"):

```bash
uart:~$ ot coap get <S-mleid> .well-known/core
coap response from ... with payload: 3c2f656e762f74656d703e2c3c2f6163742f76616c76653e
```

Decode the hex as ASCII. This is how a gateway or dashboard finds out what a node offers
without reading its firmware.

### B. Tune CON for a sleeping valve

Lab 3 Task 5.3 showed the PUT arriving twice when the poll period (5 s) is longer than
CoAP's first ACK wait (2–3 s). Fix it on the client:

```bash
uart:~$ ot coap parameters request 8000 3 2 4
uart:~$ ot coap put <S-mleid> act/valve con 1
uart:~$ ot coap parameters request default
```

**DDR question:** what's the new worst-case time before `ResponseTimeout`? What's the
cost of a longer `ACK_TIMEOUT` when the valve really is gone?

### C. Two observers (third board)

Flash a third board, join it to the mesh, `ot coap start` on it, and observe `/env/temp`
from both clients. S sends each notification once per observer. Then unplug one client
without cancelling and watch S's log over the next heartbeats: the CON notification to
the missing client is retried and fails, and S stops sending to it.

### D. Add a resource

Add `/env/hum` (relative humidity, simulated, CBOR `{"h": uint}` in %) next to
`/env/temp`:

1. Copy the `COAP_RESOURCE_DEFINE` block and a GET handler from `env_temp.c` into a new
   `src/env_hum.c`; add the file to `CMakeLists.txt`.
2. Encode with `zcbor_uint32_put()` instead of `zcbor_float16_put()`.
3. Write the contract (table + CDDL) before the code, and check it with
   `ot coap get <S-mleid> env/hum` and `.well-known/core`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ot coap get` prints nothing, S logs nothing | `ot coap start` was run on S too, so S's server is deaf. `ot coap stop` on S. |
| `coap receive response error 28: ResponseTimeout` on a GET | Wrong address, or S is not attached. Check `ot state` on S and use its `ot ipaddr mleid`. |
| A GET or PUT gets no reply but S is attached | Path typo or a leading `/`: S answers `4.04 Not Found`, but only to a `con` request; a NON request with an error gets no reply at all. Use `env/temp`. |
| Observe stops after a while | S dropped you after a failed CON heartbeat (C was busy or out of range). Run `ot coap observe` again. |
| PUT logs `4.00` on S | The payload wasn't `0` or `1`. |
| `ot mode -` and S never becomes `child` | C is not a router or leader, or S was the leader. Form the network on C (Lab 3 Task 1.2). |
| Pings to the sleepy S time out | The ping timeout (last argument) must exceed the poll period. |
