# SOP-04: Sensor Firmware Tour, Wiring and Experiments

> **Main Lab Guide:** [Lab 4: Real Sensors](../lab4.md) — the contract, tasks and
> deliverables live there.
> **ISO lens:** PED, SCD, ASD, audited through the Trustworthiness viewpoint (§6.6)
> **Firmware:** [`firmware/lab4_sensors`](../../../firmware/lab4_sensors), the Lab 3
> firmware with a real sensor behind `/env/temp`.

## 1. What's in the firmware

| File | What it does |
|---|---|
| `src/reading.c` | The sensor side: a thread reads the sensor every 2 s, applies the plausibility checks, keeps the last good reading and the counters, and adds the `soilsense` shell command. |
| `src/env_temp.c` | `/env/temp`: GET and Observe as in Lab 3, plus freshness: Max-Age counts down with the reading's age, and a 5.03 replaces the value once it is older than 60 s. |
| `src/valve.c`, `src/main.c` | `/act/valve` and the LED, unchanged from Lab 3. |
| `sensors/*.overlay` | One devicetree overlay per sensor: which driver, on which pins. |
| `Kconfig` | Puts the BMP280 in forced mode: it measures when asked and sleeps in between. |

The split follows the ISO map: `reading.c` is sensing (SCD), `env_temp.c` is the service
contract (ASD). The application asks for "the temperature sensor" through a devicetree
alias, so the same code reads any of the four sensors:

```c
static const struct device *const sensor = DEVICE_DT_GET(DT_ALIAS(temp_sensor));
...
sensor_sample_fetch(sensor);
sensor_channel_get(sensor, SENSOR_CHAN_AMBIENT_TEMP, &v);
```

Built without an overlay, there is no `temp-sensor` alias and `reading.c` falls back to
Lab 3's simulated sine. That's how C is built, and it's the fallback for a pair whose
sensor is broken.

## 2. Wiring and builds

| Sensor | Overlay | Bus | Pins | Notes |
|---|---|---|---|---|
| DS18B20 probe | `sensors/ds18b20.overlay` | 1-Wire | data GPIO18 | The internal pull-up works for one probe on its 1 m cable; for longer cables or several probes add 4.7 kΩ from GPIO18 to 3V3. |
| DHT22 / AM2302 | `sensors/dht22.overlay` | single-wire | data GPIO19 | The module has its pull-up. Reads ≥ 2 s apart. |
| DHT11 | `sensors/dht11.overlay` | single-wire | data GPIO19 | Same wiring as the DHT22; a DHT11 built as a DHT22 (or the reverse) reads garbage. |
| BMP280 | `sensors/bmp280.overlay` | I²C, address 0x76 | SDA GPIO6, SCL GPIO7 | CSB → 3V3 selects I²C; SDO → GND sets 0x76 (→ 3V3 gives 0x77: change `reg` and the node name). Temperature and pressure, no humidity. |

Power every sensor from 3V3. The board has a single 3V3 pin: with more than one device,
take 3V3 and GND to the breadboard rails.

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_DTC_OVERLAY_FILE=sensors/ds18b20.overlay
```

Super Mini (console on the USB port):

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_CONF_FILE=usb_console.conf \
    -DEXTRA_DTC_OVERLAY_FILE="usb_console.overlay;sensors/ds18b20.overlay"
```

To move a sensor to another pin, change the GPIO number in its overlay. Avoid GPIO8 and
GPIO9 (boot straps and the LED), GPIO12/13 (USB) and GPIO16/17 (the console UART).

## 3. Command reference

| Command | Does |
|---|---|
| `soilsense stats` | last good reading and its age, humidity (DHT), reads / failed / rejected since the last reset, read time min / avg / max |
| `soilsense reset` | zero the counters (before a quiet or busy measurement) |
| `soilsense log on` / `off` | print every reading as it is taken |
| `soilsense inject <C>` | pass one made-up reading through the plausibility checks, as if the sensor had sent it |

The checks, in `reading.c`:

| Check | Rejects | Why |
|---|---|---|
| Range | below −40 °C or at/above 85 °C | Outside every sensor's range; a DS18B20 reports exactly 85.0 °C at power-on before its first conversion. |
| Step | > 5 °C away from a reading taken less than 10 s earlier | No air or soil warms that fast. After 10 s without an accepted reading the step check is skipped, so a real change is accepted. |

Three failed reads in a row log `Sensor lost`; the thread keeps retrying every 2 s and
logs `Sensor back` on the first good read.

## 4. Experiments

### A. What each sensor costs to read

`soilsense stats` shows the read time. The DS18B20 takes ~760 ms, but the driver sleeps
while the probe converts, so the CPU can idle. The DHT sensors take ~22 ms with the CPU
busy the whole time: the driver times every bit itself. The BMP280 in forced mode takes
tens of milliseconds, sleeping while it measures. **DDR question:** with your sensor read every 2 s, which costs more
energy per hour, the read or one Observe notification? Use the ESP32-C6 active and
radio currents from the datasheet.

### B. The DHT and the radio

The DHT driver measures pulse lengths in software, and anything that interrupts it (the
radio, the OpenThread thread) can corrupt a bit. `CONFIG_DHT_LOCK_IRQS=y` turns off
interrupts for the whole ~22 ms read:

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
    -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay -DCONFIG_DHT_LOCK_IRQS=y
```

Repeat Lab 4 Task 5.1. Does the read failure rate drop? Watch the ping loss on C at the
same time: what does the radio lose while interrupts are off?

### C. Humidity as a second resource (DHT)

`soilsense stats` already prints humidity. Serve it as `/env/hum` with CBOR
`{"h": float16}` in %RH, following SOP-03 Experiment D: write the contract first
(including the sensor's range, and what the node answers when the value sits at the top
of it), then the code.

### D. Two sensors, one answer

With a DS18B20 and a DHT22 on the same S (GPIO18 and GPIO19), Task 3.4's "wrong but
believable" value has a second opinion. Sketch how `/env/temp` would use the second
sensor: average, cross-check, or fall back? What does each option do to integrity and
availability?

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Read failed (-5)` on every read (DHT) | Data on the wrong pin, no power, or a DHT11 built with the DHT22 overlay (or the reverse). Check the wiring against §2. |
| `DS18B20: No 1-Wire slaves connected` | Data wire loose or on the wrong pin; with a long cable, add the 4.7 kΩ pull-up. |
| `bmp280@76 was not found at boot` | The BMP280 driver checks for the chip only at startup. Check SDA/SCL/CSB/SDO, then reset S. |
| Temperature exactly 85.0 °C rejected (DS18B20) | The probe reset (power glitch) and returned its power-on value. Check the 3V3 and GND wires. |
| Humidity stuck at 95 % (DHT11) or 100 % (DHT22) | Condensation from breath or a damp environment; the element needs minutes to dry. |
| `ot coap get` prints `6e6f2066726573682072656164696e67` | That's "no fresh reading" in ASCII: S answered 5.03 because no reading is younger than 60 s. Check the sensor wiring. |
| C stopped receiving notifications | S ended the observation with a 5.03, or dropped C after a failed CON heartbeat. Run `ot coap observe` again. |
