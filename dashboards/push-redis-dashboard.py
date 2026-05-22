#!/usr/bin/env python3
"""Redis (Session Service) dashboard — 4 environments (DO prod, DO uat, DO staging, NHN staging).

Uses redis_exporter multi-target scrape. No agent installed on Redis hosts —
exporter connects from monitoring server using per-target password file.
"""

import json, ssl, urllib.request, base64, sys

GRAFANA_URL = "https://nhn-grafana.koneksi.co.kr"
USER   = "admin"
PASS   = "ar@dm1n"
DS_UID = "PBFA97CFB590B2093"
JOB    = "redis"

def ds(): return {"type": "prometheus", "uid": DS_UID}

# ── helpers ──────────────────────────────────────────────────────────────────

def stat(pid, title, expr, x, y, w, h, unit="short", thresholds=None,
         mappings=None, decimals=0, color_mode="background", graph_mode="area"):
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
            "colorMode": color_mode, "graphMode": graph_mode,
            "textMode": "value",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
        },
        "targets": [{"datasource": ds(), "expr": expr, "instant": True,
                     "legendFormat": " ", "refId": "A"}],
    }

def gauge(pid, title, expr, x, y, w, h, unit="percent", thresholds=None, maxv=100):
    return {
        "datasource": ds(),
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "id": pid, "title": title, "type": "gauge",
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": thresholds or [
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 70},
                    {"color": "red", "value": 85},
                ]},
                "unit": unit, "min": 0, "max": maxv,
            }
        },
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": ""},
            "showThresholdMarkers": True,
        },
        "targets": [{"datasource": ds(), "expr": expr, "instant": True,
                     "legendFormat": " ", "refId": "A"}],
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

# ── thresholds + mappings ────────────────────────────────────────────────────

UP_DOWN_MAPS = [{"type": "value", "options": {
    "1": {"text": "Up",   "color": "green"},
    "0": {"text": "Down", "color": "red"},
}}]
THRESH_UP_DOWN = [
    {"color": "red",   "value": None},
    {"color": "green", "value": 1},
]
THRESH_GOOD_HIGH = [
    {"color": "red",    "value": None},
    {"color": "yellow", "value": 1},
    {"color": "green",  "value": 4},
]
THRESH_BAD_NONZERO = [
    {"color": "green",  "value": None},
    {"color": "red",    "value": 1},
]

ENVS = [
    ("do-prod",     "DO Production"),
    ("do-uat",      "DO UAT"),
    ("do-staging",  "DO Staging"),
    ("nhn-staging", "NHN Staging"),
]

# ── build dashboard ─────────────────────────────────────────────────────────

panels = []
pid = 1
y = 0

# === Row: At-a-Glance ===
panels.append(row_panel(pid, "📊 At-a-Glance", y)); pid += 1
y += 1

panels.append(stat(pid, "Redis Instances Up",
    f'sum(redis_up{{job="{JOB}"}})',
    0, y, 6, 4, thresholds=THRESH_GOOD_HIGH)); pid += 1
panels.append(stat(pid, "Instances Down",
    f'sum(1 - redis_up{{job="{JOB}"}}) OR vector(0)',
    6, y, 6, 4, thresholds=THRESH_BAD_NONZERO)); pid += 1
panels.append(stat(pid, "Total Connected Clients",
    f'sum(redis_connected_clients{{job="{JOB}"}})',
    12, y, 6, 4, thresholds=[{"color":"blue","value":None}])); pid += 1
panels.append(stat(pid, "Total Memory Used",
    f'sum(redis_memory_used_bytes{{job="{JOB}"}})',
    18, y, 6, 4, unit="bytes", decimals=1,
    thresholds=[{"color":"blue","value":None}])); pid += 1
y += 4

# === Per-env status row ===
panels.append(row_panel(pid, "🟢 Status by Environment", y)); pid += 1
y += 1

