#!/bin/bash
# =====================================================================
# server_setup.sh: turn the Mac Studio into the model server
#
# Usage (on the Mac Studio only):   bash server_setup.sh
#
# What it does:
#   1. Installs Ollama (the model server) with Homebrew
#   2. Runs it as a background service that starts at login
#      and accepts requests from your other Macs
#   3. Downloads the models named in standard.sh (main, fast, embedding)
#
# Safe to run more than once. To switch models, edit MODEL_MAIN /
# MODEL_FAST in 01-environment/standard.sh and run this again.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../01-environment/standard.sh
. "$HERE/../01-environment/standard.sh"

step() { echo; echo "==> $1"; }
ok()   { echo "    ok: $1"; }
die()  { echo "    STOP: $1"; exit 1; }

# ---------------------------------------------------------------------
step "0. Checks"
PROFILE="${DR_PROFILE:-$(cat "$DR_ROOT/.dr_profile" 2>/dev/null)}"
[ "$PROFILE" = "studio" ] || die "this machine's profile is '$PROFILE'. Run this on the Mac Studio only."
command -v brew >/dev/null || die "Homebrew not found. Finish Step 1 first."
if [ -d /Applications/Ollama.app ]; then
  echo "    Note: the Ollama desktop app is installed. Quit it and remove it from"
  echo "    System Settings > General > Login Items, or it will fight this service for port $OLLAMA_PORT."
fi
ok "profile studio, Homebrew present"

# ---------------------------------------------------------------------
step "1. Install Ollama"
if brew list --formula ollama >/dev/null 2>&1; then
  ok "already installed ($(ollama --version 2>/dev/null | head -1))"
else
  brew install ollama || die "brew install ollama failed"
  ok "installed"
fi
OLLAMA_BIN="$(brew --prefix)/bin/ollama"
[ -x "$OLLAMA_BIN" ] || die "ollama not found at $OLLAMA_BIN"

# Homebrew's own service would start a second copy without our settings
if brew services list 2>/dev/null | grep -q '^ollama .*started'; then
  brew services stop ollama >/dev/null 2>&1
  ok "stopped Homebrew's default ollama service (ours replaces it)"
fi

# ---------------------------------------------------------------------
step "2. Background service (starts at login, open to your other Macs)"
LABEL="com.drivingrange.ollama"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$DR_ROOT/scripts/logs"
mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- Managed by server_setup.sh (Driving Range Standard v$STANDARD_VERSION). Edit standard.sh, not this file. -->
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$OLLAMA_BIN</string>
    <string>serve</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>OLLAMA_HOST</key><string>$OLLAMA_LISTEN:$OLLAMA_PORT</string>
    <key>OLLAMA_CONTEXT_LENGTH</key><string>$OLLAMA_CONTEXT_LENGTH</string>
    <key>OLLAMA_KEEP_ALIVE</key><string>$OLLAMA_KEEP_ALIVE</string>
    <key>OLLAMA_NUM_PARALLEL</key><string>$OLLAMA_NUM_PARALLEL</string>
    <key>OLLAMA_MAX_LOADED_MODELS</key><string>$OLLAMA_MAX_LOADED_MODELS</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOGDIR/ollama.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/ollama.log</string>
</dict>
</plist>
EOF
plutil -lint "$PLIST" >/dev/null || die "service file is invalid: $PLIST"

# Reload so new settings take effect
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1
launchctl bootstrap "gui/$(id -u)" "$PLIST" || die "could not start the service (see $LOGDIR/ollama.log)"
ok "service $LABEL loaded"
ok "listening on $OLLAMA_LISTEN:$OLLAMA_PORT, context $OLLAMA_CONTEXT_LENGTH, keep-alive $OLLAMA_KEEP_ALIVE"

# Wait for the server to answer
printf "    waiting for the server"
for _ in $(seq 1 30); do
  if curl -s -m 2 "http://localhost:$OLLAMA_PORT/api/version" >/dev/null; then echo; break; fi
  printf "."; sleep 1
done
curl -s -m 2 "http://localhost:$OLLAMA_PORT/api/version" >/dev/null || die "server did not start (see $LOGDIR/ollama.log)"
ok "server answering: $(curl -s "http://localhost:$OLLAMA_PORT/api/version")"

# ---------------------------------------------------------------------
step "3. Download models"
echo "    The main model is about 24 GB. This can take a while."
for m in "$MODEL_MAIN" "$MODEL_FAST" "$MODEL_EMBED"; do  # embedding model added in v1.3 (Step 3)
  if "$OLLAMA_BIN" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$m"; then
    ok "$m already downloaded"
  else
    echo "    pulling $m ..."
    "$OLLAMA_BIN" pull "$m" || die "could not download $m"
    ok "$m downloaded"
  fi
done

# ---------------------------------------------------------------------
echo
echo "================================================================"
echo "Model server ready on this Mac Studio."
echo
"$OLLAMA_BIN" list
echo
echo "Next:"
echo "  1. Quick test:   ollama run $MODEL_FAST \"Say hello in five words.\""
echo "  2. Speed test:   bash $HERE/speedtest.sh"
echo "  3. Checklist:    bash $HERE/../01-environment/verify.sh"
echo "  Then run speedtest.sh and verify.sh on the iMac and MacBook too."
echo "================================================================"
