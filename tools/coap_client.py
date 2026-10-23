#!/usr/bin/env python3
"""Simple CoAP client for the SoilSense resources (/env/temp, /act/valve).

Two ways to reach node S:

    # Lab 5: the laptop talks CoAP to S through the Border Router (needs aiocoap)
    python coap_client.py --host 2800:db8::1234 get /env/temp
    python coap_client.py --host 2800:db8::1234 --count 10 get /env/temp
    python coap_client.py --host 2800:db8::1234 put /act/valve 1

    # Labs 3-4: drive client C's OpenThread shell over its serial port (needs pyserial;
    # close any serial monitor on that port first). The RTT includes the serial line.
    python coap_client.py --serial /dev/ttyUSB0 --host <S-mleid> --count 10 get /env/temp

With cbor2 installed the CBOR payload is decoded.
"""
import argparse
import asyncio
import re
import statistics
import time

try:
    import cbor2
except ImportError:
    cbor2 = None

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PROMPT_RE = re.compile(r"uart:~\$ ?")
RESPONSE_RE = re.compile(r"coap response from \S+(?: OBS=\d+)? with payload: ([0-9a-fA-F]*)\r*\n")


def show_payload(payload):
    if not payload:
        return
    if cbor2 is not None:
        try:
            print('Payload (CBOR):', cbor2.loads(payload), f'[{payload.hex()}]')
            return
        except Exception:
            pass
    print('Payload:', payload.hex())


async def over_ip(args):
    from aiocoap import Context, Message, GET, PUT

    proto = await Context.create_client_context()
    uri = f'coap://[{args.host}]{args.path}'
    rtts = []
    for i in range(args.count):
        if args.method == 'get':
            req = Message(code=GET, uri=uri)
        else:
            req = Message(code=PUT, uri=uri, payload=(args.value or '').encode())
        start = time.perf_counter()
        try:
            resp = await proto.request(req).response
        except Exception as e:
            print(f'[{i + 1}] Error:', e)
            continue
        rtt = (time.perf_counter() - start) * 1000
        rtts.append(rtt)
        print(f'[{i + 1}] Code: {resp.code}  RTT: {rtt:.0f} ms')
        if i == 0:
            show_payload(resp.payload)
    return rtts


def over_serial(args):
    import serial
    import termios

    ser = serial.Serial(args.serial, 115200, timeout=0.05)
    # Closing the port with HUPCL set resets some boards (CH343, CP210x).
    attrs = termios.tcgetattr(ser.fd)
    attrs[2] &= ~termios.HUPCL
    termios.tcsetattr(ser.fd, termios.TCSANOW, attrs)

    def send(line):
        ser.write((line + '\r').encode())
        ser.flush()

    def wait_response(timeout):
        raw, seen, end = '', None, time.perf_counter() + timeout
        while time.perf_counter() < end:
            raw += ser.read(256).decode(errors='ignore')
            # The shell redraws its prompt between the bytes it prints: strip it from
            # the whole buffer, since an escape sequence can straddle two reads.
            buf = PROMPT_RE.sub('', ANSI_RE.sub('', raw))
            if seen is None and 'coap response from' in buf:
                seen = time.perf_counter()  # the RTT stops here; the rest is the serial line
            m = RESPONSE_RE.search(buf)
            if m:
                return seen, bytes.fromhex(m.group(1))
            if 'ResponseTimeout' in buf:
                return None, None
        return None, None

    send('ot coap start')
    send('ot coap cancel')  # an Observe left running would answer in place of the GET
    time.sleep(0.5)
    ser.reset_input_buffer()
    path = args.path.lstrip('/')
    cmd = f'ot coap get {args.host} {path}' if args.method == 'get' else \
          f'ot coap put {args.host} {path} con {args.value or ""}'.rstrip()
    rtts = []
    for i in range(args.count):
        send(cmd)
        start = time.perf_counter()
        t, payload = wait_response(args.timeout)
        if t is None:
            print(f'[{i + 1}] Error: no response within {args.timeout:.0f} s')
        else:
            rtt = (t - start) * 1000
            rtts.append(rtt)
            print(f'[{i + 1}] RTT: {rtt:.0f} ms')
            if i == 0:
                show_payload(payload)
        time.sleep(0.5)
        ser.reset_input_buffer()
    ser.close()
    return rtts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', required=True, help="S's IPv6 address, without brackets")
    parser.add_argument('--serial', metavar='PORT', help="client C's serial port: send through its OpenThread shell")
    parser.add_argument('--count', type=int, default=1, help='repeat the request and report the median RTT')
    parser.add_argument('--timeout', type=float, default=10, help='seconds to wait for each response (--serial)')
    parser.add_argument('method', choices=['get', 'put'])
    parser.add_argument('path', help='resource, e.g. /env/temp or /act/valve')
    parser.add_argument('value', nargs='?', help='PUT value (0 or 1)')
    args = parser.parse_args()

    rtts = over_serial(args) if args.serial else asyncio.run(over_ip(args))
    if args.count > 1 and rtts:
        print(f'{len(rtts)}/{args.count} responses, median RTT {statistics.median(rtts):.0f} ms '
              f'(min {min(rtts):.0f}, max {max(rtts):.0f})')


if __name__ == '__main__':
    main()
