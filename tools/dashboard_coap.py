"""
IoT Systems Design - Lab Dashboard (Thread / CoAP / CBOR Version)
Application and Service Domain (ASD) Server

Shows /env/temp (CoAP Observe, CBOR {"t": float16}) and drives /act/valve
(CBOR {"v": 0|1}), with the same layout as the HTTP and MQTT dashboards of
Labs 0 and 0.5. Three ways to reach the mesh:

    # Labs 3-4: the dashboard owns client C's serial port and drives its
    # OpenThread shell (close any serial monitor on that port first)
    python tools/dashboard_coap.py --serial /dev/ttyUSB0 --node <S-mleid>

    # Lab 5: the laptop talks CoAP to S itself, through the Border Router
    pip install aiocoap
    python tools/dashboard_coap.py --host <S-omr-address>

    # Labs 6-8: the same over DTLS with the node's pre-shared key (tools/coaps.py)
    python tools/dashboard_coap.py --host <S-omr-address> --psk soilsense-lab-6

    # Read-only: follow a saved copy of C's console where `ot coap observe` runs
    python tools/dashboard_coap.py --log /tmp/nodeC.log

Open http://localhost:5000, or http://<laptop IP>:5000 from a phone on the
same Wi-Fi.
"""

import argparse
import asyncio
import logging
import re
import struct
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

COAP_RESOURCE = "/env/temp"
VALVE_RESOURCE = "/act/valve"
CONTENT_FORMAT = 60  # application/cbor
OBSERVE_RENEW_S = 70  # re-register when nothing arrived for longer than Max-Age

state_lock = threading.Lock()
latest_sensor_data = {"error": "Waiting for first Observe notification..."}
valve_state = {"v": None, "note": "unknown"}
notify_count = 0
start_time = time.time()
recent_payloads = deque(maxlen=20)  # last 20 raw CBOR hex strings, for evidence
source = None  # the active SerialSource / HostSource / DtlsSource / LogSource


# --- CBOR decoding for the two contracts of Lab 3 ---

def float16_to_float(h: int) -> float:
    """Decode IEEE 754 half-precision (16-bit) to Python float."""
    sign = (h >> 15) & 0x1
    exp = (h >> 10) & 0x1F
    mant = h & 0x3FF
    if exp == 0:
        val = mant / 1024.0 * 2 ** (-14)
    elif exp == 31:
        return float("nan") if mant else (float("-inf") if sign else float("inf"))
    else:
        val = (1 + mant / 1024.0) * 2 ** (exp - 15)
    return -val if sign else val


def decode_env_temp_cbor(payload: bytes):
    """{"t": float16} is always A1 61 74 F9 hh ll; anything else returns None."""
    if len(payload) != 6 or payload[:4] != b"\xa1\x61\x74\xf9":
        return None
    return float16_to_float(struct.unpack(">H", payload[4:6])[0])


def decode_valve_cbor(payload: bytes):
    """{"v": 0|1} is A1 61 76 0v; anything else returns None."""
    if len(payload) != 4 or payload[:3] != b"\xa1\x61\x76" or payload[3] > 1:
        return None
    return payload[3]


def handle_payload(payload: bytes, code: str = "2.05"):
    """Update the shared state from one response or notification."""
    global latest_sensor_data, notify_count

    temp = decode_env_temp_cbor(payload)
    if temp is not None:
        with state_lock:
            latest_sensor_data = {
                "temperature": round(temp, 2),
                "raw_cbor": payload.hex(),
                "bytes": len(payload),
                "at": time.time(),
            }
            notify_count += 1
            recent_payloads.append(payload.hex())
        print(f"[CoAP] {COAP_RESOURCE} = {temp:.2f} C  (CBOR: {payload.hex()})")
        return

    valve = decode_valve_cbor(payload)
    if valve is not None:
        with state_lock:
            valve_state.update(v=valve, note="open" if valve else "closed")
        print(f"[CoAP] {VALVE_RESOURCE} = {valve}  (CBOR: {payload.hex()})")
        return

    text = payload.decode("ascii", errors="replace")
    with state_lock:
        latest_sensor_data = {"error": f"{code} {text}".strip()}
    print(f"[CoAP] {code} with payload {payload.hex()} ({text!r})")


# --- Source 1: client C's OpenThread shell over serial (Labs 3-4) ---

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PROMPT_RE = re.compile(r"uart:~\$ ?")
# The shell redraws its prompt between the bytes it prints, so strip the
# prompt before matching. Example of one clean line:
#   coap response from fdde:...:1a07 OBS=3 with payload: a16174f94e43
RESPONSE_RE = re.compile(r"coap response from (\S+)(?: OBS=\d+)? with payload: ([0-9a-fA-F]+)")


