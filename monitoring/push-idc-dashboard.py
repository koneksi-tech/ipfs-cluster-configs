#!/usr/bin/env python3
"""Build and push the IDC IPFS Cluster monitoring dashboard to Grafana.
   Covers node1–node4 only. node5 is the load balancer — excluded.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER = "admin"
PASS = "ar@dm1n"
IF   = "$nodename"


# ── helpers ───────────────────────────────────────────────────────────────────

def ds():
    return {"type": "prometheus", "uid": "${datasource}"}

def target(expr, legend="{{nodename}}", ref="A"):
    return {"datasource": ds(), "editorMode": "code", "expr": expr,
            "instant": False, "legendFormat": legend, "range": True, "refId": ref}

def target_instant(expr, legend="{{nodename}}", ref="A"):
    """Use for stat panels — one current value per node."""
    return {"datasource": ds(), "editorMode": "code", "expr": expr,
            "instant": True, "legendFormat": legend, "range": False, "refId": ref}

def timeseries(id, title, x, y, w, h, targets, unit="short", fill=10):
    return {
        "datasource": ds(),
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": fill,
                    "lineInterpolation": "smooth", "lineWidth": 2,
                    "showPoints": "never", "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                    "thresholdsStyle": {"mode": "off"}
                },
                "unit": unit
            },
            "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "legend": {"calcs": ["mean", "max", "lastNotNull"],
                       "displayMode": "table", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"}
        },
        "targets": targets,
        "title": title,
        "type": "timeseries"
    }

def stat(id, title, x, y, w, h, targets, unit="short", thresholds=None, color_mode="background", graph_mode="area"):
    if thresholds is None:
        thresholds = [{"color": "green", "value": None}]
    return {
        "datasource": ds(),
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": thresholds},
                "unit": unit
            },
            "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "colorMode": color_mode, "graphMode": graph_mode,
            "justifyMode": "auto", "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto"
        },
        "targets": targets,
        "title": title,
        "type": "stat"
    }

def bargauge(id, title, x, y, w, h, targets, unit="bytes"):
    return {
        "datasource": ds(),
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {
                    "mode": "percentage",
                    "steps": [
                        {"color": "green",  "value": None},
                        {"color": "yellow", "value": 70},
                        {"color": "red",    "value": 90}
                    ]
                },
                "unit": unit
            },
            "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "displayMode": "lcd",
            "minVizHeight": 10, "minVizWidth": 0,
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "showUnfilled": True
        },
        "targets": targets,
        "title": title,
        "type": "bargauge"
    }

def row_panel(id, title, y):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": id, "title": title, "type": "row"}


# ── panels ────────────────────────────────────────────────────────────────────

p = []
i = 1

# ── Row: Overview ─────────────────────────────────────────────────────────────
p.append(row_panel(i, "Overview", 0)); i += 1

# h=8 gives enough height to display all 4 nodes — h=4 only fits 2
p.append(stat(i, "CPU Usage %", 0, 1, 6, 8,
    [target(f'100 - (avg by (nodename) (irate(node_cpu_seconds_total{{mode="idle",nodename=~"{IF}"}}[5m])) * 100)')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Memory Usage %", 6, 1, 6, 8,
    [target(f'(1 - node_memory_MemAvailable_bytes{{nodename=~"{IF}"}} / node_memory_MemTotal_bytes{{nodename=~"{IF}"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Data Disk Usage % (/data)", 12, 1, 6, 8,
    [target(f'(1 - node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}} / node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 75}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Uptime", 18, 1, 6, 8,
    [target(f'time() - node_boot_time_seconds{{nodename=~"{IF}"}}')],
    unit="dtdhms", color_mode="value", graph_mode="none",
    thresholds=[{"color": "green", "value": None}]
)); i += 1

# ── Row: CPU ──────────────────────────────────────────────────────────────────
p.append(row_panel(i, "CPU", 9)); i += 1

p.append(timeseries(i, "CPU Usage %", 0, 10, 24, 8,
    [target(f'100 - (avg by (nodename) (irate(node_cpu_seconds_total{{mode="idle",nodename=~"{IF}"}}[5m])) * 100)')],
    unit="percent"
)); i += 1

# ── Row: Memory ───────────────────────────────────────────────────────────────
p.append(row_panel(i, "Memory", 18)); i += 1

p.append(timeseries(i, "Memory Usage", 0, 19, 12, 8,
    [
        target(f'node_memory_MemTotal_bytes{{nodename=~"{IF}"}} - node_memory_MemAvailable_bytes{{nodename=~"{IF}"}}', "{{nodename}} used",      "A"),
        target(f'node_memory_MemAvailable_bytes{{nodename=~"{IF}"}}',                                                  "{{nodename}} available", "B"),
    ],
    unit="bytes"
)); i += 1

p.append(bargauge(i, "Memory Available Now", 12, 19, 12, 8,
    [target_instant(f'node_memory_MemAvailable_bytes{{nodename=~"{IF}"}}', "{{nodename}}")],
    unit="bytes"
)); i += 1

# ── Row: Data Storage /data ───────────────────────────────────────────────────
p.append(row_panel(i, "Data Storage — /data", 27)); i += 1

p.append(stat(i, "Data Disk Used %", 0, 28, 6, 8,
    [target(f'(1 - node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}} / node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Data Disk Free", 6, 28, 6, 8,
    [target(f'node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}', "{{nodename}}")],
    unit="bytes", color_mode="value", graph_mode="none",
    thresholds=[{"color": "red", "value": None}, {"color": "yellow", "value": 1099511627776}, {"color": "green", "value": 5497558138880}]
)); i += 1

p.append(stat(i, "Data Disk Used", 12, 28, 6, 8,
    [target(f'node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}} - node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}', "{{nodename}}")],
    unit="bytes", color_mode="background", graph_mode="none",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 54975581388800}, {"color": "red", "value": 109951162777600}]
)); i += 1

p.append(stat(i, "Data Disk Total", 18, 28, 6, 8,
    [target(f'node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}}', "{{nodename}}")],
    unit="bytes", color_mode="value", graph_mode="none",
    thresholds=[{"color": "green", "value": None}]
)); i += 1

p.append(bargauge(i, "Data Disk — Used vs Free per Node (/data)", 0, 36, 14, 8,
    [
        target_instant(f'node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}} - node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}',
               "{{nodename}} used", "A"),
        target_instant(f'node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}',
               "{{nodename}} free", "B"),
    ],
    unit="bytes"
)); i += 1

p.append(timeseries(i, "Data Disk Usage Over Time (/data)", 14, 36, 10, 8,
    [
        target(f'node_filesystem_size_bytes{{nodename=~"{IF}",mountpoint="/data"}} - node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}',
               "{{nodename}} used", "A"),
        target(f'node_filesystem_avail_bytes{{nodename=~"{IF}",mountpoint="/data"}}',
               "{{nodename}} free", "B"),
    ],
    unit="bytes"
)); i += 1

# ── Row: Disk I/O ─────────────────────────────────────────────────────────────
p.append(row_panel(i, "Disk I/O", 44)); i += 1

p.append(timeseries(i, "Disk I/O Throughput", 0, 45, 24, 8,
    [
        target(f'irate(node_disk_read_bytes_total{{nodename=~"{IF}"}}[5m])',    "{{nodename}} read",  "A"),
        target(f'irate(node_disk_written_bytes_total{{nodename=~"{IF}"}}[5m])', "{{nodename}} write", "B"),
    ],
    unit="Bps"
)); i += 1

# ── Row: Network ──────────────────────────────────────────────────────────────
p.append(row_panel(i, "Network", 53)); i += 1

p.append(timeseries(i, "Network Receive Bandwidth", 0, 54, 12, 8,
    [target(f'irate(node_network_receive_bytes_total{{nodename=~"{IF}",device!="lo"}}[5m]) * 8', "{{nodename}} {{device}}")],
    unit="bps"
)); i += 1

p.append(timeseries(i, "Network Transmit Bandwidth", 12, 54, 12, 8,
    [target(f'irate(node_network_transmit_bytes_total{{nodename=~"{IF}",device!="lo"}}[5m]) * 8', "{{nodename}} {{device}}")],
    unit="bps"
)); i += 1

p.append(timeseries(i, "Network Errors & Drops", 0, 62, 24, 6,
    [
        target(f'irate(node_network_receive_errs_total{{nodename=~"{IF}",device!="lo"}}[5m])',  "{{nodename}} {{device}} rx_err",  "A"),
        target(f'irate(node_network_receive_drop_total{{nodename=~"{IF}",device!="lo"}}[5m])',  "{{nodename}} {{device}} rx_drop", "B"),
        target(f'irate(node_network_transmit_errs_total{{nodename=~"{IF}",device!="lo"}}[5m])', "{{nodename}} {{device}} tx_err",  "C"),
        target(f'irate(node_network_transmit_drop_total{{nodename=~"{IF}",device!="lo"}}[5m])', "{{nodename}} {{device}} tx_drop", "D"),
    ],
    unit="pps", fill=0
)); i += 1

# ── Row: System ───────────────────────────────────────────────────────────────
p.append(row_panel(i, "System", 68)); i += 1

p.append(timeseries(i, "System Load Average", 0, 69, 16, 8,
    [
        target(f'node_load1{{nodename=~"{IF}"}}',  "{{nodename}} 1m",  "A"),
        target(f'node_load5{{nodename=~"{IF}"}}',  "{{nodename}} 5m",  "B"),
        target(f'node_load15{{nodename=~"{IF}"}}', "{{nodename}} 15m", "C"),
    ]
)); i += 1

p.append(stat(i, "Open File Descriptors", 16, 69, 8, 8,
    [target(f'node_filefd_allocated{{nodename=~"{IF}"}}')],
    unit="short", color_mode="background",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50000}, {"color": "red", "value": 100000}]
)); i += 1


# ── dashboard ─────────────────────────────────────────────────────────────────

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": p,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["idc", "ipfs", "cluster"],
    "templating": {
        "list": [
            {
                "current": {"selected": False, "text": "Prometheus", "value": "Prometheus"},
                "hide": 0, "includeAll": False, "multi": False,
                "name": "datasource", "options": [], "query": "prometheus",
                "refresh": 1, "type": "datasource"
            },
            {
                "current": {"selected": True, "text": "All", "value": "$__all"},
                "datasource": {"type": "prometheus", "uid": "${datasource}"},
                "definition": 'label_values(node_cpu_seconds_total{job="ipfs-cluster-nodes",cluster="idc",nodename!="idc-node-5-lb"}, nodename)',
                "hide": 0, "includeAll": True, "multi": True,
                "name": "nodename",
                "query": {
                    "query": 'label_values(node_cpu_seconds_total{job="ipfs-cluster-nodes",cluster="idc",nodename!="idc-node-5-lb"}, nodename)',
                    "refId": "StandardVariableQuery"
                },
                "refresh": 2,
                "regex": "",
                "sort": 1,
                "type": "query"
            }
        ]
    },
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "IDC IPFS Cluster — Node Monitoring (node1–node4)",
    "uid": "idc-ipfs-cluster",
    "version": 0
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})

auth = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=payload.encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    method="POST"
)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        result = json.loads(resp.read())
        print(f"✓ Dashboard pushed")
        print(f"  URL : {GRAFANA_URL}{result.get('url', '')}")
        print(f"  UID : {result.get('uid', '')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
