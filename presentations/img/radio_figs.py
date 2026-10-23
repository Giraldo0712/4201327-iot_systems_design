#!/usr/bin/env python3
"""Figures for the session-1 deck (01_radio.md).

    python3 radio_figs.py       # writes radio_*.svg here

Airtimes are computed from the PHY rates (802.15.4: 32 µs per byte at 250 kbps;
Wi-Fi 4: 72.2 Mbps, one stream; LoRaWAN: SF12, 125 kHz, CR 4/5, 13 B of MAC overhead).
"""
import math
from pathlib import Path

from figlib import C, GRID, INK, MUTED, PAL, T, line, rect, save, svg, text

HERE = Path(__file__).resolve().parent
TH = PAL["Thread"]


def stacks():
    rows = [("Application", "HTTP / MQTT", "CoAP", "Lab 3"),
            ("Transport", "TCP", "UDP", "Lab 3"),
            ("Network", "IPv4, DHCP from the AP", "IPv6", "Lab 2"),
            ("Adaptation", "—", "6LoWPAN", "Lab 2"),
            ("MAC", "802.11", "802.15.4", "today"),
            ("PHY", "OFDM, 20 MHz channels", "O-QPSK, 2 MHz channels", "today"),
            ("Topology", "star around the AP", "mesh", "Lab 2")]
    body = [text(400, 34, "Lab 0 (built)", 24, 700, MUTED, "middle"),
            text(760, 34, "Labs 1–8 (Thread)", 24, 700, C[TH], "middle")]
    y = 56
    for name, old, new, tag in rows:
        today = tag == "today"
        body.append(text(220, y + 33, name, 22, 700, INK, "end"))
        body.append(rect(240, y, 320, 50, T["gray"], MUTED, 2, 8))
        body.append(text(400, y + 33, old, 21, 400, INK, "middle"))
        body.append(rect(600, y, 320, 50, T[TH], C[TH], 4 if today else 2, 8))
        body.append(text(760, y + 33, new, 21, 700 if today else 400, C[TH] if today else INK, "middle"))
        body.append(text(940, y + 33, tag, 20, 700 if today else 400, C[TH] if today else MUTED))
        y += 58
    return svg(1060, y + 6, body)


