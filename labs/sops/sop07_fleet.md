# SOP-07: Telemetry, the Bridge and the Fleet Dashboard

- **Serves:** [Lab 7](../lab7.md)
- **Hardware:** every node of the team, one OTBR, a laptop on its hotspot
- **Firmware:** [`firmware/lab7_telemetry`](../../firmware/lab7_telemetry); Zephyr as pinned
  in [setup](../../docs/setup.md)
- **Host:** Docker with Compose ([setup §7](../../docs/setup.md#7-docker-for-labs-7-and-8)),
  the stack in [`tools/fleet/`](../../tools/fleet), the bridge
  [`tools/coap_mqtt_bridge.py`](../../tools/coap_mqtt_bridge.py)

Steps, checks and fixes only; the questions are in the lab. DTLS mechanics are in
[SOP-06](sop06_security.md).

## 1. Build and flash

Every node, with the team's key (and its sensor overlay where it has one):

```bash
source ~/zephyrproject/env.sh
cd firmware/lab7_telemetry
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- -DCONFIG_LAB_PSK='"<team-key>"'
west flash
```

The Thread dataset survives reflashing: `ot ifconfig up`, `ot thread start`. A node new to
the team's network takes the dataset as in [SOP-05 §3](sop05_border_router.md#3-move-s-and-c-onto-the-otbrs-network).

**Verify** on each node:

```
uart:~$ health
batt:   3298 mV (simulated)
rssi:   -56 dBm
up:     121 s
hsfail: 0 failed DTLS handshakes
period: 60 s
```

and from the laptop:

```bash
python tools/coap_client.py --host <node-omr> --psk <team-key> get /sys/health
Payload (CBOR): {'batt': 3295, 'rssi': -51, 'up': 347, 'hsfail': 0} [...]
```

The report period, on each node's shell: `health period <s>`. The node's log prints the
size of every notification: `notify /sys/health (CON): CoAP <n> B, next in <s> s`.

## 2. Start the fleet stack

```bash
cd tools/fleet
docker compose up -d
docker compose ps
```

**Verify:** `mosquitto`, `influxdb`, `telegraf` and `grafana` are `running`.

The stack brings its own MQTT broker on port 1883. The Lab 0 broker uses the same port:
stop it first (`sudo systemctl stop mosquitto`), or start the stack with
`MQTT_PORT=1884 docker compose up -d` and give the bridge `--port 1884`.

## 3. Run the bridge

```bash
pip install paho-mqtt cbor2              # once, with env.sh sourced
python tools/coap_mqtt_bridge.py --psk <team-key> \
    --node north=<omr-1> --node south=<omr-2> --node east=<omr-3>
[bridge] publishing to localhost:1883 under soilsense/#
[north] session up, handshake 358 ms
[north] soilsense/north/env <- {'t': 23.46875}
[north] soilsense/north/health <- {'batt': 3295, 'rssi': -51, 'up': 347, 'hsfail': 0}
```

Names are free; the dashboard shows them. In another terminal:

```bash
mosquitto_sub -h localhost -t 'soilsense/#' -v
soilsense/north/env {"t": 25.390625}
soilsense/south/env {"t": 24.375}
```

**Verify:** a `session up` line per node, and every node's topics on `mosquitto_sub`.

## 4. Open the dashboard

`http://localhost:3000` opens the **SoilSense fleet** dashboard read-only; from a phone on
the hotspot, `http://<laptop-ipv4>:3000`. To edit, sign in as `admin` / `soilsense`.

**Verify:** the three status panels show every node in green, and the fleet table has a
row per node.

The dashboard is generated: edit
[`tools/fleet/grafana/make_dashboard.py`](../../tools/fleet/grafana/make_dashboard.py),
run it, then `docker compose restart grafana`.

## 5. The drills

Note the time of each action; the dashboard refreshes every 10 s.

| Drill | Action | Shows on the dashboard as |
|---|---|---|
| Silent node | pull a node's USB cable | its *last report* passes 150 s and turns red |
| Low battery | `health batt 2900` on a node | its battery drops below the 3000 mV line at its next report |
| Wrong key | `python tools/coap_client.py --host <node-omr> --psk wrong get /env/temp` | its *failed handshakes* turns red at its next report |
| Reboot | press a node's reset button | its uptime drops; the bridge logs a new session |

A node counts a failed handshake when it gives up waiting for the client, so the count
lags the probe. `health batt 3300` restores the battery.

## 6. A cloud broker

Any MQTT broker that takes TLS client certificates works. For AWS IoT Core: create a
*Thing*, download its certificate, private key and the Amazon root CA, and attach a policy
allowing `iot:Connect` and `iot:Publish` on `soilsense/*`. Then:

```bash
python tools/coap_mqtt_bridge.py --psk <team-key> --node north=<omr-1> \
    --broker <account>-ats.iot.<region>.amazonaws.com --port 8883 \
    --cafile AmazonRootCA1.pem --cert <thing>.pem.crt --key <thing>-private.pem.key
```

**Verify:** the console's MQTT test client, subscribed to `soilsense/#`, shows the nodes.

## 7. Stop

```bash
docker compose down          # keeps the history; add -v to erase it
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Bind for 0.0.0.0:1883 failed: port is already allocated` | The Lab 0 broker holds 1883 | §2: stop it, or `MQTT_PORT=1884` |
| `permission denied ... docker.sock` | Your user isn't in the `docker` group | Setup §7, then a new terminal |
| The bridge prints `handshake timed out` for one node | Wrong key on that node, or the node is off the network | `health` and `ot state` on the node |
| `No module named 'paho'` | The bridge's dependencies are missing | `pip install paho-mqtt cbor2` |
| `mosquitto_sub` shows the topics, the dashboard is empty | Telegraf isn't connected yet, or the time range is too short | `docker compose logs telegraf`; widen the range |
| Dashboard panels say `No data` after a restart | InfluxDB is still starting | Wait a minute and reload |
| Every node turns red at once | The bridge stopped, or the laptop left the hotspot | Restart the bridge; check the laptop's route (Lab 5) |
