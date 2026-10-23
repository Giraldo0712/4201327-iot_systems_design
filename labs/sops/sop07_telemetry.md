# SOP-07: Telemetry, the Dashboard & the CoAP→MQTT Bridge

> **Main Lab Guide:** [Lab 7: Operations & Observability](../lab7.md)
> **ISO placement:** OMD (Operation & Management Domain) under the Usage viewpoint; RAID **interchange subsystem** lights up.
> **GreenField Context:** Stop flying blind — turn raw readings into fleet telemetry, then make the data leave the mesh.

## Objectives

Implement the **Operation & Management Domain (OMD)** by reporting device health (`batt`, `rssi`, `up`). Visualize it locally on the dashboard you already have (the **local-CLI** path), then stand up the **interchange subsystem** — a CoAP→MQTT bridge that publishes the fused fleet telemetry off-mesh to a broker (local Mosquitto by default, AWS IoT Core as an optional internet tier).

---

## Part A — The telemetry signals (firmware)

Three signals, all cheap to read on the ESP32-C6. Add them to your **Lab 6 Node A** firmware.

```c
#include "esp_timer.h"
// for ADC battery read:
#include "esp_adc/adc_oneshot.h"

// RSSI of the last received frame (dBm) — OpenThread radio API
int8_t rssi = otPlatRadioGetRssi(esp_openthread_get_instance());

// Uptime in seconds since boot
int64_t uptime_s = esp_timer_get_time() / 1000000;
```

**Battery voltage.** Two options — pick one and document it in ADR-007:

```c
// Option 1 — real ADC read (ESP32-C6: ADC1 channels are GPIO0..GPIO6).
// Wire the battery through a divider so it stays under the ADC full-scale.
adc_oneshot_unit_handle_t adc;
adc_oneshot_unit_init_cfg_t unit_cfg = { .unit_id = ADC_UNIT_1 };
adc_oneshot_new_unit(&unit_cfg, &adc);
adc_oneshot_chan_cfg_t chan_cfg = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
adc_oneshot_config_channel(adc, ADC_CHANNEL_0, &chan_cfg);   // GPIO0
int raw_mv;
adc_oneshot_read(adc, ADC_CHANNEL_0, &raw_mv);
int batt_mv = raw_mv * DIVIDER_RATIO;   // undo your resistor divider

// Option 2 — documented mock (fine for the lab if you have no divider wired):
int batt_mv = 3100;   // mock; state in ADR-007 that this is not a real measurement
```

Now expose the three signals. **ADR-007 chooses between two deliveries:**

### A.1 — Piggyback onto `/env/temp` (one packet, energy-efficient)

Modify `hnd_temp_get` in `coap_demo.c`. The map goes from one key to four:

```c
CborEncoder map;
cbor_encoder_create_map(&encoder, &map, CborIndefiniteLength);

cbor_encode_text_stringz(&map, "t");
cbor_encode_float(&map, current_temp);

// --- OMD telemetry (piggybacked) ---
cbor_encode_text_stringz(&map, "rssi");
cbor_encode_int(&map, rssi);

cbor_encode_text_stringz(&map, "batt");
cbor_encode_int(&map, batt_mv);

cbor_encode_text_stringz(&map, "up");
cbor_encode_int(&map, uptime_s);

cbor_encoder_close_container(&encoder, &map);
```

The reading is now `{"t": ..., "rssi": ..., "batt": ..., "up": ...}` — one packet carries business data and telemetry. Cheapest on the air; the cost is that `/env/temp` is no longer a clean single-purpose resource.

### A.2 — A separate `/sys/health` resource (clean, independently observable)

```c
static void hnd_health_get(coap_resource_t *r, coap_session_t *s,
                           const coap_pdu_t *req, const coap_string_t *q,
                           coap_pdu_t *resp) {
    uint8_t buf[32];
    CborEncoder enc, map;
    cbor_encoder_init(&enc, buf, sizeof(buf), 0);
    cbor_encoder_create_map(&enc, &map, 3);
    cbor_encode_text_stringz(&map, "rssi"); cbor_encode_int(&map, rssi);
    cbor_encode_text_stringz(&map, "batt"); cbor_encode_int(&map, batt_mv);
    cbor_encode_text_stringz(&map, "up");   cbor_encode_int(&map, uptime_s);
    cbor_encoder_close_container(&enc, &map);
    size_t len = cbor_encoder_get_buffer_size(&enc, buf);
    coap_pdu_set_code(resp, COAP_RESPONSE_CODE_CONTENT);
    coap_add_data(resp, len, buf);
}
// register alongside /env/temp:
// coap_resource_t *h = coap_resource_init(coap_make_str_const("sys/health"), 0);
// coap_register_handler(h, COAP_REQUEST_GET, hnd_health_get);
// coap_resource_set_get_observable(h, 1);   // make it observable too
// coap_add_resource(ctx, h);
```

