#!/usr/bin/env python3
"""SoilSense end-to-end test suite (Lab 8, the Golden Master).

    python tools/test_e2e.py <node-omr> --psk <team-key> [--valve <valve-omr>]

Run it from the laptop, outside the mesh, with each node's OMR address: every
test that passes also proves the Border Router path. Uses tools/coaps.py (the
Zephyr virtual environment has its cryptography package) and cbor2.

  1. plain CoAP      UDP 5683 gets no answer
  2. DTLS            the team key gets a session, a wrong key doesn't
  3. contracts       /env/temp {"t"}, /sys/health {"batt", "rssi", "up", "hsfail", "ver"}
  4. valve           PUT {"v": 1}, GET, PUT {"v": 0}
  5. invalid input   an unknown path gets 4.04, a bad valve payload 4.00
  6. stress          20 GETs paced inside the rate limit: success ratio and latency
  7. burst           12 GETs back to back: the rate limiter answers 4.29

Exit code 0 when nothing FAILs.
"""
import argparse
import os
import socket
import statistics
import sys
import time

import cbor2

from coaps import CoapsSession, DtlsError, code_str

RATE_WINDOW_S = 10
RATE_MAX = 8
VALVE = {1: bytes([0xA1, 0x61, 0x76, 0x01]), 0: bytes([0xA1, 0x61, 0x76, 0x00])}

results = []


def record(name, status, detail=""):
    results.append((name, status, detail))
    print(f"[{status:4}] {name}" + (f": {detail}" if detail else ""))


def plain_coap_answers(host, timeout=3.0):
    """A raw CoAP GET /env/temp to UDP 5683; True if anything comes back."""
    msg = bytes([0x42, 0x01]) + os.urandom(2) + os.urandom(2) + b"\xb3env\x04temp"
    with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        try:
            s.sendto(msg, (host, 5683))
            s.recvfrom(512)
            return True
        except OSError:
            return False


def get_map(s, path):
    code, body, _ = s.request("GET", path)
    if code >> 5 != 2:
        return code, None
    try:
        return code, cbor2.loads(body)
    except Exception:
        return code, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("node", help="a node's OMR address")
    ap.add_argument("--psk", required=True, help="the team's DTLS key")
    ap.add_argument("--identity", default="soilsense-pilot")
    ap.add_argument("--valve", help="the valve node's OMR address, if not the same node")
    args = ap.parse_args()
    valve = args.valve or args.node

    print(f"=== SoilSense e2e suite: {args.node} ===\n")

    if plain_coap_answers(args.node):
        record("plain CoAP refused", "FAIL", "UDP 5683 answered: the node isn't on CoAPS only")
    else:
        record("plain CoAP refused", "PASS", "no answer on UDP 5683")

    try:
        with CoapsSession(args.node, args.identity, "definitely-not-the-key", timeout=8):
            record("wrong key refused", "FAIL", "a wrong key got a session")
    except DtlsError:
        record("wrong key refused", "PASS", "no session")

    try:
        session = CoapsSession(args.node, args.identity, args.psk).__enter__()
    except DtlsError as e:
        record("DTLS session", "FAIL", str(e))
        return report()
    record("DTLS session", "PASS", f"handshake {session.handshake_ms:.0f} ms")

    code, env = get_map(session, "env/temp")
    ok = isinstance(env, dict) and "t" in env
    record("/env/temp contract", "PASS" if ok else "FAIL", f"{code_str(code)} {env}")
    code, health = get_map(session, "sys/health")
    want = {"batt", "rssi", "up", "hsfail", "ver"}
    ok = isinstance(health, dict) and want <= set(health)
    record("/sys/health contract", "PASS" if ok else "FAIL", f"{code_str(code)} {health}")

    vs = session if valve == args.node else CoapsSession(valve, args.identity, args.psk).__enter__()
    steps = [("PUT", VALVE[1], 0x44, VALVE[1]), ("GET", b"", 0x45, VALVE[1]), ("PUT", VALVE[0], 0x44, VALVE[0])]
    lats, ok = [], True
    for method, payload, want_code, want_body in steps:
        t0 = time.monotonic()
        code, body, _ = vs.request(method, "act/valve", payload, cbor=bool(payload))
        lats.append(1000 * (time.monotonic() - t0))
        if code != want_code or body != want_body:
            ok = False
            record("valve round trip", "FAIL", f"{method}: {code_str(code)} {body.hex()}")
            break
    if ok:
        record("valve round trip", "PASS", f"open, read, close; avg {statistics.mean(lats):.0f} ms")

    code, _, _ = session.request("GET", "does/not/exist")
    record("unknown path -> 4.04", "PASS" if code == 0x84 else "FAIL", code_str(code))
    code, _, _ = vs.request("PUT", "act/valve", b"7")
    record("bad valve payload -> 4.00", "PASS" if code == 0x80 else "FAIL", code_str(code))

    print(f"\n(waiting {RATE_WINDOW_S} s for the rate-limit window)")
    time.sleep(RATE_WINDOW_S + 1)
    lats, served = [], 0
    for _ in range(20):
        t0 = time.monotonic()
        try:
            code, _, _ = session.request("GET", "env/temp")
            if code == 0x45:
                served += 1
                lats.append(1000 * (time.monotonic() - t0))
        except TimeoutError:
            pass
        time.sleep(RATE_WINDOW_S / RATE_MAX + 0.1)
    detail = f"{served}/20 served"
    if lats:
        detail += f", latency min/avg/max {min(lats):.0f}/{statistics.mean(lats):.0f}/{max(lats):.0f} ms"
    record("stress (20 paced GETs)", "PASS" if served >= 16 else "FAIL", detail)

    time.sleep(RATE_WINDOW_S + 1)
    codes = [session.request("GET", "env/temp")[0] for _ in range(12)]
    first = next((i + 1 for i, c in enumerate(codes) if c == 0x9D), None)
    record("burst -> 4.29", "PASS" if first else "FAIL",
           f"first 4.29 at request {first}" if first else "no 4.29 in 12 requests")

    session.__exit__(None, None, None)
    if vs is not session:
        vs.__exit__(None, None, None)
    return report()


def report():
    print("\n=== Summary ===")
    for name, status, detail in results:
        print(f"  {status:4}  {name}" + (f": {detail}" if detail else ""))
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
