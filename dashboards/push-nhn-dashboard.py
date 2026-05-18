#!/usr/bin/env python3
"""Build and push the NHN IPFS Cluster monitoring dashboard to Grafana."""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER = "admin"
PASS = "ar@dm1n"
IF = "$instance"   # instance filter variable placeholder


# ── helpers ──────────────────────────────────────────────────────────────────

def ds():
    return {"type": "prometheus", "uid": "${datasource}"}

def target(expr, legend="{{instance}}", ref="A"):
    return {"datasource": ds(), "editorMode": "code", "expr": expr,
            "instant": False, "legendFormat": legend, "range": True, "refId": ref}

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
                        {"color": "green", "value": None},
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

def row_panel(id, title, y, collapsed=False):
    return {"collapsed": collapsed, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": id, "title": title, "type": "row"}


# ── panels ───────────────────────────────────────────────────────────────────

p = []
i = 1

# ── Row: Overview ────────────────────────────────────────────────────────────
p.append(row_panel(i, "Overview", 0)); i += 1

p.append(stat(i, "CPU Usage %", 0, 1, 6, 4,
    [target(f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance=~"{IF}"}}[5m])) * 100)')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Memory Usage %", 6, 1, 6, 4,
    [target(f'(1 - node_memory_MemAvailable_bytes{{instance=~"{IF}"}} / node_memory_MemTotal_bytes{{instance=~"{IF}"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 80}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Disk Usage % (root)", 12, 1, 6, 4,
    [target(f'(1 - node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/",fstype!="tmpfs"}} / node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/",fstype!="tmpfs"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 75}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Uptime", 18, 1, 6, 4,
    [target(f'time() - node_boot_time_seconds{{instance=~"{IF}"}}')],
    unit="dtdhms", color_mode="value", graph_mode="none",
    thresholds=[{"color": "green", "value": None}]
)); i += 1

# ── Row: CPU ─────────────────────────────────────────────────────────────────
p.append(row_panel(i, "CPU", 5)); i += 1

p.append(timeseries(i, "CPU Usage %", 0, 6, 24, 8,
    [target(f'100 - (avg by (instance) (irate(node_cpu_seconds_total{{mode="idle",instance=~"{IF}"}}[5m])) * 100)')],
    unit="percent"
)); i += 1

# ── Row: Memory ──────────────────────────────────────────────────────────────
p.append(row_panel(i, "Memory", 14)); i += 1

p.append(timeseries(i, "Memory Usage", 0, 15, 12, 8,
    [
        target(f'node_memory_MemTotal_bytes{{instance=~"{IF}"}} - node_memory_MemAvailable_bytes{{instance=~"{IF}"}}', "{{instance}} used",      "A"),
        target(f'node_memory_MemAvailable_bytes{{instance=~"{IF}"}}',                                                  "{{instance}} available", "B"),
    ],
    unit="bytes"
)); i += 1

p.append(bargauge(i, "Memory Available Now", 12, 15, 12, 8,
    [target(f'node_memory_MemAvailable_bytes{{instance=~"{IF}"}}', "{{instance}}")],
    unit="bytes"
)); i += 1

# ── Row: Block Storage /mnt/data ─────────────────────────────────────────────
p.append(row_panel(i, "Block Storage — /mnt/data (1TB per node)", 23)); i += 1

p.append(stat(i, "Block Storage Used %", 0, 24, 6, 4,
    [target(f'(1 - node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}} / node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}) * 100')],
    unit="percent",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 70}, {"color": "red", "value": 90}]
)); i += 1

p.append(stat(i, "Block Storage Free", 6, 24, 6, 4,
    [target(f'node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}', "{{instance}}")],
    unit="bytes", color_mode="value", graph_mode="none",
    thresholds=[{"color": "red", "value": None}, {"color": "yellow", "value": 107374182400}, {"color": "green", "value": 214748364800}]
)); i += 1

p.append(stat(i, "Block Storage Used", 12, 24, 6, 4,
    [target(f'node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}} - node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}', "{{instance}}")],
    unit="bytes", color_mode="background", graph_mode="none",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 751619276800}, {"color": "red", "value": 966367641600}]
)); i += 1

p.append(stat(i, "Block Storage Total", 18, 24, 6, 4,
    [target(f'node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}', "{{instance}}")],
    unit="bytes", color_mode="value", graph_mode="none",
    thresholds=[{"color": "green", "value": None}]
)); i += 1

p.append(bargauge(i, "Block Storage — Used vs Free per Node (/mnt/data)", 0, 28, 14, 8,
    [
        target(f'node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}} - node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}',
               "{{instance}} used", "A"),
        target(f'node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}',
               "{{instance}} free", "B"),
    ],
    unit="bytes"
)); i += 1