def airtime():
    rows = [("Wi-Fi 4", "1500 B at 72 Mbps", 0.2e-3, "gray"),
            ("802.15.4", "127 B at 250 kbps", 133 * 32e-6, TH),
            ("LoRaWAN SF12", "51 B at ~250 bps", 2.79, "gray")]
    x0, x1, lo, hi = 260, 1040, 1e-4, 10.0
    def xs(t):
        return x0 + (math.log10(t) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (x1 - x0)
    body, y = [], 20
    for name, sub, t, col in rows:
        body.append(text(x0 - 16, y + 26, name, 22, 700, C[col], "end"))
        body.append(text(x0 - 16, y + 50, sub, 17, 400, MUTED, "end"))
        body.append(rect(x0, y + 8, xs(t) - x0, 40, T[col], C[col], 2, 6))
        label = f"{t * 1e3:.1f} ms" if t < 1 else f"{t:.1f} s"
        body.append(text(xs(t) + 12, y + 36, label, 22, 700, C[col]))
        y += 76
    body.append(line(x0, y + 4, x1, y + 4, INK, 2))
    for i, lab in enumerate(["0.1 ms", "1 ms", "10 ms", "100 ms", "1 s", "10 s"]):
        x = xs(lo * 10 ** i)
        body.append(line(x, 14, x, y + 4, GRID, 1, dash="4 4"))
        body.append(line(x, y + 4, x, y + 12, INK, 2))
        body.append(text(x, y + 36, lab, 18, 400, MUTED, "middle"))
    body.append(text(x1, y + 66, "time the transmitter is on, for one frame (log scale)", 18, 400, MUTED, "end"))
    return svg(1080, y + 80, body)


def band():
    f0, f1, x0, x1 = 2400, 2485, 60, 1040
    def xs(f):
        return x0 + (f - f0) / (f1 - f0) * (x1 - x0)
    body = []
    for ch, fc in ((1, 2412), (6, 2437), (11, 2462)):
        body.append(rect(xs(fc - 10), 40, xs(fc + 10) - xs(fc - 10), 150, T["gray"], MUTED, 2, 6))
        body.append(text(xs(fc), 70, f"Wi-Fi {ch}", 22, 700, MUTED, "middle"))
        body.append(text(xs(fc), 96, "20 MHz", 17, 400, MUTED, "middle"))
    for k in range(11, 27):
        fc = 2405 + 5 * (k - 11)
        body.append(rect(xs(fc - 1), 130, xs(fc + 1) - xs(fc - 1), 90, T[TH], C[TH], 2, 2))
        body.append(text(xs(fc), 248, str(k), 18, 700, C[TH], "middle"))
    body.append(line(x0, 220, x1, 220, INK, 2))
    for f in range(2400, 2486, 20):
        body.append(line(xs(f), 220, xs(f), 228, INK, 2))
        body.append(text(xs(f), 290, f"{f}", 17, 400, MUTED, "middle"))
    body.append(text(x1, 316, "MHz · 802.15.4 channel k is centred at 2405 + 5·(k − 11) MHz, 2 MHz wide",
                     17, 400, MUTED, "end"))
    return svg(1080, 330, body)


def frame():
    x0, w, scale = 40, 1000, 1000 / 127
    parts = [("MHR", 9, "~9 B", "gray"), ("security", 14, "0–14 B", "gray"),
             ("payload: everything above the MAC", 102, "≤ 102 B", TH), ("FCS", 2, "2 B", "gray")]
    body = [text(x0, 30, "One 802.15.4 frame: 127 bytes", 24, 700, INK)]
    x = x0
    for name, n, size, col in parts:
        ww = n * scale
        body.append(rect(x, 50, ww, 70, T[col], C[col], 2, 4))
        if ww > 50:
            body.append(text(x + ww / 2, 82, name, 20, 700, C[col], "middle"))
        body.append(text(x + ww / 2, 108 if ww > 50 else 145, size, 18, 400, INK, "middle"))
        x += ww
    px = x0 + 23 * scale
    body.append(line(px, 160, px + 40 * scale, 160, C["c5"], 4))
    body.append(text(px, 192, "an uncompressed IPv6 header alone: 40 B", 20, 700, C["c5"]))
    body.append(text(px, 222, "then UDP (8 B), CoAP, and your data", 20, 400, INK))
    body.append(text(x0, 270, "Wi-Fi carries up to 1500 B of IP packet per frame: Lab 0 never counted header bytes.",
                     19, 400, MUTED))
    return svg(1080, 290, body)


def boundary():
    ped, scd = PAL["PED"], PAL["SCD"]
    body = [rect(20, 20, 470, 300, T[ped], C[ped], 3, 14),
            text(40, 60, "PED · Physical Entity Domain", 21, 700, C[ped]),
            rect(590, 20, 470, 300, T[scd], C[scd], 3, 14),
            text(610, 60, "SCD · Sensing & Controlling Domain", 21, 700, C[scd])]
    for i, s in enumerate(["radio waves in the air", "Wi-Fi and microwave interference",
                           "distance, walls, vegetation"]):
        body.append(text(40, 115 + i * 44, "· " + s, 21, 400, INK))
    for i, s in enumerate(["802.15.4 radio", "ESP32-C6: MAC, OpenThread", "flash: the network dataset"]):
        body.append(text(610, 115 + i * 44, "· " + s, 21, 400, INK))
    body.append(rect(498, 110, 84, 120, "#ffffff", INK, 3, 8))
    body.append(text(540, 166, "antenna", 16, 700, INK, "middle"))
    body.append(text(540, 196, "⇄", 30, 700, INK, "middle"))
    body.append(text(540, 360, "the boundary: the antenna turns bits into waves and back", 21, 700, INK, "middle"))
    return svg(1080, 380, body)


if __name__ == "__main__":
    for name, fig in [("radio_stacks.svg", stacks), ("radio_airtime.svg", airtime), ("radio_band.svg", band),
                      ("radio_frame.svg", frame), ("radio_boundary.svg", boundary)]:
        print(save(HERE, name, fig()))
