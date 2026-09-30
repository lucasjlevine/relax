#!/usr/bin/env bash
# Run ON Silk (SSH). Find and kill Node workers for this account's apps.
# Unit may respawn them — kill, then reload apps from .silk.ini.
set -euo pipefail

NETID="${NETID:-$(whoami)}"
FORCE="${FORCE:-0}"

echo "==> User: $NETID (uid=$(id -u))"
echo
echo "==> Your processes (node / server.js / unit / relax):"
ps -u "$NETID" -o pid,ppid,stat,etime,args 2>/dev/null \
  | grep -Eine 'node|server\.js|nginx-unit|unit:|relax/deploy|relax/backend|uvicorn' \
  | grep -viE 'grep|kill-stale' || echo "(none matched)"

echo
echo "==> pgrep:"
pgrep -afu "$NETID" 'node|server\.js|uvicorn' 2>/dev/null || echo "(none)"

echo
if [[ "$FORCE" != "1" ]]; then
  printf "Kill matching Node PIDs? Type yes: "
  read -r ans
  if [[ "$ans" != "yes" ]]; then
    echo "Aborted. Manual: kill <PID>  or  kill -9 <PID>"
    exit 0
  fi
fi

PIDS=""
for pat in \
  'relax/deploy/silk/dist/web/server\.js' \
  'node.*server\.js'
do
  PIDS="$PIDS $(pgrep -u "$NETID" -f "$pat" 2>/dev/null || true)"
done

# uniq
PIDS=$(echo "$PIDS" | tr ' ' '\n' | awk 'NF && !seen[$0]++' | tr '\n' ' ')
PIDS=$(echo "$PIDS" | xargs)

if [[ -z "${PIDS}" ]]; then
  echo "No auto-matched PIDs. Kill manually from the list above:"
  echo "  kill <PID>"
  echo "  kill -9 <PID>   # if it ignores TERM"
  exit 0
fi

echo "==> kill (TERM): $PIDS"
# shellcheck disable=SC2086
kill $PIDS 2>/dev/null || true
sleep 2

LEFT=""
for pid in $PIDS; do
  if kill -0 "$pid" 2>/dev/null; then
    LEFT="$LEFT $pid"
  fi
done
LEFT=$(echo "$LEFT" | xargs)

if [[ -n "${LEFT}" ]]; then
  echo "==> kill -9: $LEFT"
  # shellcheck disable=SC2086
  kill -9 $LEFT 2>/dev/null || true
fi

echo "==> Still running:"
pgrep -afu "$NETID" 'node|server\.js|uvicorn' 2>/dev/null || echo "(none)"

cat <<EOF

Reload the Unit Node app (or Unit may spawn workers again from old config):
  cp ~/www-root/relax/deploy/silk/.silk.ini ~/www-root/.silk.ini
  silk site ${NETID}.w3.uvm.edu update
  silk app ${NETID}.w3.uvm.edu load

API is systemd (not Unit): systemctl --user restart relax-api

Non-interactive kill:  FORCE=1 ./deploy/silk/kill-stale-apps.sh
EOF
