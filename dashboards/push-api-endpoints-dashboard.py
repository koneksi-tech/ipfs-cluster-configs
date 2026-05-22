#!/usr/bin/env python3
"""API Endpoints — Backend + Data Provenance health dashboard.

Covers 9 endpoints across 4 environments (DO prod, DO uat, DO staging, NHN staging):
  - probe success / HTTP status
  - response latency (with phase breakdown)
  - TLS certificate expiry per service
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER   = "admin"
PASS   = "ar@dm1n"
DS_UID = "PBFA97CFB590B2093"
JOB    = "backend-api-health"

def ds(): return {"type": "prometheus", "uid": DS_UID}

# ── helpers ──────────────────────────────────────────────────────────────────

def target(expr, legend="", ref="A", instant=False, fmt="time_series"):
    return {
        "datasource": ds(), "editorMode": "code", "expr": expr,
        "instant": instant, "range": not instant,
        "legendFormat": legend, "refId": ref, "format": fmt
    }

def stat(pid, title, expr, x, y, w, h, unit="short", thresholds=None,
         mappings=None, decimals=0, color_mode="background"):
    fc = {
        "color": {"mode": "thresholds" if thresholds else "fixed", "fixedColor": "blue"},
        "unit": unit, "decimals": decimals,
    }
    if thresholds: fc["thresholds"] = {"mode": "absolute", "steps": thresholds}
    if mappings:   fc["mappings"]   = mappings
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "stat",
        "fieldConfig": {"defaults": fc},
        "options": {
            "colorMode": color_mode, "graphMode": "area",
            "textMode": "value",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
        },
        "targets": [target(expr, legend=" ", instant=True)],
    }

def timeseries(pid, title, x, y, w, h, targets, unit="short", calcs=None):
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "timeseries",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": 8,
                    "lineWidth": 2, "showPoints": "never", "spanNulls": False,
                },
                "unit": unit,
            }
        },
        "options": {
            "legend": {"calcs": calcs or ["mean","max","lastNotNull"],
                       "displayMode": "table", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": targets,
    }

def row_panel(pid, title, y):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": pid, "title": title, "type": "row"}

# ── thresholds ──────────────────────────────────────────────────────────────

THRESH_UP_DOWN = [
    {"color": "red",   "value": None},
    {"color": "green", "value": 1},
]
UP_DOWN_MAPS = [{"type": "value", "options": {
    "1": {"text": "OK",   "color": "green"},
    "0": {"text": "DOWN", "color": "red"},
}}]
THRESH_TLS = [
    {"color": "red",    "value": None},
    {"color": "orange", "value": 7},
    {"color": "yellow", "value": 14},
    {"color": "green",  "value": 30},
]
THRESH_LATENCY = [
    {"color": "green",  "value": None},
    {"color": "yellow", "value": 0.5},
    {"color": "red",    "value": 1.0},
]
THRESH_GOOD_HIGH = [
    {"color": "red",    "value": None},
    {"color": "yellow", "value": 1},
    {"color": "green",  "value": 9},
]
THRESH_BAD_NONZERO = [
    {"color": "green",  "value": None},
    {"color": "red",    "value": 1},
]

# ── environments + services to render ──────────────────────────────────────

ENVS = [
    ("do-prod",     "DO Production",   "#b91c1c"),
    ("do-uat",      "DO UAT",          "#6366f1"),
    ("do-staging",  "DO Staging",      "#1f6feb"),
    ("nhn-staging", "NHN Staging",     "#0ea5e9"),
]

# ── build dashboard ─────────────────────────────────────────────────────────

panels = []
pid = 1
y = 0

# === Row: at-a-glance summary ===
panels.append(row_panel(pid, "📊 At-a-Glance", y)); pid += 1
y += 1

panels.append(stat(pid, "Endpoints Monitored",
    f'count(probe_success{{job="{JOB}"}})',
    0, y, 6, 4, thresholds=[{"color":"blue","value":None}], color_mode="background")); pid += 1

panels.append(stat(pid, "All Up (✓ OK)",
    f'count(probe_success{{job="{JOB}"}} == 1)',
    6, y, 6, 4, thresholds=THRESH_GOOD_HIGH, color_mode="background")); pid += 1

panels.append(stat(pid, "Down (✗)",
    f'count(probe_success{{job="{JOB}"}} == 0) OR vector(0)',
    12, y, 6, 4, thresholds=THRESH_BAD_NONZERO, color_mode="background")); pid += 1

panels.append(stat(pid, "Avg Response Time",
    f'avg(probe_duration_seconds{{job="{JOB}"}})',
    18, y, 6, 4, unit="s", decimals=2,
    thresholds=THRESH_LATENCY, color_mode="background")); pid += 1
y += 4

# === Row: status by environment ===
panels.append(row_panel(pid, "🟢 Status by Environment", y)); pid += 1
y += 1

# Render each env as a uniform horizontal row: label + Backend + Data Provenance
# (NHN Staging's "Backend (api)" alias is monitored in Prometheus but not shown here
#  to keep the grid uniform and avoid Grafana panel-compaction artifacts.)
for env_id, env_label, _ in ENVS:
    label_panel = {
        "datasource": ds(),
        "gridPos": {"h": 4, "w": 4, "x": 0, "y": y},
        "id": pid,
        "options": {
            "content": f'<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#fff;background:#1f2937;border-radius:6px;font-weight:600;font-size:15px;padding:8px;text-align:center;">{env_label}</div>',
            "mode": "html"
        },
        "type": "text", "transparent": True,
    }
    panels.append(label_panel); pid += 1
    # Backend (worst of all backend-* services per env — min returns 0 if any down)
    panels.append(stat(pid, "Backend",
        f'min(probe_success{{job="{JOB}", env="{env_id}", service=~"koneksi-backend.*"}})',
        4, y, 10, 4, mappings=UP_DOWN_MAPS, thresholds=THRESH_UP_DOWN, color_mode="background")); pid += 1
    panels.append(stat(pid, "Data Provenance",
        f'probe_success{{job="{JOB}", env="{env_id}", service="data-provenance"}}',
        14, y, 10, 4, mappings=UP_DOWN_MAPS, thresholds=THRESH_UP_DOWN, color_mode="background")); pid += 1
    y += 4

# === Row: response time ===
panels.append(row_panel(pid, "⏱ Response Latency", y)); pid += 1
y += 1

panels.append(timeseries(pid, "Response Time per Endpoint",
    0, y, 24, 8, [
        target(f'probe_duration_seconds{{job="{JOB}"}}',
               legend="{{env}} · {{service}}", ref="A"),
    ], unit="s")); pid += 1
y += 8

panels.append(timeseries(pid, "Request Phase Breakdown (avg across endpoints)",
    0, y, 24, 7, [
        target(f'avg by (phase) (probe_http_duration_seconds{{job="{JOB}"}})',
               legend="{{phase}}", ref="A"),
    ], unit="s")); pid += 1
y += 7

# === Row: HTTP status codes ===
panels.append(row_panel(pid, "📡 HTTP Response Codes", y)); pid += 1
y += 1

panels.append(timeseries(pid, "HTTP Status Code per Endpoint",
    0, y, 24, 7, [
        target(f'probe_http_status_code{{job="{JOB}"}}',
               legend="{{env}} · {{service}}", ref="A"),
    ], unit="short")); pid += 1
y += 7

# === Row: TLS certs ===
panels.append(row_panel(pid, "🔒 TLS Certificate Expiry", y)); pid += 1
y += 1

# TLS expiry bar per env
panels.append(timeseries(pid, "Days Until Certificate Expiry",
    0, y, 24, 9, [
        target(f'(probe_ssl_earliest_cert_expiry{{job="{JOB}"}} - time()) / 86400',
               legend="{{env}} · {{service}}", ref="A"),
    ], unit="d", calcs=["min","lastNotNull"])); pid += 1
y += 9

# === dashboard ==============================================================

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["api", "endpoints", "backend", "provenance"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "API Endpoints — Backend & Data Provenance",
    "uid": "api-endpoints",
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
        print(f"✓ Dashboard pushed: API Endpoints — Backend & Data Provenance")
        print(f"  URL : {GRAFANA_URL}{result.get('url','')}")
        print(f"  UID : {result.get('uid','')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
