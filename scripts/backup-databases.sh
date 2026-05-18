#!/usr/bin/env bash
# Database backup script — runs on the monitoring server (133.186.241.75)
# Backs up: MongoDB (133.186.159.180), PostgreSQL 1 (133.186.217.90), PostgreSQL 2 (125.6.39.52)
# Destination: /recovery-db-files/{mongodb,postgres1,postgres2}/
# Retention: 7 daily backups per database
#
# Cron (as ubuntu, on monitoring server):
#   0 2 * * * /bin/bash /home/ubuntu/scripts/backup-databases.sh >> /var/log/backup-databases.log 2>&1

set -euo pipefail

BACKUP_KEY="$HOME/.ssh/db-backup-key"
BACKUP_ROOT="/recovery-db-files"
RETENTION_DAYS=7
DATE="$(date -u +'%Y-%m-%d')"
TS="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

DISCORD_WEBHOOK="https://discord.com/api/webhooks/1500690813439709304/OZaTtp1X2e88iZSnG8gvnkKHHs7Yya_FCxqG6zH-pWgNsQ46bOABTI56dsZmtKK-ezlu"

SSH="ssh -i $BACKUP_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"

LOG_FILE="/var/log/backup-databases.log"
touch "$LOG_FILE" 2>/dev/null || LOG_FILE="$HOME/backup-databases.log"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG_FILE"; }

discord() {
  local msg="$1"
  msg="${msg//\"/\\\"}"
  msg="${msg//$'\n'/\\n}"
  curl -fsS -X POST -H 'Content-Type: application/json' \
    -d "{\"content\":\"${msg}\"}" "$DISCORD_WEBHOOK" >/dev/null 2>&1 || true
}

results=()
failed=()

# ── MongoDB ───────────────────────────────────────────────────────────────────
backup_mongodb() {
  local dest="$BACKUP_ROOT/mongodb"
  local file="mongodb-backup-${DATE}.archive.gz"
  local full="$dest/$file"

  log "MongoDB: starting backup → $full"
  $SSH ubuntu@133.186.159.180 \
    "mongodump --archive --gzip \
      --username admin \
      --password 'koneksi@dm1n' \
      --authenticationDatabase admin" \
    > "$full" 2>/tmp/mongodump-err.txt

  local size
  size=$(du -sh "$full" 2>/dev/null | cut -f1)
  log "MongoDB: done — $size"
  results+=("✅ MongoDB: $file ($size)")

  # Retention
  find "$dest" -name 'mongodb-backup-*.archive.gz' \
    -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
}

# ── PostgreSQL 1 ──────────────────────────────────────────────────────────────
backup_postgres1() {
  local dest="$BACKUP_ROOT/postgres1"
  local file="postgres1-backup-${DATE}.sql.gz"
  local full="$dest/$file"

  log "PostgreSQL 1: starting backup → $full"
  $SSH ubuntu@133.186.217.90 \
    "sudo -u postgres pg_dumpall --clean" \
    | gzip > "$full"

  local size
  size=$(du -sh "$full" 2>/dev/null | cut -f1)
  log "PostgreSQL 1: done — $size"
  results+=("✅ PostgreSQL 1: $file ($size)")

  find "$dest" -name 'postgres1-backup-*.sql.gz' \
    -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
}

# ── PostgreSQL 2 ──────────────────────────────────────────────────────────────
backup_postgres2() {
  local dest="$BACKUP_ROOT/postgres2"
  local file="postgres2-backup-${DATE}.sql.gz"
  local full="$dest/$file"

  log "PostgreSQL 2: starting backup → $full"
  $SSH ubuntu@125.6.39.52 \
    "sudo -u postgres pg_dumpall --clean" \
    | gzip > "$full"

  local size
  size=$(du -sh "$full" 2>/dev/null | cut -f1)
  log "PostgreSQL 2: done — $size"
  results+=("✅ PostgreSQL 2: $file ($size)")

  find "$dest" -name 'postgres2-backup-*.sql.gz' \
    -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
}

# ── Run all ───────────────────────────────────────────────────────────────────
log "=== Database backup started ==="

for db in mongodb postgres1 postgres2; do
  if backup_${db} 2>>/tmp/backup-${db}-err.txt; then
    true
  else
    err=$(cat /tmp/backup-${db}-err.txt 2>/dev/null | tail -5)
    failed+=("❌ ${db}: $err")
    log "FAILED: $db — $err"
  fi
done

# ── Discord notification ──────────────────────────────────────────────────────
if [ ${#failed[@]} -eq 0 ]; then
  lines=$(printf '%s\n' "${results[@]}")
  discord "🗄️ **Daily DB Backup — Success**\n📅 ${DATE}  🕒 ${TS}\n\n${lines}\n\n📦 Stored on: \`133.186.241.75:/recovery-db-files/\`\n🔁 Retention: 7 days  |  Next backup: tomorrow 02:00 UTC"
  log "All backups completed successfully"
else
  ok=$(printf '%s\n' "${results[@]}")
  fail=$(printf '%s\n' "${failed[@]}")
  discord "❌ **Daily DB Backup — FAILED**\n📅 ${DATE}  🕒 ${TS}\n\n${ok}\n${fail}\n\n⚠️ Check log: \`133.186.241.75:/var/log/backup-databases.log\`"
  log "Some backups failed"
  exit 1
fi