Cleaner architecture, but it's a second packet per report — more air time, more energy. That's the ADR-007 trade.

**Report interval.** Telemetry drifts over hours, not seconds. Do **not** stream it at the business-data rate. Either piggyback (it rides existing `/env/temp` notifications) or, for `/sys/health`, observe it on a slow timer (e.g. every few minutes). Defend your number against the Lab 3/4 battery budget.

---

## Part B — The local dashboard (extend `dashboard_coap.py`)

This is the **local-CLI** path — Node B runs `coap observe`, you tail its monitor log. Reuse [`tools/dashboard_coap.py`](../../tools/dashboard_coap.py).

**Setup (same as the stub):**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install aiocoap cbor2 matplotlib flask paho-mqtt
```

**Generalize the decoder.** The current `decode_env_temp_cbor` is a strict 6-byte single-key parser. With telemetry added, decode the whole map with `cbor2`:

```python
import cbor2

def decode_telemetry_cbor(payload: bytes):
    """Decode the extended map {"t","rssi","batt","up"} or a /sys/health subset."""
    try:
        obj = cbor2.loads(payload)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return {
        "temperature": round(obj["t"], 2) if "t" in obj else None,
        "rssi": obj.get("rssi"),
        "batt": obj.get("batt"),
        "uptime": obj.get("up"),
    }
```

**Status light + fleet table.** Key the in-memory state by node (the source IPv6 captured from the CLI line), and compute a Green/Red light per node:

```python
import time

fleet = {}   # node_addr -> {temperature, rssi, batt, uptime, last_seen}

def status_light(node):
    age = time.time() - node["last_seen"]
    ok = (node.get("batt", 0) > 3000
          and node.get("rssi", -127) > -90
          and age < 60)
    return "GREEN" if ok else "RED"
```

Add three Chart.js datasets (temperature, RSSI, battery) and render `fleet` as an HTML table with the status light per row. The HTML skeleton, the `/api/sensor` poller, and the Chart.js block are already in [`dashboard_coap.py`](../../tools/dashboard_coap.py) — extend, don't rewrite.

**Walk test (verification):**
1. Run the dashboard against Node B's monitor log.
2. Pick up a node, walk away from the OTBR.
3. Watch `rssi` fall and the light flip Green→Red.
4. Record the RSSI at which the Observe stream stops updating.

---

## Part C — The interchange: the CoAP→MQTT bridge

This is the **graded headline** — the data leaves the mesh. The bridge subscribes to each node's CoAP Observe (reachable globally thanks to your Lab 5 OTBR), decodes the CBOR, and **publishes JSON to an MQTT broker**. Inside the mesh: CoAP/CBOR/IPv6. Outside: MQTT/JSON/IPv4. The bridge is the translator — Table A.3 *information fusion*, RAID interchange.

### C.1 — The bridge script

Save as `tools/coap_mqtt_bridge.py`:

```python
"""CoAP->MQTT bridge — RAID interchange subsystem.
Observes /env/temp on each node, decodes CBOR, republishes JSON to MQTT.
"""
import asyncio, json, cbor2
import aiocoap
import paho.mqtt.client as mqtt

NODES = {                       # node label -> CoAP URI (global IPv6 via the Lab 5 OTBR)
    "node-a": "coap://[fd11:22::1]/env/temp",
    "node-b": "coap://[fd11:22::2]/env/temp",
}
MQTT_HOST, MQTT_PORT = "localhost", 1883

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)   # paho 2.x: version arg is required
mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
mqttc.loop_start()

async def observe(label, uri):
    ctx = await aiocoap.Context.create_client_context()
    req = aiocoap.Message(code=aiocoap.GET, uri=uri, observe=0)
    pr = ctx.request(req)
    async for resp in pr.observation:
        try:
            data = cbor2.loads(resp.payload)
        except Exception:
            continue
        topic = f"soilsense/{label}/telemetry"
        mqttc.publish(topic, json.dumps(data))
        print(f"[bridge] {topic} <- {data}")

async def main():
    await asyncio.gather(*(observe(l, u) for l, u in NODES.items()))

