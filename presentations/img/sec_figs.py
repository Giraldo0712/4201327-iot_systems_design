#!/usr/bin/env python3
"""Figures for the session-6 deck (06_security.md).

    python3 sec_figs.py       # writes sec_*.svg here

The handshake is the PSK flight sequence of RFC 6347 §4.2 as the lab firmware runs
it (with a HelloVerifyRequest cookie, no ServerKeyExchange).
"""
from pathlib import Path

from figlib import C, GRID, INK, MUTED, PAL, T, box, line, rect, save, svg, text

HERE = Path(__file__).resolve().parent
TH, RAID, TW = PAL["Thread"], PAL["RAID"], PAL["Trustworthiness"]


def layers():
    body = [box(20, 150, 170, 64, "laptop", "gray", 22, ""),
            box(400, 150, 170, 64, "OTBR", PAL["SCD"], 22, ""),
            box(790, 150, 120, 64, "router", TH, 20, ""),
            box(950, 150, 110, 64, "S", TH, 24, "")]
    body.append(line(190, 182, 400, 182, INK, 3))
    body.append(text(295, 140, "Wi-Fi", 20, 700, MUTED, "middle"))
    body.append(line(570, 182, 790, 182, C[TH], 3))
    body.append(line(910, 182, 950, 182, C[TH], 3))
    body.append(text(680, 140, "Thread mesh", 20, 700, C[TH], "middle"))
    body.append(rect(570, 240, 490, 40, T[TH], C[TH], 2, 8))
    body.append(text(815, 267, "Thread network key: each mesh hop", 19, 700, C[TH], "middle"))
    body.append(rect(20, 300, 1040, 40, T[TW], C[TW], 2, 8))
    body.append(text(540, 327, "DTLS session: laptop to S, end to end, through the OTBR", 19, 700, C[TW], "middle"))
    body.append(rect(20, 60, 380, 40, "#ffffff", C["c5"], 2, 8, dash="8 6"))
    body.append(text(210, 87, "no Thread key here", 19, 700, C["c5"], "middle"))
    return svg(1080, 360, body)


def handshake():
    cx, sx = 200, 880
    flights = [("ClientHello", True, ""),
               ("HelloVerifyRequest (cookie)", False, "the client proves it owns its address"),
               ("ClientHello + cookie", True, ""),
               ("ServerHello, ServerHelloDone", False, ""),
               ("ClientKeyExchange (PSK identity), ChangeCipherSpec, Finished", True, "from here, encrypted"),
               ("ChangeCipherSpec, Finished", False, ""),
               ("CoAP GET /env/temp, as application data", True, "")]
    body = [text(cx, 34, "client", 22, 700, INK, "middle"), text(sx, 34, "S, UDP 5684", 22, 700, INK, "middle")]
    bottom = 70 + len(flights) * 76
    body.append(line(cx, 48, cx, bottom, GRID, 3))
    body.append(line(sx, 48, sx, bottom, GRID, 3))
    y = 80
    for i, (label, right, note) in enumerate(flights):
        col = C[TW] if i >= 4 else INK
        if i == 6:
            col = C[PAL["ASD"]]
        a, b = (cx, sx - 8) if right else (sx, cx + 8)
        body.append(line(a, y, b, y + 16, col, 2, arrow=True))
        body.append(text((cx + sx) / 2, y - 6, label, 19, 700, col, "middle"))
        if note:
            body.append(text((cx + sx) / 2, y + 36, note, 17, 400, MUTED, "middle"))
        y += 76
    return svg(1080, bottom + 10, body)


if __name__ == "__main__":
    for name, fig in [("sec_layers.svg", layers), ("sec_handshake.svg", handshake)]:
        print(save(HERE, name, fig()))
