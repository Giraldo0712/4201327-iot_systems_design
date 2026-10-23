# SOP-06: CoAP over DTLS

- **Serves:** [Lab 6](../lab6.md)
- **Hardware:** the Lab 5 setup: the OTBR (ESP32-S3 and its RCP), **S** with its sensor,
  **C**, and the laptop on the same hotspot
- **Firmware:** [`firmware/lab6_secure`](../../firmware/lab6_secure); Zephyr as pinned in
  [setup](../../docs/setup.md)
- **Host tools:** [`tools/coap_client.py`](../../tools/coap_client.py) and
  [`tools/dashboard_coap.py`](../../tools/dashboard_coap.py), with their DTLS client in
  [`tools/coaps.py`](../../tools/coaps.py) (needs `cryptography`, already in the Zephyr
  virtual environment)

Steps, checks and fixes only; the questions are in the lab. The contracts are unchanged:
[SoilSense API](../../docs/api.md).

## 1. Build, flash and rejoin

1. The key: the build's default is `soilsense-lab-6`, identity `soilsense-pilot`. Every
   pair in the room shares that default, so pick your own and use it on both boards and
   on the laptop:

   ```bash
   source ~/zephyrproject/env.sh
   cd firmware/lab6_secure
   # S, with its sensor overlay (example: DHT22)
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- \
       -DEXTRA_DTC_OVERLAY_FILE=sensors/dht22.overlay -DCONFIG_LAB_PSK='"<your-key>"'
   west flash
   # C, without a sensor
   west build -p always -b esp32c6_devkitc/esp32c6/hpcore . -- -DCONFIG_LAB_PSK='"<your-key>"'
   west flash
   ```

   The inner quotes are Kconfig's: the value needs its own quotes inside the shell's. Keys
   up to 32 characters.

2. The Thread dataset survives reflashing. On both boards:

   ```
   uart:~$ ot ifconfig up
   uart:~$ ot thread start
   ```

**Verify:** the boot log reads

```
<inf> lab6_secure: SoilSense node ready: CoAPS /env/temp (dht22) and /act/valve on UDP 5684, PSK identity "soilsense-pilot". OpenThread commands start with "ot".
```

and `ot state` reaches `router` (or `child`). Note S's OMR address (`ot ipaddr`, the one
with the OTBR's prefix) and its ML-EID (`ot ipaddr mleid`).

## 2. Plain CoAP is refused

From the laptop (needs `aiocoap`, as in Lab 5):

```bash
python tools/coap_client.py --host <S-omr> get /env/temp
[1] Error: Network error: NetworkError
```

From C:

```
uart:~$ ot coap start
uart:~$ ot coap get <S-mleid> env/temp
Done
```

**Verify:** no `coap response` line, on either side.

## 3. CoAPS from C

The `coaps` shell command opens one DTLS session per command, prints the handshake time,
sends its requests and closes the session:

```
uart:~$ coaps get <S-mleid> env/temp 3
DTLS handshake: 100 ms
2.05, payload a16174f94e41, RTT 23 ms
2.05, payload a16174f94e41, RTT 22 ms
2.05, payload a16174f94e41, RTT 22 ms
uart:~$ coaps put <S-mleid> act/valve 1
DTLS handshake: 100 ms
2.04, payload a1617601, RTT 23 ms
```

| Command | Does |
|---|---|
| `coaps get <addr> <path> [count]` | one session, `count` GETs over it |
| `coaps put <addr> <path> <0\|1>` | PUT `{"v": 0\|1}` as CBOR |
| `coaps key <key>` · `coaps key default` | the key C presents · back to the build's |

A wrong key:

```
uart:~$ coaps key not-the-key
uart:~$ coaps get <S-mleid> env/temp
DTLS handshake failed after 10002 ms (-116)
uart:~$ coaps key default
```

**Verify:** the right key gets `2.05` and `2.04`; the wrong one gets no session.

## 4. CoAPS from the laptop

