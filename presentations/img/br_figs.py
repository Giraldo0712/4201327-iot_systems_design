#!/usr/bin/env python3
"""Figures for the session-5 deck (05_border_router.md).

    python3 br_figs.py       # writes br_*.svg here

Networks after ISO/IEC 30141:2024 Table A.4 / Figure A.6; the two-board OTBR is
firmware/lab5_border_router (ESP32-S3) and firmware/lab5_rcp (ESP32-C6).
"""
from pathlib import Path

from figlib import C, INK, MUTED, PAL, T, box, line, poly, rect, save, svg, text

HERE = Path(__file__).resolve().parent
TH, SCD, UD = PAL["Thread"], PAL["SCD"], PAL["UD"]


def networks():
    nets = [("Proximity", "Thread mesh", TH), ("Access", "Wi-Fi hotspot", "gray"),
            ("Services", "cloud or laptop", "gray"), ("User", "carrier network", "gray")]
    body, w, gap = [], 245, 15
    for i, (name, sub, col) in enumerate(nets):
        x = 20 + i * (w + gap)
        body.append(rect(x, 40, w, 260, T[col], C[col], 2, 12))
        body.append(text(x + w / 2, 76, name, 24, 700, C[col], "middle"))
        body.append(text(x + w / 2, 104, sub, 19, 400, INK, "middle"))
    for n, x in (("S", 60), ("C", 150)):
        body.append(f'<circle cx="{x}" cy="230" r="28" fill="#ffffff" stroke="{C[TH]}" stroke-width="3"/>')
        body.append(text(x, 238, n, 22, 700, C[TH], "middle"))
    body.append(box(192, 140, 160, 56, "OTBR", SCD, 24))
    body.append(box(320 + 40, 210, 165, 50, "hotspot", "gray", 19))
    body.append(box(540 + 40, 210, 165, 50, "dashboard", "gray", 19))
    body.append(box(800 + 40, 210, 165, 50, "phone", UD, 19))
    body.append(poly([(80, 204), (200, 175)], C[TH], 3, arrow=True))
    body.append(poly([(352, 168), (440, 168), (440, 204)], INK, 3, arrow=True))
    body.append(line(527, 235, 575, 235, INK, 3, arrow=True))
    body.append(line(747, 235, 835, 235, INK, 3, arrow=True))
    body.append(text(540, 340, "ISO/IEC 30141 Table A.4: one path from S to Daniela's phone crosses all four",
                     20, 400, MUTED, "middle"))
    return svg(1080, 356, body)


def two_boards():
    body = [rect(260, 40, 380, 280, T[SCD], C[SCD], 3, 14),
            text(450, 78, "ESP32-S3 host", 24, 700, C[SCD], "middle")]
    for i, s in enumerate(["OpenThread Border Router", "IPv6 routing, NAT64", "Router Advertisements",
                           "Wi-Fi driver", "the ot shell"]):
        body.append(text(290, 120 + i * 38, "· " + s, 20, 400, INK))
    body += [rect(760, 40, 300, 280, T[TH], C[TH], 3, 14),
             text(910, 78, "ESP32-C6 RCP", 24, 700, C[TH], "middle")]
    for i, s in enumerate(["802.15.4 PHY", "802.15.4 MAC", "no IP stack", "no application"]):
        body.append(text(790, 120 + i * 38, "· " + s, 20, 400, INK))
    body.append(line(645, 180, 755, 180, INK, 3, arrow=True))
    body.append(line(755, 200, 645, 200, INK, 3, arrow=True))
    body.append(text(700, 160, "UART", 18, 700, INK, "middle"))
    body.append(text(700, 230, "Spinel", 18, 700, INK, "middle"))
    body.append(text(700, 254, "460800", 16, 400, MUTED, "middle"))
    body.append(box(20, 150, 160, 60, "Wi-Fi AP", "gray", 21))
    body.append(line(185, 180, 255, 180, INK, 3, arrow=True))
    body.append(text(910, 352, "to the mesh: 802.15.4 frames", 19, 400, MUTED, "middle"))
    body.append(text(100, 240, "IPv6, IPv4", 18, 400, MUTED, "middle"))
    return svg(1080, 370, body)


def prefix():
    body = [box(430, 150, 220, 70, "OTBR", SCD, 26)]
    body.append(rect(20, 40, 380, 290, T[TH], C[TH], 2, 12))
    body.append(text(210, 76, "Thread side", 23, 700, C[TH], "middle"))
    for i, s in enumerate(["Network Data: the OMR prefix,", "flags paros (SLAAC on)", "",
                           "each node builds its own", "OMR address from it (SLAAC)"]):
        body.append(text(40, 120 + i * 34, s, 19, 700 if i in (0, 3) else 400, INK))
    body.append(rect(690, 40, 370, 290, T["gray"], MUTED, 2, 12))
    body.append(text(875, 76, "Wi-Fi side", 23, 700, MUTED, "middle"))
    for i, s in enumerate(["Router Advertisement with a", "Route Information Option", "(RFC 4191)", "",
                           "laptop: OMR prefix", "via the OTBR"]):
        body.append(text(710, 120 + i * 34, s, 19, 700 if i in (0, 4) else 400, INK))
    body.append(line(425, 185, 405, 185, C[TH], 4, arrow=True))
    body.append(line(655, 185, 685, 185, INK, 4, arrow=True))
    body.append(text(540, 270, "a router, not a proxy:", 20, 700, C[SCD], "middle"))
    body.append(text(540, 298, "it forwards IPv6 datagrams", 19, 400, INK, "middle"))
    return svg(1080, 345, body)


def bytes_():
    scale, right = 9.0, 1060
    rows = [("in the mesh", [("802.15.4", 12, "gray"), ("IPHC+UDP", 8, TH), ("CoAP", 12, "c3"), ("CBOR", 6, "c3")]),
            ("on Wi-Fi", [("802.11", 30, "gray"), ("IPv6", 40, "gray"), ("UDP", 8, "gray"), ("CoAP", 12, "c3"),
                          ("CBOR", 6, "c3")])]
    body, y = [], 40
    for name, parts in rows:
        body.append(text(20, y - 10, name, 21, 700, INK))
        x = right - sum(n for _, n, _ in parts) * scale
        for lab, n, col in parts:
            w = n * scale
            body.append(rect(x, y, w, 56, T[col], C[col], 2, 4))
            if w >= 100:
                body.append(text(x + w / 2, y + 35, lab, 18, 700, C[col], "middle"))
            else:
                body.append(text(x + w / 2, y + 82, lab, 18, 700, C[col], "middle"))
            x += w
        y += 130
    cx = right - 18 * scale
    body.append(f'<rect x="{cx - 6:.1f}" y="28" width="{18 * scale + 12:.1f}" height="200" rx="8" fill="none" '
                f'stroke="{C["c3"]}" stroke-width="3" stroke-dasharray="10 6"/>')
    body.append(text(right, 280, "the CoAP message and its 6 bytes of CBOR are identical on both sides",
                     20, 700, C["c3"], "end"))
    body.append(text(right, 308, "sizes approximate", 17, 400, MUTED, "end"))
    return svg(1080, 320, body)


if __name__ == "__main__":
    for name, fig in [("br_networks.svg", networks), ("br_two_boards.svg", two_boards), ("br_prefix.svg", prefix),
                      ("br_bytes.svg", bytes_)]:
        print(save(HERE, name, fig()))
