#!/bin/bash
# =====================================================================
# install_news_count.sh: count the news every morning at 3:30, on the Mac Studio
#
#   bash install_news_count.sh            install (or reinstall) the 3:30 am count
#   bash install_news_count.sh status     is it installed, when did it last run?
#   bash install_news_count.sh now        run it once now, the way the schedule does
#   bash install_news_count.sh remove     stop it and take it out
#   bash install_news_count.sh --print    show the LaunchAgent file, change nothing
#
# My first scheduled agent run. It only counts (uv run news.py count): no model, no headlines
# kept. Trends need about a week of counts, so this starts before the brief exists.
# Same way as the monitor (com.drivingrange.monitor): a LaunchAgent that runs as me, in my session,
# so it can read the vault. It writes counts to ~/vault/_news/counts/, one row to the logbook
# (agent "news", event "direct", counts only), and its summary line to
# ~/driving-range/scripts/logs/news-count.log.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../01-environment/standard.sh
. "$HERE/../01-environment/standard.sh"

LABEL="com.drivingrange.newscount"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$DR_ROOT/scripts/logs/news-count.log"
HOUR="${NEWS_COUNT_HOUR:-3}"
MINUTE="${NEWS_COUNT_MINUTE:-30}"
UV="$(command -v uv || true)"

plist() {
cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$UV</string>
        <string>run</string>
        <string>--quiet</string>
        <string>news.py</string>
        <string>count</string>
    </array>
    <key>WorkingDirectory</key><string>$HERE</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONUNBUFFERED</key><string>1</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>$HOUR</integer>
        <key>Minute</key><integer>$MINUTE</integer>
    </dict>
    <key>RunAtLoad</key><false/>
    <key>StandardOutPath</key><string>$LOG</string>
    <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
}

case "${1:-install}" in
  --print)
    [ -n "$UV" ] || UV="/opt/homebrew/bin/uv"
    plist ;;
  status)
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "Scheduled: every day at $(printf '%d:%02d' "$HOUR" "$MINUTE") (Studio time)"
    else
      echo "Not installed"
    fi
    echo "Last lines of $LOG:"; tail -3 "$LOG" 2>/dev/null || echo "  (no runs yet)" ;;
  now)
    launchctl kickstart "gui/$(id -u)/$LABEL" 2>/dev/null || { echo "Not installed: run bash install_news_count.sh first."; exit 1; }
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
      sleep 2
      launchctl print "gui/$(id -u)/$LABEL" 2>/dev/null | grep -q "state = running" || break
    done
    echo "Last lines of $LOG:"; tail -3 "$LOG" 2>/dev/null ;;
  remove)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    rm -f "$PLIST"
    echo "Removed. Counts already saved stay in ~/vault/_news/counts/ (uv run news.py count still works by hand)." ;;
  install)
    [ "$(uname)" = "Darwin" ] || { echo "This sets up a macOS LaunchAgent. Run it on the Studio."; exit 1; }
    [ -n "$UV" ] || { echo "uv not found. Run 01-environment/setup.sh first."; exit 1; }
    mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
    plist > "$PLIST"
    plutil -lint "$PLIST" >/dev/null || { echo "The LaunchAgent file didn't check out: $PLIST"; exit 1; }
    launchctl bootstrap "gui/$(id -u)" "$PLIST" || { echo "launchctl couldn't load it."; exit 1; }
    echo "Installed: news count every day at $(printf '%d:%02d' "$HOUR" "$MINUTE") (Studio time)."
    echo "Try it now: bash install_news_count.sh now" ;;
  *)
    echo "Usage: bash install_news_count.sh [install|status|now|remove|--print]"; exit 2 ;;
esac
