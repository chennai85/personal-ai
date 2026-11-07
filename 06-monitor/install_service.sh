#!/bin/bash
# =====================================================================
# install_service.sh: keep the monitor page running on the Mac Studio
#
#   bash install_service.sh            install (or reinstall) and start it
#   bash install_service.sh status     is it running, and does it answer?
#   bash install_service.sh remove     stop it and take it out
#   bash install_service.sh --print    show the LaunchAgent file, change nothing
#
# Same way as the model server (com.drivingrange.ollama): a LaunchAgent that starts at
# login and restarts if it stops. It runs as you, in your session, so it can read the vault.
# The only thing it writes is its startup lines, to ~/driving-range/scripts/logs/monitor.log.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../01-environment/standard.sh
. "$HERE/../01-environment/standard.sh"

LABEL="com.drivingrange.monitor"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT="${MONITOR_PORT:-8765}"
LOG="$DR_ROOT/scripts/logs/monitor.log"
PY="$(pyenv which python3 2>/dev/null || command -v python3)"

plist() {
cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$HERE/monitor.py</string>
        <string>serve</string>
        <string>--port</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key><string>$HERE</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONUNBUFFERED</key><string>1</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>StandardOutPath</key><string>$LOG</string>
    <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
}

answers() { curl -s -m 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/snapshot?days=1"; }

case "${1:-install}" in
  --print)
    plist ;;
  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then echo "Service: loaded, starts at login"; else echo "Service: not installed"; fi
    CODE="$(answers)"
    if [ "$CODE" = "200" ]; then echo "Page: answering on port $PORT"; else echo "Page: not answering (HTTP $CODE). Last lines of $LOG:"; tail -5 "$LOG" 2>/dev/null; fi ;;
  remove)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    rm -f "$PLIST"
    echo "Removed. The monitor no longer runs on its own (python3 monitor.py serve still works by hand)." ;;
  install)
    [ "$(uname)" = "Darwin" ] || { echo "This sets up a macOS LaunchAgent. Run it on the Studio."; exit 1; }
    [ -n "$PY" ] || { echo "python3 not found. Run 01-environment/setup.sh first."; exit 1; }
    mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    plist > "$PLIST"
    plutil -lint "$PLIST" >/dev/null || { echo "The LaunchAgent file didn't check out: $PLIST"; exit 1; }
    launchctl bootstrap "gui/$(id -u)" "$PLIST" || { echo "launchctl couldn't start it. See $LOG"; exit 1; }
    for _ in 1 2 3 4 5 6 7 8 9 10; do [ "$(answers)" = "200" ] && break; sleep 1; done
    if [ "$(answers)" = "200" ]; then
      echo "Running. On this Mac: http://localhost:$PORT"
      grep -h "Monitor on\|Tailscale" "$LOG" 2>/dev/null | tail -2
      echo "If macOS asks whether python3 may accept incoming connections: Allow (Tailscale needs it)."
    else
      echo "Installed, but the page isn't answering yet. Last lines of $LOG:"; tail -5 "$LOG" 2>/dev/null; exit 1
    fi ;;
  *)
    echo "Usage: bash install_service.sh [install|status|remove|--print]"; exit 2 ;;
esac
