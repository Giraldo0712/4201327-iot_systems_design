"""CoAP over DTLS 1.2 with a pre-shared key, for the SoilSense nodes of Labs 6-8.

One cipher suite, TLS_PSK_WITH_AES_128_CCM_8 (RFC 6655), the one the nodes serve.
Needs only the `cryptography` package, which the Zephyr virtual environment
already has. With verbose=True the handshake prints each flight as it goes.

    from coaps import CoapsSession
    with CoapsSession("2800:db8::1234", "soilsense-pilot", b"soilsense-lab-6") as s:
        code, payload = s.request("GET", "env/temp")
"""
import hashlib
import hmac
import os
import random
import socket
import struct
import time

from cryptography.hazmat.primitives.ciphers.aead import AESCCM

PORT = 5684
SUITE = 0xC0A8  # TLS_PSK_WITH_AES_128_CCM_8
VERSION = b"\xfe\xfd"  # DTLS 1.2
CT_CCS, CT_ALERT, CT_HANDSHAKE, CT_APP = 20, 21, 22, 23
HT_CLIENT_HELLO, HT_SERVER_HELLO, HT_HELLO_VERIFY = 1, 2, 3
HT_SERVER_KEY_EXCHANGE, HT_SERVER_HELLO_DONE = 12, 14
HT_CLIENT_KEY_EXCHANGE, HT_FINISHED = 16, 20


class DtlsError(Exception):
    pass


def prf(secret, label, seed, n):
    """TLS 1.2 PRF with SHA-256 (RFC 5246 §5)."""
    seed = label + seed
    out, a = b"", seed
    while len(out) < n:
        a = hmac.new(secret, a, hashlib.sha256).digest()
        out += hmac.new(secret, a + seed, hashlib.sha256).digest()
    return out[:n]