for env_id, env_label in ENVS:
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
    panels.append(stat(pid, "Status",
        f'redis_up{{job="{JOB}", env="{env_id}"}}',
        4, y, 5, 4, mappings=UP_DOWN_MAPS, thresholds=THRESH_UP_DOWN, color_mode="background", graph_mode="none")); pid += 1
    panels.append(stat(pid, "Connected Clients",
        f'redis_connected_clients{{job="{JOB}", env="{env_id}"}}',
        9, y, 5, 4, thresholds=[{"color":"blue","value":None}])); pid += 1
    panels.append(stat(pid, "Memory Used",
        f'redis_memory_used_bytes{{job="{JOB}", env="{env_id}"}}',
        14, y, 5, 4, unit="bytes", decimals=1, thresholds=[{"color":"blue","value":None}])); pid += 1
    panels.append(stat(pid, "Uptime",
        f'redis_uptime_in_seconds{{job="{JOB}", env="{env_id}"}}',
        19, y, 5, 4, unit="s", thresholds=[{"color":"blue","value":None}])); pid += 1
    y += 4

# === Connections timeseries ===
panels.append(row_panel(pid, "👥 Connected Clients Over Time", y)); pid += 1
y += 1
panels.append(timeseries(pid, "Connected Clients per Environment",
    0, y, 24, 7, [
        {"datasource": ds(),
         "expr": f'redis_connected_clients{{job="{JOB}"}}',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="short")); pid += 1
y += 7

# === Memory ===
panels.append(row_panel(pid, "💾 Memory", y)); pid += 1
y += 1
panels.append(timeseries(pid, "Memory Used (RSS bytes)",
    0, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'redis_memory_used_bytes{{job="{JOB}"}}',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="bytes")); pid += 1
panels.append(timeseries(pid, "Memory Used vs Max (per env)",
    12, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'redis_memory_used_bytes{{job="{JOB}"}}',
         "legendFormat": "{{env}} used", "refId": "A"},
        {"datasource": ds(),
         "expr": f'redis_memory_max_bytes{{job="{JOB}"}} > 0',
         "legendFormat": "{{env}} max", "refId": "B"},
    ], unit="bytes")); pid += 1
y += 8

# === Ops + CPU ===
panels.append(row_panel(pid, "⚡ Throughput & CPU", y)); pid += 1
y += 1
panels.append(timeseries(pid, "Commands Processed (per second)",
    0, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'rate(redis_commands_processed_total{{job="{JOB}"}}[5m])',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="ops")); pid += 1
panels.append(timeseries(pid, "CPU Time (user + sys, rate)",
    12, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'rate(redis_cpu_user_seconds_total{{job="{JOB}"}}[5m]) + rate(redis_cpu_sys_seconds_total{{job="{JOB}"}}[5m])',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="percentunit")); pid += 1
y += 8

# === Keys & Evictions ===
panels.append(row_panel(pid, "🔑 Keys & Evictions", y)); pid += 1
y += 1
panels.append(timeseries(pid, "Total Keys per Environment",
    0, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'sum by (env) (redis_db_keys{{job="{JOB}"}})',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="short")); pid += 1
panels.append(timeseries(pid, "Evicted Keys (rate)",
    12, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'rate(redis_evicted_keys_total{{job="{JOB}"}}[5m])',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="ops")); pid += 1
y += 8

# === Hit rate & rejected connections ===
panels.append(row_panel(pid, "🎯 Cache Health", y)); pid += 1
y += 1
panels.append(timeseries(pid, "Cache Hit Rate",
    0, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'rate(redis_keyspace_hits_total{{job="{JOB}"}}[5m]) / '
                 f'(rate(redis_keyspace_hits_total{{job="{JOB}"}}[5m]) + rate(redis_keyspace_misses_total{{job="{JOB}"}}[5m]))',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="percentunit")); pid += 1
panels.append(timeseries(pid, "Rejected Connections (rate) — indicates maxclients hit",
    12, y, 12, 8, [
        {"datasource": ds(),
         "expr": f'rate(redis_rejected_connections_total{{job="{JOB}"}}[5m])',
         "legendFormat": "{{env}}", "refId": "A"}
    ], unit="ops")); pid += 1
y += 8

# ── dashboard ─────────────────────────────────────────────────────────────────

dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "graphTooltip": 1,
    "panels": panels,
    "refresh": "30s",
    "schemaVersion": 38,
    "tags": ["redis", "session", "service"],
    "templating": {"list": []},
    "time": {"from": "now-1h", "to": "now"},
    "timepicker": {},
    "timezone": "browser",
    "title": "Redis — Session Service (All Environments)",
    "uid": "redis-multi-env",
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
        print(f"✓ Dashboard pushed: Redis — Session Service")
        print(f"  URL : {GRAFANA_URL}{result.get('url','')}")
        print(f"  UID : {result.get('uid','')}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
    sys.exit(1)