asyncio.run(main())
```

> **CLI-tail fallback.** If your OTBR isn't routing global IPv6 to the nodes yet, you can keep the Lab 3 approach: tail Node B's `coap observe` monitor log (like [`dashboard_coap.py`](../../tools/dashboard_coap.py)'s `tail_log`) and publish each decoded line instead of using aiocoap directly. Same MQTT output — only the *source* of the readings differs.

### C.2 — Stand up a local broker (Mosquitto — the no-pain default)

```bash
# Linux:
sudo apt install -y mosquitto mosquitto-clients
# macOS:
brew install mosquitto && brew services start mosquitto
# Docker (any OS):
docker run -it -p 1883:1883 eclipse-mosquitto
```
If Mosquitto refuses anonymous connections, allow them for the lab — create `mosquitto.conf` with:
```
listener 1883
allow_anonymous true
```
and run `mosquitto -c mosquitto.conf`.

### C.3 — Run it and prove the data left the mesh

```bash
# Terminal 1 — raw proof the fused stream exists:
mosquitto_sub -t 'soilsense/#' -v

# Terminal 2 — the bridge:
python tools/coap_mqtt_bridge.py

# Terminal 3 — the operator view (reuse the Lab 0.5 dashboard):
python tools/dashboard_mqtt.py
```

> **Topic change for `dashboard_mqtt.py`.** It defaults to `iot/sensor`. Point it at the bridge's topic: set `TOPIC_SENSOR = "soilsense/+/telemetry"` (the `+` wildcard matches every node). The payload is JSON, which it already decodes.

You should now see every node's telemetry, fused, on one broker — and you got there *without* anyone running `coap observe` by hand. The data has left the proximity network.

---

## Part D (optional stretch) — AWS IoT Core (the real internet)

The whole point: **the same bridge, a different broker.** Your bytes now cross NAT64 to the public internet — the path you proved in [Lab 5](../lab5.md).

1. In the AWS IoT console: **Create a Thing** → **Auto-generate certificate** → download `device.cert.pem`, `device.private.key`, and the **Amazon Root CA**.
2. Attach a policy allowing `iot:Connect` / `iot:Publish` on your topic.
3. Find your **ATS endpoint** (`xxxx-ats.iot.<region>.amazonaws.com`).
4. Change three things in the bridge — the host, the port, and TLS:

```python
MQTT_HOST, MQTT_PORT = "xxxx-ats.iot.us-east-1.amazonaws.com", 8883
mqttc.tls_set(ca_certs="AmazonRootCA1.pem",
              certfile="device.cert.pem",
              keyfile="device.private.key")
mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
```

Watch the messages arrive in the **AWS IoT → MQTT test client**, subscribed to `soilsense/#`. That's it — the bridge didn't change, only its destination did. (This is also why a heavyweight cloud platform isn't *required*: it can't ingest CoAP/CBOR/IPv6 natively, so you'd build this same bridge regardless. The bridge is the architecture.)

---

## Verification

1. **Telemetry:** a CoAP read of `/env/temp` (piggyback) or `/sys/health` returns `batt`/`rssi`/`up`.
2. **Local dashboard:** the fleet table shows each node with a Green/Red light; the walk test flips a node to Red.
3. **Interchange:** `mosquitto_sub -t 'soilsense/#'` shows ≥2 nodes' telemetry as JSON; `dashboard_mqtt.py` renders it.
4. **(Stretch)** AWS IoT MQTT test client shows the same messages over TLS:8883.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Bridge: `aiocoap` request times out | Node not globally reachable — confirm the Lab 5 OTBR published a global prefix and the node's address is right. Try a CoAP `get` from your laptop first. Use the CLI-tail fallback (C.1) if routing isn't ready. |
| `paho` `TypeError: __init__() missing argument` | paho-mqtt 2.x requires `mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)` — see the bridge and [`dashboard_mqtt.py`](../../tools/dashboard_mqtt.py). |
| `mosquitto_sub` connects but no messages | Bridge not publishing — check its console for `[bridge]` lines; check the topic matches (`soilsense/#`). |
| Mosquitto: `Connection refused` | Broker not running, or rejecting anonymous clients — add `allow_anonymous true` (C.2) for the lab. |
| Dashboard shows nothing on `soilsense/+/telemetry` | `TOPIC_SENSOR` still `iot/sensor` — change it (C.3). |
| CBOR decode returns `None` | Payload isn't the expected map — print `resp.payload.hex()` and confirm the firmware encoder ran (Part A). |
| AWS: TLS handshake fails / `Connection refused` 8883 | Wrong CA/cert/key path, clock skew, or the IoT policy denies `iot:Connect`/`iot:Publish` on your topic. Check the policy resource ARN matches `soilsense/*`. |
| AWS connects but no messages in test client | Subscribe to `soilsense/#` (the bridge publishes per-node sub-topics), and confirm the endpoint is the **ATS** endpoint, not the legacy one. |
