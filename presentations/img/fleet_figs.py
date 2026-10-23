#!/usr/bin/env python3
"""Figures for the session-7 deck (07_fleet.md).

    python3 fleet_figs.py       # writes fleet_*.svg here

fleet_dashboard.png is a screenshot of tools/fleet's Grafana dashboard on the course
bench (2026-10-23, three ESP32-C6 nodes), taken during the Lab 7 drills.
"""
from pathlib import Path

from figlib import C, INK, MUTED, PAL, T, box, line, save, svg, text

HERE = Path(__file__).resolve().parent
TH, RAID, SCD, UD = PAL["Thread"], PAL["RAID"], PAL["SCD"], PAL["UD"]


def paths():
    body = [text(20, 34, "Labs 3–6: one node, one shell, inside the mesh", 21, 700, MUTED)]
    body.append(box(20, 50, 150, 56, "node", SCD, 20))
    body.append(line(170, 78, 300, 78, MUTED, 3, arrow=True))
    body.append(box(300, 50, 170, 56, "your shell", "gray", 20))
    body.append(text(20, 160, "Lab 7: the whole fleet, out of the mesh", 21, 700, INK))
    hops = [("nodes", SCD, "CoAPS · CBOR"), ("bridge", RAID, "MQTT · JSON"), ("broker", "gray", "subscribe"),
            ("Telegraf", "gray", "points"), ("InfluxDB", "gray", "Flux queries"), ("Grafana", UD, "")]
    x = 20
    for i, (name, col, proto) in enumerate(hops):
        body.append(box(x, 180, 140, 60, name, col, 20))
        if proto:
            body.append(line(x + 140, 210, x + 175, 210, INK, 3, arrow=True))
            body.append(text(x + 157, 268, proto, 16, 400, MUTED, "middle"))
        x += 175
    body.append(text(20, 320, "the mesh speaks CoAP over IPv6; everything right of the bridge is ordinary IT",
                     19, 400, MUTED))
    return svg(1080, 336, body)


def loop():
    steps = [("telemetry", "batt, rssi, up, hsfail"),
             ("baseline", "normal for this node?"),
             ("compare", "outside the band?"),
             ("alert", "a red light, a ticket")]
    body, x = [], 20
    for i, (name, sub) in enumerate(steps):
        col = PAL["Trustworthiness"] if name == "alert" else "c6"
        body.append(box(x, 40, 230, 80, name, col, 22))
        body.append(text(x + 115, 152, sub, 18, 400, INK, "middle"))
        if i < 3:
            body.append(line(x + 232, 80, x + 268, 80, INK, 3, arrow=True))
        x += 270
    body.append(text(20, 200, "the lab's lights are fixed thresholds; a fleet compares each node with its own history",
                     19, 400, MUTED))
    return svg(1100, 216, body)


if __name__ == "__main__":
    for name, fig in [("fleet_paths.svg", paths), ("fleet_loop.svg", loop)]:
        print(save(HERE, name, fig()))
