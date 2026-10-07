#!/bin/bash
# shellcheck disable=SC2034  # variables are used by setup.sh and verify.sh
# =====================================================================
# Driving Range Standard v1.1
# The single source of truth for how every machine is set up.
# setup.sh and verify.sh both read this file. Change values here only.
# =====================================================================

STANDARD_VERSION="1.1"

# Where all work lives
DR_ROOT="$HOME/driving-range"
DR_DIRS="ml-playground ai-experiments trading-tools aboutu scripts scratch"

# Python: one version, managed by pyenv. Per-project packages via uv.
PYTHON_VERSION="3.13.1"
BREW_TOOLS="git pyenv uv"

# Things that must NOT be on the machine (they fight with pyenv)
MUST_BE_ABSENT="/opt/anaconda3 /Library/Frameworks/Python.framework /Applications/Python"

# Minimum free disk on every machine
MIN_FREE_GB=50

# Where downloaded models are counted (Ollama + Hugging Face caches)
MODEL_DIRS="$HOME/.ollama/models $HOME/.cache/huggingface/hub"

# ---------------------------------------------------------------------
# Profiles: one per machine.
#   ROLE            what the machine is for
#   MAX_MODEL_GB    how much disk local models may use
#   NEED_TAILSCALE  1 = required, 0 = optional (WARN if missing)
#                   Tailscale = private network between your machines.
#                   Only the MacBook needs it now: it reaches the Studio away from home.
#   MODEL_URL       where this machine sends AI requests (MODEL_BASE_URL)
#
# The Mac Studio is the model server. The other Macs reach it over
# Tailscale. "mac-studio" is the Studio's Tailscale machine name;
# change it if yours is different.
# ---------------------------------------------------------------------
load_profile() {
  case "$1" in
    macbook)
      ROLE="coding and travel"
      MAX_MODEL_GB=10
      NEED_TAILSCALE=1
      MODEL_URL="http://mac-studio:11434"
      ;;
    imac)
      ROLE="desk work and learning"
      MAX_MODEL_GB=20
      NEED_TAILSCALE=0
      MODEL_URL="http://mac-studio:11434"
      ;;
    studio)
      ROLE="model server"
      MAX_MODEL_GB=200
      NEED_TAILSCALE=0
      MODEL_URL="http://localhost:11434"
      ;;
    *)
      return 1
      ;;
  esac
  return 0
}

# Lines that must be in ~/.zshrc (verify.sh checks each one exactly)
zshrc_required_lines() {
  echo 'export PYENV_ROOT="$HOME/.pyenv"'
  echo 'export PATH="$PYENV_ROOT/bin:$PATH"'
  echo 'eval "$(pyenv init - zsh)"'
  echo 'alias dr="cd ~/driving-range"'
}