class DtlsPskClient:
    def __init__(self, host, identity, psk, port=PORT, timeout=10.0, verbose=False):
        self.addr = (host, port)
        self.identity = identity.encode() if isinstance(identity, str) else identity
        self.psk = psk.encode() if isinstance(psk, str) else psk
        self.timeout = timeout
        self.verbose = verbose
        self.sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = {0: 0, 1: 0}  # next record sequence number per epoch
        self.msg_seq = 0
        self.transcript = b""
        self.keys = None
        self.t0 = time.monotonic()

    def log(self, what):
        if self.verbose:
            print(f"  {1000 * (time.monotonic() - self.t0):7.1f} ms  {what}")

    # --- records ---

    def record(self, ctype, body, epoch):
        seqnum = struct.pack(">H", epoch) + self.seq[epoch].to_bytes(6, "big")
        self.seq[epoch] += 1
        if epoch:
            k = self.keys
            aad = seqnum + bytes([ctype]) + VERSION + struct.pack(">H", len(body))
            body = seqnum + AESCCM(k["client_key"], tag_length=8).encrypt(k["client_iv"] + seqnum, body, aad)
        return bytes([ctype]) + VERSION + seqnum + struct.pack(">H", len(body)) + body

    def parse_records(self, datagram):
        """Yield (type, epoch, plaintext) for every record the datagram holds."""
        i = 0
        while i + 13 <= len(datagram):
            ctype = datagram[i]
            seqnum = datagram[i + 3:i + 11]
            epoch = struct.unpack(">H", seqnum[:2])[0]
            n = struct.unpack(">H", datagram[i + 11:i + 13])[0]
            body = datagram[i + 13:i + 13 + n]
            i += 13 + n
            if epoch:
                if not self.keys or n < 16:
                    continue
                k = self.keys
                aad = seqnum + bytes([ctype]) + VERSION + struct.pack(">H", n - 16)
                try:
                    body = AESCCM(k["server_key"], tag_length=8).decrypt(k["server_iv"] + body[:8], body[8:], aad)
                except Exception:
                    continue  # DTLS drops a record that fails authentication
            yield ctype, epoch, body

    # --- handshake ---

    def handshake_msg(self, htype, body):
        """A handshake message sent as a single fragment (RFC 6347 §4.2.2)."""
        msg = bytes([htype]) + len(body).to_bytes(3, "big") + struct.pack(">H", self.msg_seq) + \
            (0).to_bytes(3, "big") + len(body).to_bytes(3, "big") + body
        self.msg_seq += 1
        return msg

    def exchange(self, flight, done):
        """Send a flight, retransmitting it on silence (RFC 6347 §4.2.4), until
        done(got) is true; got maps handshake types (and "ccs") to messages."""
        got, wait, deadline = {}, 1.0, time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            self.sock.sendto(b"".join(flight()), self.addr)
            end = min(time.monotonic() + wait, deadline)
            while time.monotonic() < end:
                self.sock.settimeout(max(end - time.monotonic(), 0.01))
                try:
                    data, _ = self.sock.recvfrom(2048)
                except socket.timeout:
                    break
                for ctype, epoch, body in self.parse_records(data):
                    if ctype == CT_ALERT:
                        raise DtlsError(f"alert {body.hex()} from the server")
                    if ctype == CT_HANDSHAKE and len(body) >= 12:
                        got.setdefault(body[0], body)
                    elif ctype == CT_CCS:
                        got.setdefault("ccs", body)
                if done(got):
                    return got
            wait *= 2
            self.log("no answer: retransmitting the flight")
        raise DtlsError(f"handshake timed out after {self.timeout:.0f} s (wrong key, or server unreachable)")

    def handshake(self):
        """Full PSK handshake; returns its duration in ms."""
        self.t0 = time.monotonic()
        client_random = struct.pack(">I", int(time.time())) + os.urandom(28)
        suites = struct.pack(">HH", 2, SUITE) + b"\x01\x00"

        def hello(cookie):
            return self.handshake_msg(HT_CLIENT_HELLO, VERSION + client_random + b"\x00" +
                                      bytes([len(cookie)]) + cookie + suites)

        self.log("-> ClientHello")
        ch = hello(b"")
        got = self.exchange(lambda: [self.record(CT_HANDSHAKE, ch, 0)],
                            lambda g: HT_HELLO_VERIFY in g or HT_SERVER_HELLO_DONE in g)
        if HT_HELLO_VERIFY in got:
            body = got[HT_HELLO_VERIFY][12:]
            cookie = body[3:3 + body[2]]
            self.log(f"<- HelloVerifyRequest: a {len(cookie)}-byte cookie, proof we own our address")
            ch = hello(cookie)  # the hello with the cookie starts the transcript
            self.log("-> ClientHello + cookie")
            got = self.exchange(lambda: [self.record(CT_HANDSHAKE, ch, 0)],
                                lambda g: HT_SERVER_HELLO_DONE in g)
        self.transcript = ch
        for t in (HT_SERVER_HELLO, HT_SERVER_KEY_EXCHANGE, HT_SERVER_HELLO_DONE):
            if t in got:
                self.transcript += got[t]

        sh = got[HT_SERVER_HELLO][12:]
        server_random = sh[2:34]
        sid_len = sh[34]
        suite = struct.unpack(">H", sh[35 + sid_len:37 + sid_len])[0]
        if suite != SUITE:
            raise DtlsError(f"server chose cipher suite 0x{suite:04x}")
        self.log("<- ServerHello, ServerHelloDone")

        n = len(self.psk)
        premaster = struct.pack(">H", n) + bytes(n) + struct.pack(">H", n) + self.psk  # RFC 4279 §2
        master = prf(premaster, b"master secret", client_random + server_random, 48)
        kb = prf(master, b"key expansion", server_random + client_random, 40)
        self.keys = {"client_key": kb[0:16], "server_key": kb[16:32], "client_iv": kb[32:36], "server_iv": kb[36:40]}

        cke = self.handshake_msg(HT_CLIENT_KEY_EXCHANGE, struct.pack(">H", len(self.identity)) + self.identity)
        self.transcript += cke
        fin = self.handshake_msg(HT_FINISHED, prf(master, b"client finished",
                                                   hashlib.sha256(self.transcript).digest(), 12))
        self.transcript += fin
        server_verify = prf(master, b"server finished", hashlib.sha256(self.transcript).digest(), 12)

        self.log(f'-> ClientKeyExchange (identity "{self.identity.decode()}"), ChangeCipherSpec, Finished')
        got = self.exchange(lambda: [self.record(CT_HANDSHAKE, cke, 0), self.record(CT_CCS, b"\x01", 0),
                                     self.record(CT_HANDSHAKE, fin, 1)],
                            lambda g: HT_FINISHED in g)
        if got[HT_FINISHED][12:24] != server_verify:
            raise DtlsError("the server's Finished doesn't verify")
        self.log("<- ChangeCipherSpec, Finished: session up")
        return 1000 * (time.monotonic() - self.t0)

    # --- application data ---

    def send(self, data):
        self.sock.sendto(self.record(CT_APP, data, 1), self.addr)

    def recv(self, timeout):
        """Next application-data payload, or None after `timeout` seconds."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.sock.settimeout(max(end - time.monotonic(), 0.01))
            try:
                data, _ = self.sock.recvfrom(2048)
            except socket.timeout:
                return None
            for ctype, epoch, body in self.parse_records(data):
                if ctype == CT_APP and epoch == 1:
                    return body
                if ctype == CT_ALERT and epoch == 1:
                    raise DtlsError(f"alert {body.hex()} from the server")
        return None

    def close(self):
        try:
            if self.keys:
                self.sock.sendto(self.record(CT_ALERT, b"\x01\x00", 1), self.addr)  # close_notify
        finally:
            self.sock.close()


# --- a minimal CoAP codec (RFC 7252), enough for /env/temp and /act/valve ---

CODES = {"GET": 1, "POST": 2, "PUT": 3, "DELETE": 4}
OPT_OBSERVE, OPT_URI_PATH, OPT_CONTENT_FORMAT = 6, 11, 12
CON, NON, ACK, RST = 0, 1, 2, 3


def coap_encode(mtype, code, mid, token, options, payload=b""):
    out = bytes([0x40 | (mtype << 4) | len(token), code]) + struct.pack(">H", mid) + token
    last = 0
    for num, val in sorted(options, key=lambda o: o[0]):
        delta, length = num - last, len(val)
        def ext(x):
            return (x, b"") if x < 13 else (13, bytes([x - 13])) if x < 269 else (14, struct.pack(">H", x - 269))
        d, de = ext(delta)
        l, le = ext(length)
        out += bytes([(d << 4) | l]) + de + le + val
        last = num
    return out + (b"\xff" + payload if payload else b"")


def coap_decode(msg):
    """(type, code, mid, token, {option: [values]}, payload)"""
    mtype, tkl, code = (msg[0] >> 4) & 3, msg[0] & 0x0F, msg[1]
    mid = struct.unpack(">H", msg[2:4])[0]
    token, i, num, opts = msg[4:4 + tkl], 4 + tkl, 0, {}

    def ext(v, i):
        if v == 13:
            return msg[i] + 13, i + 1
        if v == 14:
            return struct.unpack(">H", msg[i:i + 2])[0] + 269, i + 2
        return v, i

    while i < len(msg) and msg[i] != 0xFF:
        delta, length = msg[i] >> 4, msg[i] & 0x0F
        delta, i = ext(delta, i + 1)
        length, i = ext(length, i)
        num += delta
        opts.setdefault(num, []).append(msg[i:i + length])
        i += length
    return mtype, code, mid, token, opts, msg[i + 1:] if i < len(msg) else b""


def code_str(code):
    return f"{code >> 5}.{code & 0x1F:02d}"


class CoapsSession:
    """One DTLS session to a node, carrying any number of CoAP exchanges."""

    def __init__(self, host, identity, psk, port=PORT, verbose=False, timeout=10.0):
        self.dtls = DtlsPskClient(host, identity, psk, port, timeout, verbose)
        self.mid = random.randrange(0x10000)
        self.handshake_ms = None
        self.observing = {}  # token -> path, for every Observe registration

    def __enter__(self):
        self.handshake_ms = self.dtls.handshake()
        return self

    def __exit__(self, *exc):
        self.dtls.close()

    def _options(self, path, observe=None, cbor=False):
        opts = [(OPT_URI_PATH, seg.encode()) for seg in path.strip("/").split("/")]
        if observe is not None:
            opts.append((OPT_OBSERVE, b"" if observe == 0 else bytes([observe])))
        if cbor:
            opts.append((OPT_CONTENT_FORMAT, bytes([60])))
        return opts

    def request(self, method, path, payload=b"", cbor=False, observe=None):
        """CON request with RFC 7252 retransmission; returns (code, payload, options)."""
        self.mid = (self.mid + 1) & 0xFFFF
        token = os.urandom(4)
        msg = coap_encode(CON, CODES[method], self.mid, token, self._options(path, observe, cbor), payload)
        wait = random.uniform(2, 3)
        for _ in range(5):
            self.dtls.send(msg)
            end = time.monotonic() + wait
            while time.monotonic() < end:
                data = self.dtls.recv(end - time.monotonic())
                if data is None:
                    break
                mtype, code, mid, tok, opts, body = coap_decode(data)
                if mtype == ACK and mid == self.mid and code == 0:
                    end = time.monotonic() + 60  # empty ACK: a separate response follows
                    continue
                if tok == token:
                    if mtype == CON:
                        self.dtls.send(coap_encode(ACK, 0, mid, b"", []))
                    if observe == 0 and OPT_OBSERVE in opts:
                        self.observing[token] = path
                    return code, body, opts
                if tok in self.observing and mtype == CON:
                    self.dtls.send(coap_encode(ACK, 0, mid, b"", []))
            wait *= 2
        raise TimeoutError("no CoAP response")

    def notifications(self, timeout=None):
        """Yield (path, code, payload) for each notification on this session's Observe
        registrations, ACKing CON ones; stops after `timeout` s of silence. An error
        notification ends its observation (RFC 7641 §4.2)."""
        while self.observing:
            data = self.dtls.recv(timeout if timeout is not None else 3600)
            if data is None:
                return
            mtype, code, mid, tok, opts, body = coap_decode(data)
            if mtype == CON:
                self.dtls.send(coap_encode(ACK, 0, mid, b"", []))
            if tok not in self.observing:
                continue
            path = self.observing[tok]
            if OPT_OBSERVE not in opts:
                del self.observing[tok]
            yield path, code, body
