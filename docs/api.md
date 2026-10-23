# SoilSense CoAP API

The contracts every SoilSense node serves from Lab 3 on, and what you cite in your ADRs
and DDR §4. The firmware ([`lab3_coap`](../firmware/lab3_coap),
[`lab4_sensors`](../firmware/lab4_sensors)) produces exactly this; if you change the
firmware, change the contract first. Both resources listen on UDP port 5683.

## `/env/temp` — air temperature

| | |
|---|---|
| **Methods** | `GET`, `GET` + Observe (RFC 7641) |
| **Content-Format** | `60` (`application/cbor`) |
| **Payload** | `{"t": float16}`, °C, always 6 bytes |
| **Max-Age** | 60 s (Lab 4: 60 s minus the reading's age) |
| **Observe policy** | NON notification when the value moved > 0.5 °C since the last one; CON heartbeat after 45 s without one |

```
A1            map, 1 pair
61 74         text, 1 byte: "t"
F9 hh ll      half-precision float (IEEE 754), big-endian
```

| `t` (°C) | Wire bytes |
|---|---|
| 0.0 | `A1 61 74 F9 00 00` |
| 24.5 | `A1 61 74 F9 4E 20` |
| 25.0 | `A1 61 74 F9 4E 40` |
| −10.0 | `A1 61 74 F9 C9 00` |

### From Lab 4: what the value promises

With a real sensor behind it, `/env/temp` keeps the URI, methods, payload and Observe
policy above, and adds promises about the value:

| | |
|---|---|
| **Accuracy** | the sensor's datasheet figure: DS18B20 ±0.5 °C, DHT22 ±0.5 °C, DHT11 ±2 °C, BMP280 ±1 °C |
| **Max-Age** | how many more seconds the value stays fresh: 60 s minus the reading's age |
| **Plausibility** | values outside −40 to 85 °C, or more than 5 °C from a reading taken less than 10 s earlier, are rejected and never served |
| **No fresh reading** | when no accepted reading is younger than 60 s: `5.03 Service Unavailable`, Max-Age 10 (retry after), text payload `no fresh reading` |
| **Observe** | while readings are fresh, as above; when they stop being fresh, each observer gets one 5.03 notification (CON) and its observation ends |

## `/act/valve` — irrigation valve

| | |
|---|---|
| **Methods** | `PUT` (set), `GET` (read) |
| **Request payload** | CBOR `{"v": 0 \| 1}` with Content-Format 60, or the text `0` / `1` with no Content-Format (the OpenThread shell can only send text) |
| **Response payload** | the valve state as CBOR `{"v": 0 \| 1}`, Content-Format 60 |
| **Codes** | `2.04 Changed` after PUT · `2.05 Content` after GET · `4.00 Bad Request` for any other payload |
| **Idempotent** | yes: the same PUT twice leaves the same state |

```
A1 61 76 00   {"v": 0}  closed
A1 61 76 01   {"v": 1}  open
```

## CDDL

RFC 8610, the schema language for CBOR:

```
env-reading = { t: float16 }        ; °C, accuracy per sensor, fresh for Max-Age s
valve-state = { v: 0 / 1 }          ; 0 = closed, 1 = open
```

## Discovery

`GET /.well-known/core` (RFC 6690) lists both resources in link format.
