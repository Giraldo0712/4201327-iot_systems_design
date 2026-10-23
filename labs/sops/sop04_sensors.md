# SOP-04: Sensor Wiring, Firmware and Experiments

- **Serves:** [Lab 4](../lab4.md)
- **Hardware:** 2 ESP32-C6 boards (**S** with the sensor, **C** the client), one of the
  sensors below, a breadboard and jumper wires
- **Firmware:** [`firmware/lab4_sensors`](../../firmware/lab4_sensors), the Lab 3 firmware
  with a real sensor behind `/env/temp`; Zephyr as pinned in [setup](../../docs/setup.md)
- **Contract:** [SoilSense API](../../docs/api.md#from-lab-4-what-the-value-promises)

Steps, checks and fixes only; the questions are in the lab. The CoAP commands are in
[SOP-03](sop03_coap.md).

## 1. Wire the sensor

Power every sensor from **3V3, never 5 V**: the data line is pulled up to the sensor's
supply, and 5 V on a C6 pin damages it. The board has a single 3V3 pin; with more than
one device, take 3V3 and GND to the breadboard rails first.

| Sensor | Connections | Overlay | Notes |
|---|---|---|---|
| DS18B20 waterproof probe | red → 3V3, black → GND, yellow → **GPIO18** | `sensors/ds18b20.overlay` | 1-Wire. The internal pull-up works for one probe on its 1 m cable; for longer cables or several probes add 4.7 kΩ from GPIO18 to 3V3 |
| DHT22 / AM2302 (white) | VCC → 3V3, GND → GND, DAT → **GPIO19** | `sensors/dht22.overlay` | The module has its pull-up |
| DHT11 (blue) | VCC → 3V3, GND → GND, DATA → **GPIO19** | `sensors/dht11.overlay` | Same wiring as the DHT22, different overlay |
| BMP280 | VCC → 3V3, GND → GND, SDA → **GPIO6**, SCL → **GPIO7**, CSB → 3V3, SDO → GND | `sensors/bmp280.overlay` | I²C at 0x76 (SDO → 3V3 gives 0x77: change `reg` and the node name). No humidity |

To move a sensor to another pin, change the GPIO number in its overlay. Avoid GPIO8 and
GPIO9 (boot straps and the LED), GPIO12/13 (USB) and GPIO16/17 (the console UART).

## 2. Build S and C

```bash
source ~/zephyrproject/env.sh
cd firmware/lab4_sensors

# S, with its sensor (example: DHT22)
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay
west flash

# C, without a sensor: it serves Lab 3's simulated temperature
west build -p always -b esp32c6_devkitc/esp32c6/hpcore .
west flash
```

A Super Mini adds the USB console, with the two overlays separated by `;`:

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_CONF_FILE=usb_console.conf \
    -DEXTRA_DTC_OVERLAY_FILE="usb_console.overlay;sensors/dht22.overlay"
```

Form the network and start the client as in [SOP-03 §1](sop03_coap.md#1-build-flash-and-form-the-network).

**Verify** on S (S reads the sensor every 2 s):

```
uart:~$ soilsense stats
sensor:    dht22
last good: 24.10 C, 1 s ago
humidity:  70.6 %RH
reads:     7 in 13 s: 0 failed (0.0 %), 0 rejected
read time: min 21543 us, avg 21587 us, max 21597 us
```

## 3. Read, log and inject

| Command | Does |
|---|---|
| `soilsense stats` | last good reading and its age, humidity (DHT), reads / failed / rejected since the last reset, read time min / avg / max |
| `soilsense reset` | zero the counters |
| `soilsense log on` / `off` | print every reading as it is taken |
| `soilsense inject <°C>` | pass one made-up reading through the plausibility checks, as if the sensor had sent it |

```
uart:~$ soilsense log on
<inf> reading: dht22: 24.10 C, 70.6 %RH
...
uart:~$ soilsense log off
uart:~$ soilsense inject 90
<wrn> reading: Rejected 90.00 C from inject: outside -40..85 C
```

**Verify:** a rejected value never becomes `last good` in `soilsense stats`.

## 4. Break the sensor and the node

1. With C observing (`ot coap observe <S-mleid> env/temp`), pull the sensor's data wire.

   **Verify:** S logs three failed reads, then `Sensor lost`; about 60 s after the last good
   reading, `GET now answers 5.03`.

2. Every 15 s on C: `ot coap get <S-mleid> env/temp`. A 5.03 arrives as the text
   `no fresh reading` in hex:

   ```
   coap response from fdd7:... with payload: 6e6f2066726573682072656164696e67
   ```

3. Plug the wire back in. **Verify:** S logs `Sensor back`. Register again with
   `ot coap observe`.
4. Node off: `ot thread stop` on S, then on C `ot coap get <S-mleid> env/temp con` and
   start the stopwatch. **Verify:** `coap receive response error 28: ResponseTimeout`.
   Then `ot thread start` on S.
5. Busy radio, from C, for 2 minutes:

   ```
   uart:~$ ot ping <S-mleid> 64 1200 0.1
   ```

## 5. Extensions

| File | What it does |
|---|---|
| `src/reading.c` | the sensing side: reads every 2 s, the plausibility checks, the last good reading, the counters, the `soilsense` command |
| `src/env_temp.c` | `/env/temp`: GET and Observe as in Lab 3, plus Max-Age from the reading's age and the 5.03 |
| `src/valve.c`, `src/main.c` | `/act/valve` and the LED, as in Lab 3 |
| `sensors/*.overlay` | one devicetree overlay per sensor: driver and pins |
| `Kconfig` | the BMP280 in forced mode: it measures when asked and sleeps in between |

The application asks for "the temperature sensor" through the devicetree alias
`temp-sensor`; built without an overlay there is no alias and `reading.c` falls back to
Lab 3's simulated sine.

The DHT driver times each bit in software. To lock out interrupts for the whole read:

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay -DCONFIG_DHT_LOCK_IRQS=y
```

Humidity as `/env/hum` (CBOR `{"h": float16}`, %RH): follow the `/env/hum` steps in
[SOP-03 §8](sop03_coap.md#8-extensions), keeping `zcbor_float16_put()`. A DS18B20 on GPIO18 and a DHT22 on GPIO19 can
share one S.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Read failed (-5)` on every read (DHT) | Data on the wrong pin, no power, or a DHT11 built with the DHT22 overlay (or the reverse) | Check the wiring against §1 and the overlay |
| `DS18B20: No 1-Wire slaves connected` | Data wire loose or on the wrong pin | Reseat it; with a long cable add the 4.7 kΩ pull-up |
| `bmp280@76 was not found at boot` | The driver looks for the chip only at startup | Check SDA, SCL, CSB and SDO, then reset S |
| A reading of exactly 85.0 °C is rejected (DS18B20) | The probe reset and returned its power-on value | Check the 3V3 and GND wires |
| Humidity stuck at 95 % (DHT11) or 100 % (DHT22) | Condensation from breath or a damp spot | Wait minutes for the element to dry |
| `ot coap get` prints `6e6f2066726573682072656164696e67` | "no fresh reading": no accepted reading is younger than 60 s | Check the sensor wiring |
| C stopped receiving notifications | S ended the observation with a 5.03, or dropped C after a failed CON heartbeat | `ot coap observe` again |
