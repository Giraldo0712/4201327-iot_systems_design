#!/usr/bin/env python3
"""Figures for the session-3 deck (03_coap.md).

    python3 coap_figs.py       # writes coap_*.svg here

Timings follow RFC 7252 §4.8 defaults (ACK_TIMEOUT 2 s, ACK_RANDOM_FACTOR 1.5,
MAX_RETRANSMIT 4) and the Lab 3 firmware's Observe policy (0.5 °C, 45 s heartbeat).
Sequences are schematic: the spacing is not to scale.
"""
from pathlib import Path

from figlib import C, GRID, INK, MUTED, PAL, T, line, rect, save, svg, text

HERE = Path(__file__).resolve().parent
TH, ASD = PAL["Thread"], PAL["ASD"]


def exchange():
    body = []
    def lanes(x, title, col, msgs):
        cx, sx = x + 40, x + 420
        body.append(text(x + 230, 30, title, 24, 700, C[col], "middle"))
        body.append(text(cx, 62, "client", 19, 700, INK, "middle"))
        body.append(text(sx, 62, "server", 19, 700, INK, "middle"))
        bottom = 90 + len(msgs) * 50
        body.append(line(cx, 74, cx, bottom, GRID, 3))
        body.append(line(sx, 74, sx, bottom, GRID, 3))
        y = 100
        for label, right, strong in msgs:
            a, b = (cx, sx) if right else (sx, cx)
            colr = C[col] if strong else MUTED
            body.append(line(a, y + 6, b - (8 if right else -8), y + 20, colr, 2, arrow=True))
            body.append(text((cx + sx) / 2, y - 2, label, 20, 700 if strong else 400, colr, "middle"))
            y += 50
        return bottom
    h1 = lanes(10, "HTTP over TCP (Lab 0)", "gray",
               [("SYN", True, False), ("SYN-ACK", False, False), ("ACK", True, False),
                ("GET /api/sensor + headers, ~150 B", True, True), ("200 OK + headers, ~120 B", False, True),
                ("FIN", True, False), ("ACK, FIN", False, False), ("ACK", True, False)])
    h2 = lanes(560, "CoAP over UDP (Lab 3)", ASD,
               [("CON GET /env/temp", True, True), ("ACK 2.05 + 6 B of CBOR", False, True)])
    body.append(text(790, h2 + 60, "one datagram each way:", 21, 700, C[ASD], "middle"))
    body.append(text(790, h2 + 90, "no handshake, no teardown", 21, 400, INK, "middle"))
    return svg(1040, max(h1, h2) + 20, body)


def header():
    x0, bw = 40, 1000 / 32
    fields = [("Ver", 2), ("T", 2), ("TKL", 4), ("Code", 8), ("Message ID", 16)]
    body = [text(x0, 30, "4-byte fixed header", 22, 700, C[ASD])]
    x = x0
    for name, bits in fields:
        w = bits * bw
        body.append(rect(x, 44, w, 56, T[ASD], C[ASD], 2, 4))
        body.append(text(x + w / 2, 72, name, 20, 700, C[ASD], "middle"))
        body.append(text(x + w / 2, 93, f"{bits} bits", 15, 400, MUTED, "middle"))
        x += w
    rows = [("Token", "0–8 B", "matches a response to its request"),
            ("Options", "delta-encoded", "Uri-Path, Content-Format, Observe, Max-Age…"),
            ("FF", "1 B", "end of options"),
            ("Payload", "", "CBOR in this course")]
    y = 118
    for name, size, what in rows:
        body.append(rect(x0, y, 1000, 50, "#ffffff", MUTED, 2, 4))
        body.append(text(x0 + 16, y + 33, name, 20, 700, INK))
        body.append(text(x0 + 170, y + 33, size, 19, 400, MUTED))
        body.append(text(x0 + 360, y + 33, what, 19, 400, INK))
        y += 58
    body.append(text(x0, y + 26, "T: CON, NON, ACK or RST · Code c.dd: 0.01 GET, 0.03 PUT, 2.04 Changed, 2.05 Content, 4.04 Not Found",
                     18, 400, MUTED))
    return svg(1080, y + 40, body)


