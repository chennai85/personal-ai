#!/bin/bash
# =====================================================================
# vault_setup.sh: create my personal vault on the Mac Studio
#
# Usage (on the Mac Studio):   bash vault_setup.sh
#
# The vault path comes from VAULT_DIR in 01-environment/standard.sh.
#
# What it does:
#   1. Creates ~/vault from vault-template/ (only my user can read it)
#   2. Never overwrites a file I've already filled in
#   3. Checks privacy: FileVault on, vault outside any git repo
#   4. Lists what's still blank, so I know what to fill in first
#
# Safe to run again after a git pull: new template files are added,
# my filled-in files are left alone.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../01-environment/standard.sh
. "$HERE/../01-environment/standard.sh"
TEMPLATE="$HERE/vault-template"
VAULT="$VAULT_DIR"

step() { echo; echo "==> $1"; }
ok()   { echo "    ok: $1"; }
warn() { echo "    WARN: $1"; }
die()  { echo "    STOP: $1"; exit 1; }

# ---------------------------------------------------------------------
step "0. Checks"
[ -d "$TEMPLATE" ] || die "vault-template/ not found next to this script"
case "$VAULT/" in
  "$(dirname "$HERE")"/*) die "the vault must not be inside the repo ($VAULT)";;
esac
d="$VAULT"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  [ -d "$d/.git" ] && die "$d is a git repo. The vault must live outside any repo."
  d="$(dirname "$d")"
done
ok "vault path $VAULT is outside any git repo"

# ---------------------------------------------------------------------
step "1. Create the vault"
mkdir -p "$VAULT"
chmod 700 "$VAULT"
added=0; kept=0
while IFS= read -r src; do
  rel="${src#"$TEMPLATE"/}"
  dst="$VAULT/$rel"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    kept=$((kept+1))
  else
    cp "$src" "$dst"
    added=$((added+1))
  fi
done < <(find "$TEMPLATE" -type f ! -name '.keep')
for sub in inbox briefs .index; do mkdir -p "$VAULT/$sub"; done
chmod 700 "$VAULT/.index"
ok "$added file(s) added, $kept already there and left alone"
ok "permissions 700 (only my user)"

# ---------------------------------------------------------------------
step "2. Privacy"
if [ "$(uname)" = "Darwin" ]; then
  if fdesetup status 2>/dev/null | grep -q "On"; then
    ok "FileVault is on (the disk is encrypted)"
  else
    warn "FileVault is off. System Settings > Privacy & Security > FileVault > Turn On"
  fi
  if [ "$(scutil --get LocalHostName 2>/dev/null)" != "" ]; then
    ok "this Mac: $(scutil --get LocalHostName)"
  fi
else
  warn "not macOS: skipping the FileVault check"
fi

# ---------------------------------------------------------------------
step "3. What's still blank"
total=0
while IFS= read -r f; do
  n=$(grep -c '⟪' "$f")
  rel="${f#"$VAULT"/}"
  case "$rel" in people/_template.md|README.md) continue;; esac
  if [ "$n" -gt 0 ]; then
    printf "    %-28s %3s blank\n" "$rel" "$n"
    total=$((total+n))
  else
    printf "    %-28s done\n" "$rel"
  fi
done < <(find "$VAULT" -name '*.md' -not -path '*/briefs/*' -not -path '*/.index/*' | sort)
echo "    ---"
echo "    $total blank field(s). Blank is fine: the AI skips them and says so."

# ---------------------------------------------------------------------
step "4. Embedding model"
if curl -s -m 5 "http://localhost:$OLLAMA_PORT/api/tags" 2>/dev/null | grep -q "\"name\":\"$MODEL_EMBED\""; then
  ok "$MODEL_EMBED is on the model server"
else
  warn "$MODEL_EMBED not found. Run: bash $HERE/../02-local-model/server_setup.sh"
fi

echo
echo "Next: build the index:   uv run memory.py ingest"
echo "Then fill in on THIS Mac (not in a cloud chat):"
echo "  open -e $VAULT/me/money.md $VAULT/me/travel.md $VAULT/me/golf.md"
echo "  cp $VAULT/people/_template.md $VAULT/people/<friends-name>.md"
