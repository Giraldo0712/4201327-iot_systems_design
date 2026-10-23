#!/usr/bin/env python3
"""Cliente CoAP simple para los recursos de SoilSense (/env/temp, /act/valve).
Requiere 'aiocoap' en el entorno host; con 'cbor2' instalado decodifica el payload CBOR.
Uso:
  python coap_client.py --host 2800:db8::1234 get /env/temp
  python coap_client.py --host 2800:db8::1234 --count 10 get /env/temp
  python coap_client.py --host 2800:db8::1234 put /act/valve 1
"""
import argparse
import asyncio
import statistics
import time

from aiocoap import Context, Message, GET, PUT

try:
    import cbor2
except ImportError:
    cbor2 = None


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


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True, help='Dirección IPv6 del nodo (sin corchetes)')
    parser.add_argument('--count', type=int, default=1, help='Repite la petición y reporta el RTT mediano')
    parser.add_argument('method', choices=['get', 'put'])
    parser.add_argument('path', help='Recurso, ej /env/temp o /act/valve')
    parser.add_argument('value', nargs='?', help='Valor para PUT (0/1)')
    args = parser.parse_args()

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

    if args.count > 1 and rtts:
        print(f'{len(rtts)}/{args.count} respuestas, RTT mediano {statistics.median(rtts):.0f} ms '
              f'(min {min(rtts):.0f}, max {max(rtts):.0f})')

if __name__ == '__main__':
    asyncio.run(main())