class SerialSource:
    def __init__(self, port: str, node: str):
        import serial

        self.node = node
        self.ser = serial.Serial(port, 115200, timeout=0.2)
        self.write_lock = threading.Lock()
        self.last_rx = 0.0
        self.describe = f"client C's shell on {port}, observing [{node}]"

    def send(self, line: str):
        with self.write_lock:
            self.ser.write((line + "\r").encode())

    def observe(self):
        self.send("ot coap cancel")
        self.send(f"ot coap observe {self.node} {COAP_RESOURCE.lstrip('/')}")
        self.last_rx = time.time()

    def set_valve(self, value: int):
        self.send(f"ot coap put {self.node} {VALVE_RESOURCE.lstrip('/')} con {value}")

    def run(self):
        self.send("ot coap start")
        time.sleep(0.5)
        self.observe()
        self.send(f"ot coap get {self.node} {VALVE_RESOURCE.lstrip('/')}")
        buf = ""
        while True:
            chunk = self.ser.read(512).decode(errors="ignore")
            if chunk:
                # Split before stripping: an escape sequence can straddle two reads.
                buf += chunk
                *lines, buf = buf.split("\n")
                for line in lines:
                    m = RESPONSE_RE.search(PROMPT_RE.sub("", ANSI_RE.sub("", line)))
                    if m:
                        self.last_rx = time.time()
                        handle_payload(bytes.fromhex(m.group(2)), code="")
                    elif "ResponseTimeout" in line:
                        print(f"[CoAP] {PROMPT_RE.sub('', ANSI_RE.sub('', line)).strip()}")
            if time.time() - self.last_rx > OBSERVE_RENEW_S:
                print("[CoAP] No notification for a while: registering again")
                self.observe()


# --- Source 2: CoAP from the laptop, through the Border Router (Lab 5) ---

class HostSource:
    def __init__(self, host: str):
        self.uri = f"coap://[{host}]"
        self.loop = asyncio.new_event_loop()
        self.ctx = None
        self.describe = f"CoAP over Wi-Fi and the Border Router to [{host}]"

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())

    async def main(self):
        from aiocoap import Context

        self.ctx = await Context.create_client_context()
        await self.get_valve()
        while True:
            await self.observe_once()
            await asyncio.sleep(10)  # the 5.03 Max-Age (Lab 4): retry after it

    async def observe_once(self):
        from aiocoap import GET, Message

        req = Message(code=GET, uri=self.uri + COAP_RESOURCE, observe=0)
        try:
            pr = self.ctx.request(req)
            first = await pr.response
            handle_payload(first.payload, str(first.code))
            async for resp in pr.observation:
                handle_payload(resp.payload, str(resp.code))
                if not resp.code.is_successful():
                    break
        except Exception as e:
            with state_lock:
                latest_sensor_data.clear()
                latest_sensor_data["error"] = f"no answer ({e.__class__.__name__})"
            print(f"[CoAP] Observe ended: {e!r}")

    async def get_valve(self):
        from aiocoap import GET, Message

        try:
            resp = await self.ctx.request(Message(code=GET, uri=self.uri + VALVE_RESOURCE)).response
            handle_payload(resp.payload, str(resp.code))
        except Exception as e:
            print(f"[CoAP] GET {VALVE_RESOURCE} failed: {e!r}")

    async def put_valve(self, value: int):
        from aiocoap import PUT, Message

        req = Message(code=PUT, uri=self.uri + VALVE_RESOURCE,
                      payload=bytes([0xA1, 0x61, 0x76, value]), content_format=CONTENT_FORMAT)
        resp = await self.ctx.request(req).response
        print(f"[CoAP] PUT {VALVE_RESOURCE} {value}: {resp.code}")
        handle_payload(resp.payload, str(resp.code))

    def set_valve(self, value: int):
        asyncio.run_coroutine_threadsafe(self.put_valve(value), self.loop)


# --- Source 2b: CoAP over DTLS with a pre-shared key (Labs 6-8) ---

