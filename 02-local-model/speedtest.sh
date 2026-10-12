#!/bin/bash
# =====================================================================
# speedtest.sh: measure how fast the model server really is
#
# Usage (any Mac):   bash speedtest.sh [model ...]
#   With no arguments it tests MODEL_MAIN and MODEL_FAST from standard.sh.
#
# Sends the same short task to each model at $MODEL_BASE_URL and reports:
#   load     seconds to load the model into memory (0 if already loaded)
#   read     how fast it reads your prompt (tokens/sec)
#   write    how fast it writes the answer (tokens/sec)  <- the one you feel
#   total    seconds from request to complete answer
# Results are saved to ~/driving-range/scripts/audits/.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=../01-environment/standard.sh
. "$HERE/../01-environment/standard.sh"

URL="${MODEL_BASE_URL:-http://localhost:$OLLAMA_PORT}"
if [ "$#" -gt 0 ]; then MODELS="$*"; else MODELS="$MODEL_MAIN $MODEL_FAST"; fi
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
PROFILE="${DR_PROFILE:-unknown}"

PROMPT="You are helping with personal admin. In exactly three short bullet points, explain why someone should keep a list of their monthly subscriptions and review it every quarter."

if ! curl -s -m 5 "$URL/api/version" >/dev/null; then
  echo "Cannot reach the model server at $URL"
  echo "Is the Mac Studio awake, Tailscale connected, and server_setup.sh done?"
  exit 1
fi

NOW="$(date '+%Y-%m-%d %H:%M:%S')"
REPORT="# speedtest host=$HOST profile=$PROFILE server=$URL time=$NOW standard=v$STANDARD_VERSION
model|load_s|read_tok_s|write_tok_s|answer_tokens|total_s"

for m in $MODELS; do
  echo "Testing $m ..." >&2
  BODY=$(python3 -c 'import json,sys; print(json.dumps({"model":sys.argv[1],"prompt":sys.argv[2],"stream":False,"think":False,"options":{"temperature":0,"num_predict":200}}))' "$m" "$PROMPT")
  RESP=$(curl -s -m 600 "$URL/api/generate" -H 'Content-Type: application/json' -d "$BODY")
  LINE=$(printf '%s' "$RESP" | python3 -c '
import json, sys
name = sys.argv[1]
try:
    r = json.load(sys.stdin)
except Exception:
    print(f"{name}|error: no valid reply|||"); sys.exit()
if "error" in r:
    err = r["error"]
    print(f"{name}|error: {err}|||"); sys.exit()
ns = 1e9
load = r.get("load_duration", 0) / ns
pe_n, pe_d = r.get("prompt_eval_count", 0), r.get("prompt_eval_duration", 0) / ns
ev_n, ev_d = r.get("eval_count", 0), r.get("eval_duration", 0) / ns
total = r.get("total_duration", 0) / ns
read = pe_n / pe_d if pe_d else 0
write = ev_n / ev_d if ev_d else 0
print(f"{name}|{load:.1f}|{read:.0f}|{write:.1f}|{ev_n}|{total:.1f}")
' "$m")
  REPORT="$REPORT
$LINE"
done

echo
if command -v column >/dev/null; then printf "%s\n" "$REPORT" | column -t -s "|"; else printf "%s\n" "$REPORT"; fi
mkdir -p "$DR_ROOT/scripts/audits"
OUT="$DR_ROOT/scripts/audits/speedtest_${PROFILE}_${HOST}_$(date +%Y%m%d_%H%M%S).txt"
printf "%s\n" "$REPORT" > "$OUT"
echo
echo "Saved: $OUT"
echo "Tip: run it twice. The first run includes loading the model; the second shows everyday speed."
