#!/usr/bin/env python3
"""Figures for the session-2 deck (02_mesh.md).

    python3 mesh_figs.py       # writes mesh_*.svg here

Header fields from RFC 8200 and RFC 6282; link costs from the Thread specification
as OpenThread implements them.
"""
from pathlib import Path

from figlib import C, INK, MUTED, PAL, T, line, rect, save, svg, text

HERE = Path(__file__).resolve().parent
TH = PAL["Thread"]


def iphc():
    fields = [("ver · class · flow", 4, "always 6 · usually 0 · usually 0"),
              ("length", 2, "from the frame length"),
              ("next", 1, "UDP: one flag bit"),
              ("hops", 1, "1, 64 or 255: 2 bits"),
              ("source address", 16, "prefix from context; IID from the MAC header"),
              ("destination address", 16, "prefix from context; IID from the MAC header")]
    x0, scale = 40, 1000 / 40
    body = [text(x0, 30, "Uncompressed IPv6 header: 40 bytes", 24, 700, INK)]
    x = x0
    for name, n, why in fields:
        w = n * scale
        body.append(rect(x, 46, w, 64, "#ffffff", MUTED, 2, 4))
        if w > 150:
            body.append(text(x + w / 2, 76, name, 19, 700, INK, "middle"))
        if w >= 50:
            body.append(text(x + w / 2, 100 if w > 150 else 84, f"{n} B", 17, 400, MUTED, "middle"))
        x += w
    body.append(text(x0, 148, "what the receiver can rebuild instead:", 21, 400, MUTED))
    y = 180
    for name, n, why in fields:
        body.append(text(x0 + 20, y, f"{name}:", 21, 700, INK))
        body.append(text(x0 + 280, y, why, 21, 400, INK))
        y += 34
    body.append(rect(x0, y + 4, 2 * scale, 64, T[TH], C[TH], 3, 4))
    body.append(text(x0 + 2 * scale + 20, y + 44, "IPHC (RFC 6282): as little as 2 bytes", 24, 700, C[TH]))
    body.append(text(x0 + 2 * scale + 20, y + 72,
                     "an interface ID the receiver can't rebuild still travels: 8 B per address", 19, 400, MUTED))
    return svg(1080, y + 92, body)


def addresses():
    rows = [("link-local", "fe80:0:0:0", "built from the extended MAC address", "gray", "one radio hop"),
            ("RLOC", "mesh-local prefix", "0:ff:fe00 : router ID (6 bits) + child ID", TH, "where the node is attached"),
            ("ML-EID", "mesh-local prefix", "random, chosen once", TH, "who the node is")]
    body = [text(250, 30, "64-bit prefix", 20, 700, MUTED, "middle"),
            text(700, 30, "64-bit interface ID (IID)", 20, 700, MUTED, "middle")]
    y = 46
    for name, prefix, iid, col, job in rows:
        body.append(text(20, y + 40, name, 22, 700, C[col]))
        body.append(rect(140, y, 220, 60, T["gray"], MUTED, 2, 6))
        body.append(text(250, y + 38, prefix, 19, 400, INK, "middle"))
        body.append(rect(370, y, 660, 60, T[col], C[col], 2, 6))
        body.append(text(700, y + 38, iid, 19, 400, INK, "middle"))
        body.append(text(700, y + 86, job, 18, 700, C[col], "middle"))
        y += 108
    return svg(1060, y, body)


def costs():
    pos = {"A": (140, 300), "B": (420, 80), "C": (700, 300)}
    body = []
    def edge(a, b, label, col, sw, dash=""):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        body.append(line(x1, y1, x2, y2, col, sw, dash))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if a == "A" and b == "C":
            body.append(text(mx, my + 40, label, 20, 700, col, "middle"))
        elif a == "A":
            body.append(text(mx - 30, my - 10, label, 20, 700, col, "end"))
        else:
            body.append(text(mx + 30, my - 10, label, 20, 700, col))
    edge("A", "B", "LQ 3 · cost 1", C[TH], 6)
    edge("B", "C", "LQ 3 · cost 1", C[TH], 6)
    edge("A", "C", "LQ 1 · cost 4", MUTED, 3, "10 8")
    for n, (x, y) in pos.items():
        body.append(f'<circle cx="{x}" cy="{y}" r="42" fill="{T[TH]}" stroke="{C[TH]}" stroke-width="3"/>')
        body.append(text(x, y + 10, n, 30, 700, C[TH], "middle"))
    tx = 820
    body.append(text(tx, 70, "link margin → LQ → cost", 20, 700, INK))
    for i, (m, lq, c) in enumerate([("> 20 dB", 3, 1), ("> 10 dB", 2, 2), ("> 2 dB", 1, 4), ("less", 0, "no link")]):
        body.append(text(tx, 110 + i * 34, f"{m}  →  LQ {lq}  →  {c}", 19, 400, INK))
    body.append(text(tx, 270, "route cost = sum of links", 19, 700, INK))
    body.append(text(tx, 300, "A → B → C: 1 + 1 = 2", 19, 700, C[TH]))
    body.append(text(tx, 330, "A → C direct: 4", 19, 400, MUTED))
    return svg(1100, 370, body)


if __name__ == "__main__":
    for name, fig in [("mesh_iphc.svg", iphc), ("mesh_addresses.svg", addresses), ("mesh_costs.svg", costs)]:
        print(save(HERE, name, fig()))