class DtlsSource:
    def __init__(self, host: str, identity: str, psk: str):
        self.host, self.identity, self.psk = host, identity, psk
        self.describe = f"CoAP over DTLS (PSK identity {identity}) to [{host}]:5684"

    def session(self):
        from coaps import CoapsSession
        return CoapsSession(self.host, self.identity, self.psk)

    def run(self):
        from coaps import code_str
        while True:
            try:
                with self.session() as s:
                    print(f"[CoAPS] Session up, handshake {s.handshake_ms:.0f} ms")
                    code, body, _ = s.request("GET", VALVE_RESOURCE.lstrip("/"))
                    handle_payload(body, code_str(code))
                    code, body, _ = s.request("GET", COAP_RESOURCE.lstrip("/"), observe=0)
                    handle_payload(body, code_str(code))
                    for _, code, body in s.notifications(timeout=OBSERVE_RENEW_S):
                        handle_payload(body, code_str(code))
            except Exception as e:
                with state_lock:
                    latest_sensor_data.clear()
                    latest_sensor_data["error"] = f"no session ({e})"
                print(f"[CoAPS] {e!r}")
            time.sleep(10)

    def set_valve(self, value: int):
        def put():
            from coaps import code_str
            with self.session() as s:
                code, body, _ = s.request("PUT", VALVE_RESOURCE.lstrip("/"),
                                          bytes([0xA1, 0x61, 0x76, value]), cbor=True)
                print(f"[CoAPS] PUT {VALVE_RESOURCE} {value}: {code_str(code)}")
                handle_payload(body, code_str(code))
        threading.Thread(target=put, daemon=True).start()


# --- Source 3: a saved console log (read-only) ---

class LogSource:
    def __init__(self, path: Path):
        self.path = path
        self.describe = f"the console log {path}"

    def set_valve(self, value: int):
        raise RuntimeError("read-only source")

    def run(self):
        while not self.path.exists():
            print(f"[CoAP] Waiting for log file: {self.path}")
            time.sleep(1)
        with self.path.open("r", errors="ignore") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                m = RESPONSE_RE.search(PROMPT_RE.sub("", ANSI_RE.sub("", line)))
                if m:
                    handle_payload(bytes.fromhex(m.group(2)))


