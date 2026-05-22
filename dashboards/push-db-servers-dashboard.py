#!/usr/bin/env python3
"""Database Servers — System Metrics dashboard.

Layout:
  Row 0 — Top summary (3 cards: status + uptime + disk% + backup age per DB)
  Row 1 — MongoDB section (gauges + timeseries)
  Row 2 — PostgreSQL-1 section
  Row 3 — PostgreSQL-2 section

All queries use the `nodename` label (post-relabel, equivalent to instance).
No DB-specific exporters needed — uses node_exporter + textfile-collector metrics.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER   = "admin"
PASS   = "ar@dm1n"
DS_UID = "PBFA97CFB590B2093"

def ds(): return {"type": "prometheus", "uid": DS_UID}

# ── helpers ──────────────────────────────────────────────────────────────────

def target(expr, legend="", ref="A", instant=False):
    return {
        "datasource": ds(), "editorMode": "code", "expr": expr,
        "instant": instant, "range": not instant,
        "legendFormat": legend, "refId": ref
    }

def gauge(pid, title, x, y, w, h, expr, thresholds=None, unit="percent", maxv=100):
    thresholds = thresholds or [
        {"color": "green",  "value": None},
        {"color": "yellow", "value": 70},
        {"color": "red",    "value": 85},
    ]
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "gauge",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": thresholds},
                "unit": unit, "min": 0, "max": maxv,
            }
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
            "showThresholdLabels": False, "showThresholdMarkers": True
        },
        "targets": [target(expr, instant=True)],
    }

def stat(pid, title, x, y, w, h, expr, unit="short", thresholds=None,
         color_mode="value", mappings=None, decimals=None):
    fc_def = {
        "color": {"mode": "thresholds" if thresholds else "fixed", "fixedColor": "blue"},
        "unit": unit,
    }
    if thresholds:
        fc_def["thresholds"] = {"mode": "absolute", "steps": thresholds}
    if mappings:
        fc_def["mappings"] = mappings
    if decimals is not None:
        fc_def["decimals"] = decimals
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "stat",
        "fieldConfig": {"defaults": fc_def},
        "options": {
            "colorMode": color_mode, "graphMode": "area",
            "justifyMode": "auto", "textMode": "value",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
        },
        "targets": [target(expr, legend=" ", instant=True)],
    }

def timeseries(pid, title, x, y, w, h, targets, unit="short", legend_calcs=None):
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "timeseries",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": 10,
                    "lineWidth": 2, "showPoints": "never", "spanNulls": False,
                },
                "unit": unit,
            }
        },
        "options": {
            "legend": {
                "calcs": legend_calcs or ["mean", "max", "lastNotNull"],
                "displayMode": "table", "placement": "bottom",
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
    }

def row(pid, title, y):
    return {
        "collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "id": pid, "title": title, "type": "row",
    }

# ── status mappings + thresholds ─────────────────────────────────────────────

UP_DOWN_MAPPINGS = [{"type": "value", "options": {
    "1": {"text": "Up",   "color": "green"},
    "0": {"text": "Down", "color": "red"},
}}]

UP_DOWN_THRESHOLDS = [
    {"color": "red",   "value": None},
    {"color": "green", "value": 1},
]

BACKUP_THRESHOLDS = [
    {"color": "green",  "value": None},
    {"color": "yellow", "value": 24},
    {"color": "red",    "value": 26},
]

# ── build top summary row (1 card per DB) ────────────────────────────────────

def summary_card(pid_start, db_label, nodename, backup_label, x, y):
    """Returns 4 sub-panels making up one DB summary card."""
    panels = []
    # Status (Up/Down)
    panels.append(stat(pid_start, f"{db_label} — Status", x, y, 6, 4,
        f'up{{job="db-servers", nodename="{nodename}"}}',
        unit="short", thresholds=UP_DOWN_THRESHOLDS,
        color_mode="background", mappings=UP_DOWN_MAPPINGS))
    # Uptime
    panels.append(stat(pid_start+1, f"{db_label} — Uptime", x+6, y, 6, 4,
        f'time() - node_boot_time_seconds{{job="db-servers", nodename="{nodename}"}}',
        unit="s", decimals=0))
    # Disk %
    panels.append(stat(pid_start+2, f"{db_label} — Disk %", x+12, y, 6, 4,
        f'(1 - node_filesystem_avail_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}} / '
        f'node_filesystem_size_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}}) * 100',
        unit="percent", thresholds=[
            {"color": "green",  "value": None},
            {"color": "yellow", "value": 70},
            {"color": "red",    "value": 85},
        ], color_mode="background", decimals=1))
    # Backup age (hours)
    panels.append(stat(pid_start+3, f"{db_label} — Last Backup", x+18, y, 6, 4,
        f'(time() - db_backup_last_success_timestamp_seconds{{db="{backup_label}"}}) / 3600',
        unit="h", thresholds=BACKUP_THRESHOLDS, color_mode="background", decimals=1))
    return panels

# ── per-DB detail section ────────────────────────────────────────────────────

def db_section(pid_start, db_label, nodename, y):
    """Returns row header + gauges + timeseries panels for one DB."""
    panels = []
    pid = pid_start
    # Row header
    panels.append(row(pid, db_label, y)); pid += 1
    y += 1

    # Row: 4 small gauges (CPU / RAM / Disk / Disk Used)
    panels.append(gauge(pid, "CPU %", 0, y, 6, 6,
        f'100 * (1 - avg(rate(node_cpu_seconds_total{{job="db-servers", nodename="{nodename}", mode="idle"}}[5m])))',
        unit="percent")); pid += 1
    panels.append(gauge(pid, "RAM %", 6, y, 6, 6,
        f'(1 - node_memory_MemAvailable_bytes{{job="db-servers", nodename="{nodename}"}} / '
        f'node_memory_MemTotal_bytes{{job="db-servers", nodename="{nodename}"}}) * 100',
        unit="percent")); pid += 1
    panels.append(gauge(pid, "Disk % ( / )", 12, y, 6, 6,
        f'(1 - node_filesystem_avail_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}} / '
        f'node_filesystem_size_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}}) * 100',
        unit="percent")); pid += 1
    panels.append(stat(pid, "Disk Used / Total", 18, y, 6, 6,
        f'node_filesystem_size_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}} - '
        f'node_filesystem_avail_bytes{{job="db-servers", nodename="{nodename}", mountpoint="/", fstype!="tmpfs"}}',
        unit="bytes", decimals=1)); pid += 1
    y += 6

    # Row: CPU + RAM timeseries
    panels.append(timeseries(pid, "CPU Usage Over Time", 0, y, 12, 7, [
        target(
            f'100 * (1 - avg(rate(node_cpu_seconds_total{{job="db-servers", nodename="{nodename}", mode="idle"}}[5m])))',
            legend="CPU %", ref="A"
        ),
    ], unit="percent")); pid += 1
    panels.append(timeseries(pid, "Memory Usage", 12, y, 12, 7, [
        target(
            f'node_memory_MemTotal_bytes{{job="db-servers", nodename="{nodename}"}} - '
            f'node_memory_MemAvailable_bytes{{job="db-servers", nodename="{nodename}"}}',
            legend="used", ref="A"
        ),
        target(
            f'node_memory_MemAvailable_bytes{{job="db-servers", nodename="{nodename}"}}',
            legend="available", ref="B"
        ),
    ], unit="bytes")); pid += 1
    y += 7

    # Row: Disk I/O + Network
    panels.append(timeseries(pid, "Disk I/O", 0, y, 12, 7, [
        target(
            f'rate(node_disk_read_bytes_total{{job="db-servers", nodename="{nodename}"}}[5m])',
            legend="read", ref="A"
        ),
        target(
            f'rate(node_disk_written_bytes_total{{job="db-servers", nodename="{nodename}"}}[5m])',
            legend="write", ref="B"
        ),
    ], unit="Bps")); pid += 1
    panels.append(timeseries(pid, "Network Throughput", 12, y, 12, 7, [
        target(
            f'rate(node_network_receive_bytes_total{{job="db-servers", nodename="{nodename}", device!="lo"}}[5m])',
            legend="{{device}} rx", ref="A"
        ),
        target(
            f'rate(node_network_transmit_bytes_total{{job="db-servers", nodename="{nodename}", device!="lo"}}[5m])',
            legend="{{device}} tx", ref="B"
        ),
    ], unit="Bps")); pid += 1
    y += 7

    return panels, pid, y

# ── build dashboard ──────────────────────────────────────────────────────────

panels = []

# Top summary cards — 3 DBs, each 8 cols wide (but the helper uses 4 sub-panels x 6 wide = 24 cols)
# So instead: stack vertically as 3 horizontal rows of compact summary cards.
# Better: one row of 3 cards with 4 mini stats inside each.
# Simpler approach: one big summary panel per DB taking 8 cols wide using stat sub-panels.
# For now, place each DB summary inline (one DB per horizontal row, 24 cols).

pid = 1
y = 0

# Summary panel — DBs side-by-side, each is 8 cols × 4 high, showing 4 sub-stats stacked
# That's complex; simpler: one row of 3 cards, each card = 1 stat (status), tile separately
# Better readability: tile horizontally — 1 row of 4 stats per DB.

# MongoDB summary row
panels.append(row(pid, "📊 At-a-Glance Summary", y)); pid += 1
y += 1
panels.extend(summary_card(pid, "MongoDB", "mongodb-1", "mongodb", 0, y))
pid += 4
y += 4
panels.extend(summary_card(pid, "PostgreSQL-1", "postgres-1", "postgres1", 0, y))
pid += 4
y += 4
panels.extend(summary_card(pid, "PostgreSQL-2", "postgres-2", "postgres2", 0, y))
pid += 4
y += 4

# Per-DB detail sections
for db_label, nodename in [
    ("🍃 MongoDB (mongodb-1)",    "mongodb-1"),
    ("🐘 PostgreSQL-1",            "postgres-1"),
    ("🐘 PostgreSQL-2",            "postgres-2"),
]:
    new_panels, pid, y = db_section(pid, db_label, nodename, y)
    panels.extend(new_panels)

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["database", "mongodb", "postgresql"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Database Servers — System Metrics",
    "uid": "db-servers",
    "version": 0,
}

payload = json.dumps({"overwrite": True, "dashboard": dashboard})
auth = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
req = urllib.request.Request(
    f"{GRAFANA_URL}/api/dashboards/db",
    data=payload.encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
    method="POST",
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
