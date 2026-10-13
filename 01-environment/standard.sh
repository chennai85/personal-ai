#!/bin/bash
# shellcheck disable=SC2034  # variables are used by setup.sh and verify.sh
# =====================================================================
# Driving Range Standard v1.3
# The single source of truth for how every machine is set up.
# setup.sh and verify.sh both read this file. Change values here only.
# =====================================================================

STANDARD_VERSION="1.3"

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
# Model server (Step 2). Runs on the Mac Studio only.
# Why these models: personal-ai/02-local-model/WHY-THIS-MODEL.md
# To switch models, change the tags here and re-run server_setup.sh.
# ---------------------------------------------------------------------
MODEL_MAIN="qwen3.6:35b-a3b"     # main model: depth
MODEL_FAST="gemma4:e4b"          # fast model: quick tasks, fallback
MODEL_EMBED="qwen3-embedding:0.6b"  # embedding model: turns text into meaning (Step 3)
OLLAMA_PORT=11434
OLLAMA_LISTEN="0.0.0.0"          # accept requests from other Macs (see README security note)
OLLAMA_CONTEXT_LENGTH=32768      # how much text one conversation can hold
OLLAMA_KEEP_ALIVE="30m"          # keep a model in memory 30 minutes after last use
OLLAMA_NUM_PARALLEL=2            # answer two requests at once per model
OLLAMA_MAX_LOADED_MODELS=3       # main + fast + embedding can all stay loaded (v1.3: was 2)

# ---------------------------------------------------------------------
# Memory (Step 3). The vault lives on the Mac Studio only.
# It holds my data, so it must never be inside a git repo.
# Why this design: personal-ai/03-memory/WHY-THIS-DESIGN.md
# ---------------------------------------------------------------------
VAULT_DIR="${VAULT_DIR:-$HOME/vault}"  # my files: notes, documents, decisions
VAULT_INDEX="$VAULT_DIR/.index/memory.db"  # search index, rebuilt from the files
MEMORY_CHUNK_WORDS=500           # passage size for search
MEMORY_CHUNK_OVERLAP=80          # words shared between neighbouring passages

# ---------------------------------------------------------------------
# Profiles: one per machine.
#   ROLE            what the machine is for
#   MAX_MODEL_GB    how much disk local models may use
#   NEED_TAILSCALE  1 = required, 0 = optional (WARN if missing)
#                   Tailscale = private network between your machines.
#   MODEL_URL       where this machine sends AI requests (MODEL_BASE_URL)
#
# The Mac Studio is the model server. The other Macs reach it over
# Tailscale. "zenstudio" is the Studio's Tailscale machine name
# (shown in the Tailscale app); change it if yours is different.
# ---------------------------------------------------------------------
load_profile() {
  case "$1" in
    macbook)
      ROLE="coding and travel"
      MAX_MODEL_GB=10
      NEED_TAILSCALE=1
      MODEL_URL="http://zenstudio:11434"
      ;;
    imac)
      ROLE="desk work and learning"
      MAX_MODEL_GB=20
      NEED_TAILSCALE=1
      MODEL_URL="http://zenstudio:11434"
      ;;
    studio)
      ROLE="model server"
      MAX_MODEL_GB=200
      NEED_TAILSCALE=1
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