# --- Frontend (User Domain) — same skeleton as the Lab 0 / Lab 0.5 dashboards ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoT Lab: CoAP Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: system-ui, sans-serif; background-color: #f4f4f9; padding: 2rem; max-width: 800px; margin: 0 auto; color: #333; }
        .card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 1.5rem; }
        .status { font-family: monospace; font-size: 0.9rem; color: #666; }
        .badge { background: #e9ecef; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.85rem; font-family: monospace; }
        .proto-note { background: #fff3cd; padding: 0.75rem 1rem; border-radius: 4px; font-size: 0.85rem; border-left: 4px solid #ffc107; margin-bottom: 1.5rem; }
        .stats { display: flex; gap: 1rem; margin-top: 1rem; }
        .stat { flex: 1; background: #e9ecef; padding: 0.75rem; border-radius: 4px; text-align: center; }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #0056b3; font-family: monospace; }
        .stat-label { font-size: 0.8rem; color: #666; margin-top: 0.25rem; }
        .raw { font-family: monospace; font-size: 0.85rem; color: #555; word-break: break-all; }
        .btn-group { display: flex; gap: 1rem; margin-top: 1rem; }
        .btn { flex: 1; padding: 1rem; font-size: 1rem; border: none; border-radius: 4px; cursor: pointer; color: white; font-weight: bold; }
        .btn-on { background-color: #28a745; }
        .btn-off { background-color: #dc3545; }
        .btn:disabled { opacity: 0.4; cursor: default; }
    </style>
</head>
<body>
    <h2>IoT Systems Design Lab: CoAP Implementation</h2>
    <p class="status">Resource: <span class="badge">{{ resource }}</span> Content-Format: <span class="badge">{{ content_format }} (application/cbor)</span></p>

    <div class="proto-note">
        <strong>Protocol:</strong> Unlike the HTTP and MQTT dashboards, nothing polls the node
        and there is no broker. The node <em>pushes</em> a 6-byte CBOR payload to its observers
        (CoAP Observe, RFC 7641) when the temperature moves. Path: {{ describe }}.
    </div>

    <div class="card">
        <h3>Sensing Capability (CoAP Observe: {{ resource }})</h3>
        <canvas id="telemetryChart" height="100"></canvas>
        <p class="status" id="conn-status">Waiting for data...</p>
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="notify-count">0</div>
                <div class="stat-label">Observe notifications received</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="poll-saved">0</div>
                <div class="stat-label">Equivalent 1&nbsp;Hz polls avoided</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="bytes-per">6 B</div>
                <div class="stat-label">CBOR payload size</div>
            </div>
        </div>
        <p class="status" style="margin-top: 1rem;">Last raw CBOR: <span class="raw" id="raw-cbor">&mdash;</span></p>
    </div>

    <div class="card">
        <h3>Actuating Capability (CoAP PUT: {{ valve }})</h3>
        <p class="status">Valve: <span class="badge" id="valve-state">unknown</span></p>
        <div class="btn-group">
            <button class="btn btn-on" onclick="setValve(1)" {{ 'disabled' if readonly }}>Open</button>
            <button class="btn btn-off" onclick="setValve(0)" {{ 'disabled' if readonly }}>Close</button>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('telemetryChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Temperature (C)', borderColor: '#0056b3', data: [], fill: false, tension: 0.1 }] },
            options: { animation: false, scales: { y: { beginAtZero: false } } }
        });
        let lastAt = 0;

        function updateChart(temp) {
            chart.data.labels.push(new Date().toLocaleTimeString());
            chart.data.datasets[0].data.push(temp);
            if (chart.data.labels.length > 20) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            chart.update();
        }

        function fetchSensorData() {
            fetch('/api/sensor').then(res => res.json()).then(data => {
                const status = document.getElementById('conn-status');
                if (data.error) {
                    status.innerText = "Waiting: " + data.error;
                    status.style.color = "orange";
                } else if (data.at !== lastAt) {
                    lastAt = data.at;
                    status.innerText = "Connected. Receiving CoAP Observe notifications.";
                    status.style.color = "green";
                    updateChart(data.temperature);
                    document.getElementById('raw-cbor').innerText = data.raw_cbor;
                }
            });
        }

        function fetchStats() {
            fetch('/api/stats').then(res => res.json()).then(s => {
                document.getElementById('notify-count').innerText = s.notify_count;
                document.getElementById('poll-saved').innerText = s.polls_avoided;
                document.getElementById('valve-state').innerText = s.valve;
            });
        }

        function setValve(v) {
            fetch('/api/valve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ v: v }) });
        }

        // Observe is push-based on the radio side; the browser still asks Flask for
        // the value it holds in memory.
        setInterval(fetchSensorData, 1000);
        setInterval(fetchStats, 1000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        resource=COAP_RESOURCE,
        valve=VALVE_RESOURCE,
        content_format=CONTENT_FORMAT,
        describe=source.describe,
        readonly=isinstance(source, LogSource),
    )


@app.route("/api/sensor", methods=["GET"])
def api_sensor():
    with state_lock:
        return jsonify(latest_sensor_data)


@app.route("/api/stats", methods=["GET"])
def api_stats():
    with state_lock:
        elapsed = max(1, int(time.time() - start_time))
        return jsonify(
            {
                "notify_count": notify_count,
                "polls_avoided": max(0, elapsed - notify_count),
                "elapsed_seconds": elapsed,
                "recent_payloads": list(recent_payloads),
                "valve": valve_state["note"],
            }
        )


@app.route("/api/valve", methods=["POST"])
def api_valve():
    value = int(request.get_json(force=True).get("v", 0))
    if value not in (0, 1):
        return jsonify({"error": "v must be 0 or 1"}), 400
    try:
        source.set_valve(value)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    with state_lock:
        valve_state["note"] = f"{'opening' if value else 'closing'}..."
    return jsonify({"ok": True})


def main():
    global source

    parser = argparse.ArgumentParser(description="CoAP / CBOR dashboard for /env/temp and /act/valve")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--serial", metavar="PORT", help="client C's serial port (Labs 3-4); needs --node")
    mode.add_argument("--host", metavar="ADDR", help="S's off-mesh routable address (Lab 5)")
    mode.add_argument("--log", type=Path, help="file holding a copy of C's console (read-only)")
    parser.add_argument("--node", metavar="ADDR", help="S's mesh-local EID, for --serial")
    parser.add_argument("--psk", help="with --host: the node's pre-shared key, for CoAP over DTLS (Labs 6-8)")
    parser.add_argument("--identity", default="soilsense-pilot", help="PSK identity, with --psk")
    parser.add_argument("--port", type=int, default=5000, help="dashboard HTTP port")
    args = parser.parse_args()

    if args.serial:
        if not args.node:
            parser.error("--serial needs --node <S-mleid>")
        source = SerialSource(args.serial, args.node)
    elif args.host and args.psk:
        source = DtlsSource(args.host, args.identity, args.psk)
    elif args.host:
        source = HostSource(args.host)
    else:
        source = LogSource(args.log)

    threading.Thread(target=source.run, daemon=True).start()

    print("[*] CoAP Dashboard running.")
    print(f"[*] Reaching the node through {source.describe}")
    print(f"[*] Open http://localhost:{args.port} in your browser")
    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
