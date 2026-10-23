#!/usr/bin/env python3
"""CoAP to MQTT bridge (Lab 7): the interchange between the mesh and the access network.

For every node it holds one DTLS session (tools/coaps.py), observes /env/temp and
/sys/health, decodes the CBOR and publishes JSON to the broker:

    soilsense/<node>/env      {"t": 24.5}
    soilsense/<node>/health   {"batt": 3300, "rssi": -56, "up": 3600, "hsfail": 0}

    python tools/coap_mqtt_bridge.py --psk <key> --node north=<S-omr> --node south=<C-omr>
    python tools/coap_mqtt_bridge.py --psk <key> --node north=<S-omr> --broker 192.168.1.20

    # A cloud broker over TLS with a client certificate (AWS IoT Core, for one)
    python tools/coap_mqtt_bridge.py --psk <key> --node north=<S-omr> --broker <endpoint> \
        --port 8883 --cafile AmazonRootCA1.pem --cert device.pem.crt --key private.pem.key

Needs paho-mqtt and cbor2 (pip install paho-mqtt cbor2) and the Zephyr virtual
environment's cryptography. A node that stops answering is retried every 10 s;
spotting it is the dashboard's job.
"""
import argparse
import json
import threading
import time

import cbor2
import paho.mqtt.client as mqtt

from coaps import CoapsSession, code_str

RETRY_S = 10
SILENCE_S = 150  # re-register after this long without a notification


def bridge_node(name, host, args, client):
    topic = {"env/temp": f"soilsense/{name}/env", "sys/health": f"soilsense/{name}/health"}

    def publish(path, code, body):
        if code >> 5 != 2:
            print(f"[{name}] {path}: {code_str(code)} {body!r}")
            return
        data = cbor2.loads(body)
        client.publish(topic[path], json.dumps(data), qos=0)
        print(f"[{name}] {topic[path]} <- {data}")

    while True:
        try:
            with CoapsSession(host, args.identity, args.psk) as s:
                print(f"[{name}] session up, handshake {s.handshake_ms:.0f} ms")
                for path in topic:
                    code, body, _ = s.request("GET", path, observe=0)
                    publish(path, code, body)
                for path, code, body in s.notifications(timeout=SILENCE_S):
                    publish(path, code, body)
                print(f"[{name}] no notification for {SILENCE_S} s: registering again")
        except Exception as e:
            print(f"[{name}] {e}; retrying in {RETRY_S} s")
            time.sleep(RETRY_S)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--node", action="append", required=True, metavar="NAME=ADDR",
                        help="a node's name and off-mesh address; repeat for every node")
    parser.add_argument("--psk", required=True, help="the nodes' pre-shared key")
    parser.add_argument("--identity", default="soilsense-pilot", help="PSK identity")
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--cafile", help="CA certificate: connect to the broker over TLS")
    parser.add_argument("--cert", help="client certificate, with --cafile")
    parser.add_argument("--key", help="client private key, with --cafile")
    args = parser.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="soilsense-bridge")
    if args.cafile:
        client.tls_set(ca_certs=args.cafile, certfile=args.cert, keyfile=args.key)
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_start()
    print(f"[bridge] publishing to {args.broker}:{args.port} under soilsense/#")

    for spec in args.node:
        name, _, host = spec.partition("=")
        threading.Thread(target=bridge_node, args=(name, host, args, client), daemon=True).start()

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
