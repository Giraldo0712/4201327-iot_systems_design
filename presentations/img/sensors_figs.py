#!/usr/bin/env python3
"""Figures for the session-4 deck (04_sensors.md).

    python3 sensors_figs.py       # writes sensors_*.svg here

sensors_terms.svg is illustrative: a synthetic signal, not a measurement. The failure
timelines follow the Lab 4 contract (60 s freshness, 45 s heartbeat) and RFC 7252 §4.8.
"""
import math
import random
from pathlib import Path

from figlib import C, GRID, INK, MUTED, PAL, T, line, poly, rect, save, svg, text

HERE = Path(__file__).resolve().parent
PED, SCD, ASD, TW = PAL["PED"], PAL["SCD"], PAL["ASD"], PAL["Trustworthiness"]


def trust():
    body = [f'<rect x="20" y="20" width="1040" height="300" rx="16" fill="{T[TW]}" fill-opacity="0.6" '
            f'stroke="{C[TW]}" stroke-width="3" stroke-dasharray="12 8"/>']
    doms = [(PED, "PED", ["air or soil", "temperature"]), (SCD, "SCD", ["sensor, reads,", "plausibility checks"]),
            (ASD, "ASD", ["/env/temp contract:", "Max-Age, 5.03"])]
    x = 40
    for col, name, lines in doms:
        body.append(rect(x, 150, 300, 150, T[col], C[col], 3, 12))
        body.append(text(x + 150, 192, name, 26, 700, C[col], "middle"))
        for i, s in enumerate(lines):
            body.append(text(x + 150, 232 + i * 30, s, 21, 400, INK, "middle"))
        x += 340
    body.append(text(40, 60, "Trustworthiness viewpoint (§6.6): questions asked of every domain", 23, 700, C[TW]))
    chars = [("integrity", True), ("availability", True), ("reliability", True), ("resilience", True),
             ("confidentiality", False), ("safety", False), ("compliance", False)]
    x = 40
    for name, today in chars:
        body.append(text(x, 104, name, 20, 700 if today else 400, C[TW] if today else MUTED))
        x += len(name) * 10.5 + 28
    body.append(text(40, 360, "bold: today's four · the rest come with Labs 6 and 8", 19, 400, MUTED))
    return svg(1080, 376, body)


def terms():
    random.seed(4)
    x0, x1, y0, y1 = 80, 1040, 40, 330
    tmax, lo, hi = 120.0, 22.0, 28.0
    def xs(t):
        return x0 + t / tmax * (x1 - x0)
    def ys(v):
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)
    true = lambda t: 24.0 if t < 60 else 24.0 + 2.5 * (1 - math.exp(-(t - 60) / 3))
    sensed = lambda t: 24.0 if t < 60 else 24.0 + 2.5 * (1 - math.exp(-(t - 60) / 14))
    offset, step = 1.0, 0.5
    body = [line(x0, y1, x1, y1, INK, 2), line(x0, y0, x0, y1, INK, 2)]
    for v in range(23, 29):
        body.append(line(x0 - 6, ys(v), x0, ys(v), INK, 2))
        body.append(text(x0 - 12, ys(v) + 7, f"{v}", 18, 400, MUTED, "end"))
    body.append(text(x0 - 12, y0 - 12, "°C", 18, 700, MUTED, "end"))
    body.append(poly([(xs(t / 2), ys(true(t / 2))) for t in range(0, 241)], C[PED], 3, dash="10 6"))
    pts = []
    for k in range(0, 61):
        t = k * 2.0
        v = round((sensed(t) + offset + random.gauss(0, 0.25)) / step) * step
        pts += [(xs(t), ys(v)), (xs(t + 2), ys(v))]
    body.append(poly(pts, C[SCD], 3))
    body.append(text(xs(118), ys(26.5) + 30, "true value", 20, 700, C[PED], "end"))
    body.append(text(xs(4), ys(25.6) - 16, "readings", 20, 700, C[SCD]))
    body.append(line(xs(8), ys(24.0), xs(8), ys(25.0), C["c5"], 3))
    body.append(text(xs(8) + 10, ys(23.4), "accuracy: the offset from the truth", 20, 700, C["c5"]))
    body.append(text(xs(64), ys(23.9), "response time", 20, 700, C["c5"]))
    body.append(line(xs(61), ys(24.5), xs(75), ys(24.5), C["c5"], 3, arrow=True))
    body.append(text(xs(2), ys(27.6), "noise: the wander · resolution: the step", 20, 700, INK))
    body.append(text(x1, y1 + 34, "time (illustrative, not measured)", 18, 400, MUTED, "end"))
    return svg(1080, y1 + 46, body)


def failures():
    x0, x1, tmax = 230, 1050, 100.0
    def xs(t):
        return x0 + t / tmax * (x1 - x0)
    body = []
    def lane(y, title, col, events, spans):
        body.append(text(x0 - 20, y + 8, title, 21, 700, C[col], "end"))
        body.append(line(x0, y, x1, y, GRID, 3))
        for a, b, lab, c in spans:
            body.append(rect(xs(a), y - 16, xs(b) - xs(a), 32, T[c], C[c], 2, 6))
            body.append(text((xs(a) + xs(b)) / 2, y + 7, lab, 20, 400, INK, "middle"))
        for t, lab, c, up in events:
            body.append(line(xs(t), y - 26, xs(t), y + 26, C[c], 4))
            body.append(text(xs(t), y - 36 if up else y + 52, lab, 21, 700, C[c], "middle"))
    lane(90, "sensor dies", SCD,
         [(0, "wire pulled", SCD, True), (6, "Sensor lost", SCD, False), (60, "5.03 to observers", ASD, True)],
         [(8, 58, "GET → 2.05, last value, Max-Age falls", "gray"), (62, 100, "GET → 5.03", ASD)])
    body.append(text(x0 - 20, 122, "node fine", 18, 400, C[SCD], "end"))
    lane(250, "node dies", "c5",
         [(0, "node off", "c5", True), (45, "heartbeat overdue", "c6", True), (62, "", "c5", False)],
         [(2, 43, "silence", "gray"), (62, 93, "CON GET gives up", "c5")])
    body.append(line(x0, 330, x1, 330, INK, 2))
    for t in range(0, 101, 20):
        body.append(line(xs(t), 330, xs(t), 338, INK, 2))
        body.append(text(xs(t), 362, f"{t} s", 18, 400, MUTED, "middle"))
    return svg(1080, 380, body)


if __name__ == "__main__":
    for name, fig in [("sensors_trust.svg", trust), ("sensors_terms.svg", terms), ("sensors_failures.svg", failures)]:
        print(save(HERE, name, fig()))
