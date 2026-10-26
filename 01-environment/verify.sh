#!/bin/bash
# =====================================================================
# verify.sh: check a Mac against the Driving Range Standard
#
# Usage:   bash verify.sh [profile]
#          (profile is optional once setup.sh has run)
#
# Run it from a NEW terminal window so it sees your current settings.
# Prints PASS / WARN / FAIL lines and saves a copy to
#   ~/driving-range/scripts/audits/<profile>_<host>_<time>.txt
# Exit code is the number of FAILs (0 = all good).
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=standard.sh
. "$HERE/standard.sh"

PASS=0; WARN=0; FAIL=0; LINES=""
rec() {  # rec STATUS "check" "detail"
  LINES="${LINES}$1|$2|${3:-}
"
  case "$1" in PASS) PASS=$((PASS+1));; WARN) WARN=$((WARN+1));; FAIL) FAIL=$((FAIL+1));; esac
}

# ---------- profile ----------
PROFILE="${1:-${DR_PROFILE:-}}"
if [ -z "$PROFILE" ] && [ -f "$DR_ROOT/.dr_profile" ]; then
  PROFILE="$(cat "$DR_ROOT/.dr_profile")"
fi
if load_profile "$PROFILE"; then
  rec PASS "profile declared" "$PROFILE"
  rec INFO "role" "$ROLE"
else
  echo "No profile found. Run: bash verify.sh <macbook|imac|studio>"
  exit 1
fi

# ---------- folders ----------
if [ -d "$DR_ROOT" ]; then rec PASS "root dir" "$DR_ROOT"; else rec FAIL "root dir" "$DR_ROOT missing"; fi
for d in $DR_DIRS; do
  if [ -d "$DR_ROOT/$d" ]; then rec PASS "dir $d"; else rec FAIL "dir $d" "missing"; fi
done

# ---------- tools ----------
for t in brew git pyenv python3 uv; do
  p="$(command -v "$t" 2>/dev/null)"
  if [ -n "$p" ]; then rec PASS "tool $t" "$p"; else rec FAIL "tool $t" "not found"; fi
done

# ---------- python ----------
G="$(pyenv global 2>/dev/null)"
if [ "$G" = "$PYTHON_VERSION" ]; then rec PASS "pyenv global" "$G"; else rec FAIL "pyenv global" "is '$G', want $PYTHON_VERSION"; fi

SHIMS="$HOME/.pyenv/shims"
PY="$(command -v python3 2>/dev/null)"
if [ "$PY" = "$SHIMS/python3" ]; then rec PASS "python3 resolves to shim" "$PY"; else rec FAIL "python3 resolves to shim" "resolves to '$PY'"; fi

case ":$PATH:" in *":$SHIMS:"*) rec PASS "PATH includes" "$SHIMS";; *) rec FAIL "PATH includes" "$SHIMS missing";; esac
for bad in /Library/Frameworks/Python.framework /opt/anaconda3; do
  case "$PATH" in *"$bad"*) rec FAIL "PATH excludes" "$bad is in PATH";; *) rec PASS "PATH excludes" "$bad";; esac
done

# ---------- ~/.zshrc ----------
ZRC="$HOME/.zshrc"
while IFS= read -r line; do
  if grep -qxF "$line" "$ZRC" 2>/dev/null; then rec PASS "zshrc line" "$line"; else rec FAIL "zshrc line" "missing: $line"; fi
done <<EOF
$(zshrc_required_lines)
EOF
if grep -q '^export MODEL_BASE_URL=' "$ZRC" 2>/dev/null; then
  rec PASS "zshrc line" "$(grep '^export MODEL_BASE_URL=' "$ZRC" | tail -1)"
else
  rec FAIL "zshrc line" "missing: export MODEL_BASE_URL="
fi

# ---------- must be absent ----------
for p in $MUST_BE_ABSENT; do
  if ls -d "$p"* >/dev/null 2>&1; then rec FAIL "absent" "$p is present"; else rec PASS "absent" "$p"; fi
done

# ---------- repos (info) ----------
REPOS="$(find "$DR_ROOT" -maxdepth 3 -type d -name .git 2>/dev/null | wc -l | tr -d ' ')"
if [ "$REPOS" = "0" ]; then rec INFO "repos" "none found yet under $DR_ROOT"; else rec INFO "repos" "$REPOS git repos under $DR_ROOT"; fi

# ---------- network + model server ----------
if [ -d /Applications/Tailscale.app ]; then
  rec PASS "app" "/Applications/Tailscale.app"
elif [ "$NEED_TAILSCALE" = "1" ]; then
  rec FAIL "app" "/Applications/Tailscale.app missing"
else
  rec WARN "app" "Tailscale not installed (optional for $PROFILE)"
fi
if [ -n "${MODEL_BASE_URL:-}" ]; then
  rec PASS "MODEL_BASE_URL" "$MODEL_BASE_URL"
  # Step 2 checks are WARN, not FAIL: the Studio may be asleep, and
  # a machine that has only done Step 1 should still pass.
  if curl -s -m 3 "$MODEL_BASE_URL/api/version" >/dev/null 2>&1; then
    rec PASS "model server reachable" "$MODEL_BASE_URL ($(curl -s -m 3 "$MODEL_BASE_URL/api/version" | sed 's/[{}"]//g'))"
    TAGS="$(curl -s -m 5 "$MODEL_BASE_URL/api/tags" 2>/dev/null)"
    for m in $MODEL_MAIN $MODEL_FAST $MODEL_EMBED; do
      if printf '%s' "$TAGS" | grep -q "\"name\":\"$m\""; then rec PASS "model available" "$m"
      else rec WARN "model available" "$m not on the server (run server_setup.sh on the Studio)"; fi
    done
  else
    rec WARN "model server reachable" "no answer from $MODEL_BASE_URL (Studio asleep, or Step 2 not done)"
  fi