p.append(timeseries(i, "Block Storage Usage Over Time (/mnt/data)", 14, 28, 10, 8,
    [
        target(f'node_filesystem_size_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}} - node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}',
               "{{instance}} used", "A"),
        target(f'node_filesystem_avail_bytes{{instance=~"{IF}",mountpoint="/mnt/data"}}',
               "{{instance}} free", "B"),
    ],
    unit="bytes"
)); i += 1

# ── Row: Storage ─────────────────────────────────────────────────────────────
p.append(row_panel(i, "OS Disk — All Filesystems", 36)); i += 1

p.append(bargauge(i, "Disk Space — Used vs Free (all mounts)", 0, 37, 12, 9,
    [
        target(f'node_filesystem_size_bytes{{instance=~"{IF}",fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"}} - node_filesystem_avail_bytes{{instance=~"{IF}",fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"}}',
               "{{instance}} {{mountpoint}} used",  "A"),
        target(f'node_filesystem_avail_bytes{{instance=~"{IF}",fstype!~"tmpfs|devtmpfs|overlay",mountpoint!~"/boot.*"}}',
               "{{instance}} {{mountpoint}} free",  "B"),
    ],
    unit="bytes"
)); i += 1

p.append(timeseries(i, "Disk I/O Throughput", 12, 37, 12, 9,
    [
        target(f'irate(node_disk_read_bytes_total{{instance=~"{IF}"}}[5m])',    "{{instance}} read",  "A"),
        target(f'irate(node_disk_written_bytes_total{{instance=~"{IF}"}}[5m])', "{{instance}} write", "B"),
    ],
    unit="Bps"
)); i += 1

# ── Row: Network ─────────────────────────────────────────────────────────────
p.append(row_panel(i, "Network", 33)); i += 1

p.append(timeseries(i, "Network Receive Bandwidth", 0, 34, 12, 8,
    [target(f'irate(node_network_receive_bytes_total{{instance=~"{IF}",device!="lo"}}[5m]) * 8', "{{instance}} {{device}}")],
    unit="bps"
)); i += 1

p.append(timeseries(i, "Network Transmit Bandwidth", 12, 34, 12, 8,
    [target(f'irate(node_network_transmit_bytes_total{{instance=~"{IF}",device!="lo"}}[5m]) * 8', "{{instance}} {{device}}")],
    unit="bps"
)); i += 1

p.append(timeseries(i, "Network Errors & Drops", 0, 42, 24, 6,
    [
        target(f'irate(node_network_receive_errs_total{{instance=~"{IF}",device!="lo"}}[5m])',   "{{instance}} {{device}} rx_err",  "A"),
        target(f'irate(node_network_receive_drop_total{{instance=~"{IF}",device!="lo"}}[5m])',   "{{instance}} {{device}} rx_drop", "B"),
        target(f'irate(node_network_transmit_errs_total{{instance=~"{IF}",device!="lo"}}[5m])',  "{{instance}} {{device}} tx_err",  "C"),
        target(f'irate(node_network_transmit_drop_total{{instance=~"{IF}",device!="lo"}}[5m])',  "{{instance}} {{device}} tx_drop", "D"),
    ],
    unit="pps", fill=0
)); i += 1

# ── Row: System ──────────────────────────────────────────────────────────────
p.append(row_panel(i, "System", 48)); i += 1

p.append(timeseries(i, "System Load Average", 0, 49, 16, 8,
    [
        target(f'node_load1{{instance=~"{IF}"}}',  "{{instance}} 1m",  "A"),
        target(f'node_load5{{instance=~"{IF}"}}',  "{{instance}} 5m",  "B"),
        target(f'node_load15{{instance=~"{IF}"}}', "{{instance}} 15m", "C"),
    ]
)); i += 1

p.append(stat(i, "Open File Descriptors", 16, 49, 8, 8,
    [target(f'node_filefd_allocated{{instance=~"{IF}"}}')],
    unit="short", color_mode="background",
    thresholds=[{"color": "green", "value": None}, {"color": "yellow", "value": 50000}, {"color": "red", "value": 100000}]
)); i += 1


# ── dashboard object ──────────────────────────────────────────────────────────

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": p,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["nhn", "ipfs", "cluster"],
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
                "definition": 'label_values(node_cpu_seconds_total{job="ipfs-cluster-nodes"}, instance)',
                "hide": 0, "includeAll": True, "multi": True,
                "name": "instance",
                "query": {
                    "query": 'label_values(node_cpu_seconds_total{job="ipfs-cluster-nodes"}, instance)',
                    "refId": "StandardVariableQuery"
                },
                "refresh": 2,
                "regex": "133\\.186\\..*",
                "sort": 1,
                "type": "query"
            }
        ]
    },
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "NHN IPFS Cluster — Node Monitoring",
    "uid": "nhn-ipfs-cluster",
    "version": 0
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})

# ── push ──────────────────────────────────────────────────────────────────────

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
        print(f"  Slug: {result.get('slug', '')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
