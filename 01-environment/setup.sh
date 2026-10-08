#!/bin/bash
# =====================================================================
# setup.sh: build the Driving Range workbench on a Mac
#
# Usage:   bash setup.sh <profile>
#          profile = macbook | imac | studio
#
# Safe to run more than once. It only adds what is missing.
# It never deletes anything. Things it can't do for you
# (like installing Tailscale) are listed at the end.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=standard.sh
. "$HERE/standard.sh"

PROFILE="${1:-}"
if ! load_profile "$PROFILE"; then
  echo "Usage: bash setup.sh <macbook|imac|studio>"
  exit 1
fi

TODO=""
add_todo() { TODO="${TODO}  - $1
"; }
step() { echo; echo "==> $1"; }
ok()   { echo "    ok: $1"; }

echo "Driving Range Standard v$STANDARD_VERSION"
echo "Profile: $PROFILE ($ROLE)"

# ---------------------------------------------------------------------
step "1. Xcode Command Line Tools (compilers git and pyenv need)"
if xcode-select -p >/dev/null 2>&1; then
  ok "already installed"
else
  echo "    A macOS window will open. Click Install, wait for it to finish,"
  echo "    then run this script again."
  xcode-select --install
  exit 0
fi

# ---------------------------------------------------------------------
step "2. Homebrew (the Mac package manager)"
if [ -x /opt/homebrew/bin/brew ]; then
  BREW=/opt/homebrew/bin/brew
elif [ -x /usr/local/bin/brew ]; then
  BREW=/usr/local/bin/brew
else
  echo "    Installing Homebrew. It will ask for your Mac password."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -x /opt/homebrew/bin/brew ]; then BREW=/opt/homebrew/bin/brew; else BREW=/usr/local/bin/brew; fi
fi
eval "$("$BREW" shellenv)"
ok "$BREW"

# Make brew available in every new terminal
SHELLENV_LINE="eval \"\$($BREW shellenv)\""
touch "$HOME/.zprofile"
if grep -qF "$SHELLENV_LINE" "$HOME/.zprofile"; then
  ok "brew already in ~/.zprofile"
else
  echo "$SHELLENV_LINE" >> "$HOME/.zprofile"
  ok "added brew to ~/.zprofile"
fi

# ---------------------------------------------------------------------
step "3. Tools: $BREW_TOOLS"
for t in $BREW_TOOLS; do
  if "$BREW" list --formula "$t" >/dev/null 2>&1; then
    ok "$t already installed"
  else
    "$BREW" install "$t" && ok "installed $t"
  fi
done

# ---------------------------------------------------------------------
step "4. Python $PYTHON_VERSION via pyenv"
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - bash)"
if pyenv versions --bare | grep -qx "$PYTHON_VERSION"; then
  ok "Python $PYTHON_VERSION already installed"
else
  echo "    Building Python $PYTHON_VERSION. This takes a few minutes."
  pyenv install "$PYTHON_VERSION"
fi
pyenv global "$PYTHON_VERSION"
ok "pyenv global = $(pyenv global)"

# ---------------------------------------------------------------------
step "5. ~/.zshrc settings"
touch "$HOME/.zshrc"
BEGIN="# >>> driving-range >>>"
END="# <<< driving-range <<<"
# Remove an older driving-range block (only ours), then write a fresh one
if grep -qF "$BEGIN" "$HOME/.zshrc"; then
  cp "$HOME/.zshrc" "$HOME/.zshrc.bak.$(date +%Y%m%d%H%M%S)"
  sed -i '' "/$BEGIN/,/$END/d" "$HOME/.zshrc"
  ok "replaced previous driving-range block (backup saved)"
fi
# Only add required lines that aren't already elsewhere in ~/.zshrc
MISSING="$(zshrc_required_lines | while IFS= read -r line; do
  grep -qxF "$line" "$HOME/.zshrc" || echo "$line"
done)"
{
  echo "$BEGIN"
  echo "# Driving Range Standard v$STANDARD_VERSION. Managed by setup.sh"
  [ -n "$MISSING" ] && echo "$MISSING"
  echo "export DR_PROFILE=\"$PROFILE\""
  echo "export MODEL_BASE_URL=\"$MODEL_URL\""
  echo "$END"
} >> "$HOME/.zshrc"
ok "profile=$PROFILE, MODEL_BASE_URL=$MODEL_URL"

# ---------------------------------------------------------------------
step "6. Folders under $DR_ROOT"
for d in $DR_DIRS; do
  mkdir -p "$DR_ROOT/$d"
done
echo "$PROFILE" > "$DR_ROOT/.dr_profile"
ok "$(echo "$DR_DIRS" | wc -w | tr -d ' ') folders ready"

# ---------------------------------------------------------------------
step "7. Things that conflict with pyenv"
for p in $MUST_BE_ABSENT; do
  # /Applications/Python matches folders like "Python 3.12"
  if ls -d "$p"* >/dev/null 2>&1; then
    add_todo "Remove $p (it conflicts with pyenv). Not removed automatically."
    echo "    found: $p"
  fi
done
ok "check done"

# ---------------------------------------------------------------------
step "8. Tailscale (private network between your Macs)"
if [ -d /Applications/Tailscale.app ]; then
  ok "installed"
elif [ "$NEED_TAILSCALE" != "1" ]; then
  ok "optional for $PROFILE, skipping"
else
  add_todo "Install Tailscale from https://tailscale.com/download/mac (or the Mac App Store), and sign in with the same account on every Mac."
  echo "    not installed (see list at the end)"
fi

# ---------------------------------------------------------------------
echo
echo "================================================================"
echo "Setup finished for profile: $PROFILE"
if [ -n "$TODO" ]; then
  echo
  echo "Still to do by hand:"
  printf "%s" "$TODO"
fi
echo
echo "Next: reload your shell (exec zsh) or open a NEW terminal, then run:"
echo "    bash $HERE/verify.sh"
echo "================================================================"