else
  rec FAIL "MODEL_BASE_URL" "not set in this shell (run: exec zsh, or open a new terminal)"
fi

# ---------- model server host (Studio only) ----------
if [ "$PROFILE" = "studio" ]; then
  if command -v ollama >/dev/null 2>&1; then rec PASS "tool ollama" "$(command -v ollama)"
  else rec WARN "tool ollama" "not installed (Step 2: server_setup.sh)"; fi
  SVC="$HOME/Library/LaunchAgents/com.drivingrange.ollama.plist"
  if [ -f "$SVC" ]; then
    if launchctl print "gui/$(id -u)/com.drivingrange.ollama" >/dev/null 2>&1; then rec PASS "ollama service" "loaded, starts at login"
    else rec WARN "ollama service" "file exists but not loaded (re-run server_setup.sh)"; fi
    if grep -q "$OLLAMA_LISTEN:$OLLAMA_PORT" "$SVC"; then rec PASS "ollama listens" "$OLLAMA_LISTEN:$OLLAMA_PORT (other Macs can connect)"
    else rec WARN "ollama listens" "not on $OLLAMA_LISTEN:$OLLAMA_PORT (re-run server_setup.sh)"; fi
  else
    rec WARN "ollama service" "not set up (Step 2: server_setup.sh)"
  fi
fi

# ---------- memory vault (Studio only, Step 3) ----------
# WARN, not FAIL, until Step 3 is set up, so earlier steps still pass.
if [ "$PROFILE" = "studio" ]; then
  if [ -d "$VAULT_DIR" ]; then
    rec PASS "vault exists" "$VAULT_DIR"
    PERM="$(stat -f %Lp "$VAULT_DIR" 2>/dev/null || stat -c %a "$VAULT_DIR")"
    if [ "$PERM" = "700" ]; then rec PASS "vault private" "permissions 700"; else rec FAIL "vault private" "permissions $PERM, want 700 (chmod 700 $VAULT_DIR)"; fi
    INREPO=0; d="$VAULT_DIR"
    while [ "$d" != "/" ]; do [ -d "$d/.git" ] && INREPO=1; d="$(dirname "$d")"; done
    if [ "$INREPO" = "0" ]; then rec PASS "vault outside git" "not inside any repo"; else rec FAIL "vault outside git" "the vault is inside a git repo"; fi
    if fdesetup status 2>/dev/null | grep -q "On"; then rec PASS "FileVault" "on (disk encrypted)"; else rec FAIL "FileVault" "off: System Settings > Privacy & Security > FileVault"; fi
    CONST="$VAULT_DIR/values/constitution.md"; CHASH="$VAULT_DIR/.values/approved.sha256"
    if [ -f "$CONST" ] && [ -f "$CHASH" ]; then
      NOW_HASH="$( (shasum -a 256 "$CONST" 2>/dev/null || sha256sum "$CONST") | cut -d' ' -f1)"
      if [ "$NOW_HASH" = "$(tr -d '[:space:]' < "$CHASH")" ]; then rec PASS "constitution" "approved and unchanged"
      else rec FAIL "constitution" "BIG RED FLAG: changed since approval (uv run memory.py values)"; fi
    elif [ -f "$CONST" ]; then rec WARN "constitution" "not approved yet (uv run memory.py values approve)"
    else rec WARN "constitution" "none yet (Step 4)"; fi
    if [ -f "$VAULT_INDEX" ]; then rec PASS "memory index" "$VAULT_INDEX ($(du -h "$VAULT_INDEX" | cut -f1))"
    else rec WARN "memory index" "not built yet (uv run memory.py ingest)"; fi
  else
    rec WARN "vault exists" "$VAULT_DIR missing (Step 3: bash 03-memory/vault_setup.sh)"
  fi
fi

# ---------- disk ----------
KB=0
for d in $MODEL_DIRS; do
  [ -d "$d" ] && KB=$((KB + $(du -sk "$d" 2>/dev/null | cut -f1)))
done
MGB=$((KB / 1048576))
if [ "$MGB" -le "$MAX_MODEL_GB" ]; then rec PASS "local model size" "$MGB GB (max $MAX_MODEL_GB)"; else rec WARN "local model size" "$MGB GB (max $MAX_MODEL_GB)"; fi

FREE=$(( $(df -k "$HOME" | awk 'NR==2 {print $4}') / 1048576 ))
if [ "$FREE" -ge "$MIN_FREE_GB" ]; then rec PASS "free disk" "$FREE GB (min $MIN_FREE_GB)"; else rec FAIL "free disk" "$FREE GB (min $MIN_FREE_GB)"; fi

# ---------- report ----------
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"
REPORT="# host=$HOST profile=$PROFILE time=$NOW standard=v$STANDARD_VERSION
# pass=$PASS warn=$WARN fail=$FAIL
$LINES"

printf "%s" "$REPORT"

mkdir -p "$DR_ROOT/scripts/audits"
OUT="$DR_ROOT/scripts/audits/${PROFILE}_${HOST}_$(date +%Y%m%d_%H%M%S).txt"
printf "%s" "$REPORT" > "$OUT"
echo
echo "Saved: $OUT"
[ "$FAIL" -eq 0 ] && echo "All checks passed." || echo "$FAIL check(s) failed. Fix them and run again."
exit "$FAIL"