def retransmit():
    x0, x1, tmax = 60, 1040, 100.0
    def xs(t):
        return x0 + t / tmax * (x1 - x0)
    body = [line(x0, 220, x1, 220, INK, 2)]
    for t in range(0, 101, 10):
        body.append(line(xs(t), 220, xs(t), 228, INK, 2))
        body.append(text(xs(t), 252, f"{t} s", 20, 400, MUTED, "middle"))
    lo, hi, wait_lo = 0.0, 0.0, 2.0
    sends = [(0.0, 0.0)]
    for _ in range(4):
        lo, hi = lo + wait_lo, hi + wait_lo * 1.5
        sends.append((lo, hi))
        wait_lo *= 2
    for i, (a, b) in enumerate(sends):
        body.append(rect(xs(a) - 3, 60, max(xs(b) - xs(a), 0) + 6, 110, T[ASD], C[ASD], 2, 4))
        if i == 0:
            body.append(text(xs(a) - 3, 32, "send", 20, 700, C[ASD]))
        else:
            body.append(text((xs(a) + xs(b)) / 2, 50, f"#{i}", 20, 700, C[ASD], "middle"))
    give_lo, give_hi = lo + wait_lo, hi + wait_lo * 1.5
    body.append(rect(xs(give_lo), 60, xs(give_hi) - xs(give_lo), 110, T["c5"], C["c5"], 2, 4))
    body.append(text((xs(give_lo) + xs(give_hi)) / 2, 50, "give up", 20, 700, C["c5"], "middle"))
    body.append(text(x0, 200, "each wait is random in [1, 1.5] × its nominal value, and doubles", 20, 400, MUTED))
    return svg(1080, 270, body)


def observe():
    x0, x1 = 170, 1040
    body = []
    def lane(y, title, col):
        body.append(text(x0 - 20, y + 8, title, 21, 700, C[col], "end"))
        body.append(line(x0, y, x1, y, GRID, 3))
    lane(70, "polling", "gray")
    for i in range(6):
        x = x0 + 40 + i * 160
        body.append(line(x, 40, x, 100, MUTED, 3))
        body.append(text(x, 128, "24.5", 20, 400, MUTED, "middle"))
    body.append(text(x1, 160, "a GET every 60 s: both radios pay, even when nothing changed", 20, 400, MUTED, "end"))
    lane(250, "Observe", ASD)
    marks = [(40, "register", ASD, "GET + Observe: 0"), (330, "NON", ASD, "moved > 0.5 °C"),
             (520, "NON", ASD, "moved again"), (800, "CON", "c6", "45 s quiet: heartbeat")]
    for dx, lab, col, why in marks:
        x = x0 + dx
        body.append(line(x, 220, x, 280, C[col], 4))
        body.append(text(x, 210, lab, 20, 700, C[col], "middle"))
        body.append(text(x, 308, why, 20, 400, INK, "middle"))
    body.append(text(x1, 340, "the server, who knows when the value changed, decides when to talk", 20, 700, C[ASD], "end"))
    return svg(1080, 356, body)


def sed():
    x0, x1, tmax = 170, 1040, 6.0
    def xs(t):
        return x0 + t / tmax * (x1 - x0)
    ys = {"C, client": 70, "parent router": 190, "S, asleep": 310}
    body = []
    for name, y in ys.items():
        body.append(text(x0 - 20, y + 7, name, 20, 700, INK, "end"))
        body.append(line(x0, y, x1, y, GRID, 3))
    body.append(rect(xs(0.05), 290, xs(4.95) - xs(0.05), 40, T["gray"], MUTED, 1, 4))
    body.append(text((xs(0.05) + xs(4.95)) / 2, 316, "radio off", 20, 400, MUTED, "middle"))
    for t, lab in [(0.0, "CON PUT"), (2.5, "retransmit")]:
        body.append(line(xs(t), 70, xs(t) + 30, 182, C[ASD], 3, arrow=True))
        body.append(text(xs(t) + 6, 56, lab, 20, 700, C[ASD]))
        body.append(text(xs(t) + 40, 220, "held", 20, 400, MUTED))
    body.append(line(xs(5.0), 302, xs(5.0) + 20, 198, C[TH], 3, arrow=True))
    body.append(text(xs(5.0) - 10, 260, "poll", 20, 700, C[TH], "end"))
    body.append(line(xs(5.15), 190, xs(5.35), 300, C[TH], 3, arrow=True))
    body.append(line(xs(5.35), 190, xs(5.55), 300, C[TH], 3, arrow=True))
    body.append(text(xs(5.6), 160, "both copies", 20, 700, C[TH], "middle"))
    body.append(line(x0, 360, x1, 360, INK, 2))
    for t in range(0, 7):
        body.append(line(xs(t), 360, xs(t), 368, INK, 2))
        body.append(text(xs(t), 392, f"{t} s", 20, 400, MUTED, "middle"))
    body.append(text(x1, 424, "poll period 5 s · CoAP's first wait 2–3 s", 20, 400, MUTED, "end"))
    return svg(1080, 436, body)


if __name__ == "__main__":
    for name, fig in [("coap_exchange.svg", exchange), ("coap_header.svg", header),
                      ("coap_retransmit.svg", retransmit), ("coap_observe.svg", observe), ("coap_sed.svg", sed)]:
        print(save(HERE, name, fig()))
