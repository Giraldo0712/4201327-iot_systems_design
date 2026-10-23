#!/usr/bin/env python3
"""Writes dashboards/soilsense-fleet.json, the Lab 7 Grafana dashboard.

    python3 make_dashboard.py

Grafana reads the JSON at startup (provisioning/dashboards). Edit this script, not
the JSON, then restart Grafana: docker compose restart grafana.
"""
import json
from pathlib import Path

DS = {"type": "influxdb", "uid": "soilsense-influx"}
SILENT_S = 150   # a node is "silent" after this long without any report
LOW_BATT_MV = 3000
WEAK_RSSI_DBM = -90


def q(flux):
    return [{"refId": "A", "datasource": DS, "query": flux}]


def thresholds(*steps):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in steps]}


AGE = '''from(bucket: "soilsense")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "env" or r._measurement == "health")
  |> group(columns: ["node"])
  |> sort(columns: ["_time"])
  |> last()
  |> map(fn: (r) => ({_time: r._time, node: r.node, _field: "age",
                      _value: float(v: int(v: now()) - int(v: r._time)) / 1000000000.0}))'''


def last_per_node(field):
    return f'''from(bucket: "soilsense")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "health" and r._field == "{field}")
  |> group(columns: ["node"])
  |> last()'''


def series(measurement, field):
    return f'''from(bucket: "soilsense")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "{measurement}" and r._field == "{field}")
  |> group(columns: ["node"])
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)'''


TABLE = '''health = from(bucket: "soilsense")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "health")
  |> group(columns: ["node", "_field"])
  |> last()
  |> keep(columns: ["node", "_field", "_value"])
age = ''' + AGE.replace("_time: r._time, ", "") + '''
union(tables: [health, age])
  |> group()
  |> pivot(rowKey: ["node"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["node", "age", "batt", "rssi", "up", "hsfail"])'''

NODE_NAME = {"displayName": "${__field.labels.node}"}
MV = "suffix: mV"


def stat(title, desc, flux, x, w, unit, th):
    return {"type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": 0, "w": w, "h": 5}, "targets": q(flux),
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background", "textMode": "value_and_name", "graphMode": "none",
                        "orientation": "horizontal"},
            "fieldConfig": {"defaults": {"unit": unit, "decimals": 0, "thresholds": th,
                                         "color": {"mode": "thresholds"}, **NODE_NAME}, "overrides": []}}


def timeseries(title, desc, measurement, field, y, x, w, unit, lo, hi, th=None):
    return {"type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": 8}, "targets": q(series(measurement, field)),
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
            "fieldConfig": {"defaults": {"unit": unit, "min": lo, "max": hi, **NODE_NAME,
                                         "custom": {"lineWidth": 2, "showPoints": "always", "pointSize": 4,
                                                    "thresholdsStyle": {"mode": "line+area" if th else "off"}},
                                         "thresholds": th or thresholds(("green", None))}, "overrides": []}}


def column(name, th, unit):
    props = [{"id": "unit", "value": unit}]
    if th:
        props += [{"id": "custom.cellOptions", "value": {"type": "color-background"}},
                  {"id": "thresholds", "value": th}]
    return {"matcher": {"id": "byName", "options": name}, "properties": props}


panels = [
    stat("Seconds since the last report",
         f"Red when a node has sent nothing for {SILENT_S} s: dead battery, crash, out of range, or removed.",
         AGE, 0, 12, "s", thresholds(("green", None), ("red", SILENT_S))),
    stat("Failed DTLS handshakes",
         "Handshakes the node refused since it booted: a wrong key in the field, or someone trying keys.",
         last_per_node("hsfail"), 12, 6, "none", thresholds(("green", None), ("red", 1))),
    stat("Uptime", "Time since boot. A drop means the node rebooted.",
         last_per_node("up"), 18, 6, "s", thresholds(("blue", None))),
    timeseries("Soil temperature", "/env/temp from every node.", "env", "t", 5, 0, 24, "celsius", None, None),
    timeseries("Battery", f"Simulated on the lab boards. Below {LOW_BATT_MV} mV: plan a battery swap.",
               "health", "batt", 13, 0, 12, MV, 2700, 3400,
               thresholds(("red", None), ("transparent", LOW_BATT_MV))),
    timeseries("Link RSSI", f"Average RSSI of the link each node depends on. Below {WEAK_RSSI_DBM} dBm the link is at risk.",
               "health", "rssi", 13, 12, 12, "dBm", -100, -10,
               thresholds(("red", None), ("transparent", WEAK_RSSI_DBM))),
    {"type": "table", "title": "Fleet", "datasource": DS,
     "description": "One row per node: its latest health report, and how long ago anything arrived from it.",
     "gridPos": {"x": 0, "y": 21, "w": 24, "h": 7}, "targets": q(TABLE),
     "transformations": [{"id": "organize", "options": {
         "indexByName": {"node": 0, "age": 1, "batt": 2, "rssi": 3, "hsfail": 4, "up": 5},
         "renameByName": {"age": "last report", "batt": "battery", "rssi": "link RSSI",
                          "hsfail": "failed handshakes", "up": "uptime"}}}],
     "options": {"showHeader": True},
     "fieldConfig": {"defaults": {"decimals": 0, "custom": {"align": "center"}},
                     "overrides": [column("last report", thresholds(("green", None), ("red", SILENT_S)), "s"),
                                   column("battery", thresholds(("red", None), ("green", LOW_BATT_MV)), MV),
                                   column("link RSSI", thresholds(("red", None), ("green", WEAK_RSSI_DBM)), "dBm"),
                                   column("failed handshakes", thresholds(("green", None), ("red", 1)), "none"),
                                   column("uptime", None, "s")]}},
]

dashboard = {"uid": "soilsense-fleet", "title": "SoilSense fleet", "tags": ["soilsense"],
             "timezone": "browser", "refresh": "10s", "time": {"from": "now-30m", "to": "now"},
             "schemaVersion": 39, "version": 1, "editable": True, "panels": panels}

out = Path(__file__).resolve().parent / "dashboards" / "soilsense-fleet.json"
out.write_text(json.dumps(dashboard, indent=2) + "\n")
print(out.name)