```bash
source ~/zephyrproject/env.sh          # its virtual environment has cryptography
python tools/coap_client.py --host <S-omr> --psk <your-key> --count 10 get /env/temp
DTLS handshake: 345 ms
[1] Code: 2.05  RTT: 102 ms
Payload (CBOR): {'t': 24.640625} [a16174f94e29]
...
10/10 responses, median RTT 102 ms (min 100, max 103)
```

`-v` prints every handshake flight with its time:

```bash
python tools/coap_client.py --host <S-omr> --psk <your-key> -v put /act/valve 1
      0.0 ms  -> ClientHello
     80.4 ms  <- HelloVerifyRequest: a 32-byte cookie, proof we own our address
     80.4 ms  -> ClientHello + cookie
    180.5 ms  <- ServerHello, ServerHelloDone
    180.7 ms  -> ClientKeyExchange (identity "soilsense-pilot"), ChangeCipherSpec, Finished
    285.6 ms  <- ChangeCipherSpec, Finished: session up
DTLS handshake: 286 ms
[1] Code: 2.04  RTT: 100 ms
```

A wrong key:

```bash
python tools/coap_client.py --host <S-omr> --psk not-the-key get /env/temp
DTLS: handshake timed out after 10 s (wrong key, or server unreachable)
```

**Verify:** `2.05` with your key; the timeout with any other.

## 5. Capture the wire

On the laptop, capture the Wi-Fi interface (`ip link` names it: `wlan0`, `wlp3s0`…)
while you repeat one GET from §4:

```bash
sudo tcpdump -i wlan0 -w lab6.pcap udp port 5684
```

Stop it with Ctrl-C and open `lab6.pcap` in Wireshark (or capture there directly with the
display filter `udp.port == 5684`). Wireshark decodes DTLS: the handshake messages by
name, then `Application Data`.

**Verify:** the flights of §4 appear as separate packets, followed by application-data
records whose payload is opaque.

## 6. The dashboard over DTLS

```bash
pip install flask                      # once, with env.sh sourced
python tools/dashboard_coap.py --host <S-omr> --psk <your-key>
[CoAPS] Session up, handshake 323 ms
[CoAP] /act/valve = 0  (CBOR: a1617600)
[CoAP] /env/temp = 24.50 C  (CBOR: a16174f94e20)
```

The dashboard keeps one session for Observe and opens a second one for each valve
command.

**Verify:** `http://localhost:5000` draws the temperature; from the phone,
`http://<laptop-ipv4>:5000` and *Open* return `[CoAPS] PUT /act/valve 1: 2.04`.

## 7. Count the sessions

```bash
python tools/coap_client.py --host <S-omr> --psk <your-key> --timeout 8 --sessions 5 get /env/temp
session 1: up, handshake 313 ms
...
session 5: handshake timed out after 8 s (wrong key, or server unreachable)
```

A session the client closes frees its slot at once; one a client abandons lasts until
two minutes of silence.

**Verify:** a few sessions come up and the rest time out.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `malformed string literal in assignment to LAB_PSK` and the build stops | The key lost its inner quotes | `-DCONFIG_LAB_PSK='"<your-key>"'` |
| Every handshake times out, with the right key | S isn't attached yet, or another pair's key on one side | `ot state` on S; check the key on both builds |
| `coaps get` first handshake takes about a second, the next ones 100 ms | The first packet to a new address waits for a Thread address query | Normal |
| `No module named 'cryptography'` | The Zephyr environment isn't loaded | `source ~/zephyrproject/env.sh` |
| `No module named 'aiocoap'` (§2 only) | Plain CoAP from the laptop uses aiocoap | `pip install aiocoap` |
| A new client times out while others work | S already holds as many sessions as it can | Close a client; abandoned sessions expire after 2 min of silence |
| The dashboard says `no session` | The laptop lost its route to S, or the OTBR is down | Lab 5 checks: `ip -6 route`, `ot br state` |
| `ot coap get` to S prints nothing | Expected: S serves only CoAPS | Use `coaps get` |
