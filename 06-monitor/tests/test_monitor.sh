#!/bin/bash
# =====================================================================
# test_monitor.sh: test the monitor with stand-ins
#
# Usage (any Mac, or Linux):   bash tests/test_monitor.sh
#
# Uses a throwaway vault, made-up ledgers and reports, a stand-in model server
# and a stand-in Tailscale. Never touches ~/vault, Ollama or Tailscale.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
PORT=11996
export VAULT_DIR="$TMP/vault"
export DR_ROOT="$TMP/dr"
export DR_PROFILE="studio"
export MODEL_BASE_URL="http://127.0.0.1:$PORT"
export TAILSCALE_BIN="$TMP/tailscale"
SEEN="$TMP/methods.txt"
PASS=0; FAIL=0
check() {  # check "name" command...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  PASS  $name"; PASS=$((PASS+1))
  else echo "  FAIL  $name"; FAIL=$((FAIL+1)); fi
}
has()   { grep -qF -- "$1" <<<"$2"; }
hasnt() { ! grep -qF -- "$1" <<<"$2"; }
mon()   { python3 "$HERE/monitor.py" "$@"; }
fx()    { python3 "$HERE/tests/fixtures.py" "$@"; }
L="$VAULT_DIR/.agents/ledger.jsonl"
EVAL="$VAULT_DIR/.eval"
AUD="$DR_ROOT/scripts/audits"

python3 "$HERE/tests/mock_ollama.py" "$PORT" "$SEEN" & MOCK=$!
trap 'kill $MOCK 2>/dev/null; wait $MOCK 2>/dev/null; chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT
fx tailscale "$TMP/ts.json"
printf '#!/bin/bash\ncat "%s"\n' "$TMP/ts.json" > "$TAILSCALE_BIN"; chmod +x "$TAILSCALE_BIN"
sleep 1

approve() {  # an approved constitution, the way memory.py leaves it
  mkdir -p "$VAULT_DIR/values" "$VAULT_DIR/.values"
  printf '# My constitution\n- Never trade for me.\n' > "$VAULT_DIR/values/constitution.md"
  python3 -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" \
    "$VAULT_DIR/values/constitution.md" > "$VAULT_DIR/.values/approved.sha256"
  chmod 444 "$VAULT_DIR/values/constitution.md"
}

echo "==> an empty vault: nothing to show, nothing breaks"
mkdir -p "$VAULT_DIR"; chmod 700 "$VAULT_DIR"
OUT="$(mon status 2>&1)"; RC=$?
check "runs with no ledger"              has "nothing in the ledger yet" "$OUT"
check "no constitution: amber"           has "! no constitution yet" "$OUT"
check "tests never run: amber"           has "! values test: never run" "$OUT"
check "exit 0 (amber only)"              test "$RC" = 0

echo "==> healthy: approved constitution, clean ledger, passing tests"
approve
mkdir -p "$VAULT_DIR/.agents"; chmod 700 "$VAULT_DIR/.agents"
fx ledger clean "$L"; chmod 600 "$L"
fx report values-ok "$EVAL"; fx report side-ok "$EVAL"; fx report audit-ok "$AUD"
OUT="$(mon status 2>&1)"; RC=$?
check "all clear"                        has "✓ all clear" "$OUT"
check "exit 0"                           test "$RC" = 0
check "constitution approved"            has "constitution   approved, unchanged" "$OUT"
check "model server up, version"         has "up · Ollama 0.40.3" "$OUT"
check "loaded model shown"               has "loaded       qwen3.6:35b-a3b · 24.0 GB" "$OUT"
check "two runs this week"               has "earnings     2 runs (2 today) · 1 direct · 3 tool calls" "$OUT"
check "typical and slowest time"         has "typical 3.2 s · slowest 5.0 s" "$OUT"
check "old block outside the window"     has "blocked 0 · unverified 0 · unfinished 0" "$OUT"
check "30 days sees the old block"       has "blocked 1" "$(mon status --days 30 2>&1)"
check "tickers shown"                    has "earnings_dates ok · 1.2 s · CRWD NBIS" "$OUT"
check "question shown as length only"    has "question  35 chars" "$OUT"
check "test scores shown"                has "held the line 8/8" "$OUT"
check "side-door score shown"            has "model 6/6 · code 5/5 · values only 2" "$OUT"
check "verify counts shown"              has "42 pass · 0 warn · 0 fail" "$OUT"
check "machines from Tailscale"          has "zengaja        online" "$OUT"
check "offline machine, last seen"       has "zenmaruti      offline  macOS · 5 h ago" "$OUT"
check "no Tailscale addresses"           hasnt "100.64" "$OUT"
JS="$(mon status --json 2>&1)"
check "json is valid"                    python3 -c "import json,sys; json.loads(sys.argv[1])" "$JS"
check "json has no addresses"            hasnt "100.64" "$JS"

echo "==> a half-written last line is left alone"
fx ledger partial "$L"
OUT="$(mon status 2>&1)"
check "partial line not counted as bad"  hasnt "couldn't read" "$OUT"
check "still all clear"                  has "✓ all clear" "$OUT"

echo "==> trouble: blocks, an unverified date, a crash, a bad line, a second agent"
fx ledger trouble "$L"
OUT="$(mon status 2>&1)"; RC=$?
JS="$(mon status --json 2>&1)"
check "exit 1 when anything is red"      test "$RC" = 1
check "blocked: red"                     has "✗ earnings: 2 blocked call(s)" "$OUT"
check "unverified: red"                  has "✗ earnings: 1 unverified date(s)" "$OUT"
check "tool not ok: red"                 has "✗ earnings: 1 tool call(s) not ok" "$OUT"
check "run with no answer: amber"        has "! earnings: 1 run(s) with no answer" "$OUT"
check "bad line: amber"                  has "! ledger: 1 line(s) I couldn't read" "$OUT"
check "second agent listed"              has "life_admin   1 runs" "$OUT"
check "odd agent name counted, not shown" has "(unknown)    1 runs" "$OUT"
check "block reason as a category"       has "earnings_dates · arguments refused" "$OUT"
check "odd tool name hidden"             has "(hidden) · no such tool" "$OUT"
check "safe ticker still shown"          has "earnings_dates ok · 0.5 s · NVDA (+2 hidden)" "$OUT"
check "undeclared agent args hidden"     has "read_bills ok · 0.2 s (+1 hidden)" "$OUT"
for S in SECRET-AGENT SECRET-QUESTION SECRET-ARG SECRET-REASON SECRET-TICKER SECRET-FIELD "SECRET TOOL" SECRET-GARBAGE SECRET-PAYEE; do
  check "never shown: $S"                hasnt "$S" "$OUT$JS"
done

echo "==> two agents at once, ledger v2 (run ids, time zone)"
fx ledger v2 "$L"
OUT="$(mon status 2>&1)"
check "both runs finished"               has "unfinished 0" "$OUT"
check "no false alarm"                   hasnt "with no answer" "$OUT"
check "each agent has its run"           has "life_admin   1 runs" "$OUT"
check "same agent twice: 3 runs"         has "earnings     3 runs (3 today)" "$OUT"
check "time zone read as local time"     has "last 5 min ago" "$OUT"
fx ledger superseded "$L"
check "v1: unanswered question, then another: unfinished" has "unfinished 1" "$(mon status 2>&1)"

echo "==> the constitution, checked by the monitor itself"
fx ledger clean "$L"
chmod u+w "$VAULT_DIR/values/constitution.md"
echo "- Placing trades for me is fine." >> "$VAULT_DIR/values/constitution.md"
OUT="$(mon status 2>&1)"; RC=$?
check "changed: BIG RED FLAG"            has "✗ BIG RED FLAG: the constitution has changed" "$OUT"
check "changed: exit 1"                  test "$RC" = 1
check "the change itself never shown"    hasnt "Placing trades" "$OUT$(mon status --json 2>&1)"
mv "$VAULT_DIR/values/constitution.md" "$TMP/c.md"
check "missing after approval: red"      has "✗ BIG RED FLAG: the constitution is missing" "$(mon status 2>&1)"
rm "$TMP/c.md"; approve

echo "==> permissions loosened"
chmod 644 "$L"
check "ledger 644: red"                  has "✗ ledger permissions are 644" "$(mon status 2>&1)"
chmod 600 "$L"; chmod 755 "$VAULT_DIR"
check "vault 755: red"                   has "✗ vault permissions are 755" "$(mon status 2>&1)"
chmod 700 "$VAULT_DIR"

echo "==> the model server"
OUT="$(MOCK_MISSING=x MODEL_BASE_URL="http://127.0.0.1:1" mon status 2>&1)"
check "down: red"                        has "✗ model server not answering" "$OUT"
MOCK_MISSING=gemma4:e4b python3 "$HERE/tests/mock_ollama.py" $((PORT+1)) "$SEEN" & M2=$!; sleep 1
OUT="$(MODEL_BASE_URL="http://127.0.0.1:$((PORT+1))" mon status 2>&1)"
kill $M2; wait $M2 2>/dev/null
check "missing model: red"               has "✗ model missing: gemma4:e4b" "$OUT"
check "GET requests only"                bash -c "! grep -qv '^GET ' '$SEEN'"
check "and some were made"               test -s "$SEEN"

echo "==> test reports"
fx report values-miss "$EVAL"; fx report side-code "$EVAL"; fx report audit-fail "$AUD"
OUT="$(mon status 2>&1)"
check "values 7/8: red"                  has "✗ values test: held the line 7/8" "$OUT"
check "code guard slipped: red"          has "✗ side-door test: model 5/6 · code 4/5" "$OUT"
check "verify fails named"               has "failed: constitution, free disk" "$OUT"
check "answers never shown"              hasnt "SECRET-ANSWER" "$OUT"
fx report side-model "$EVAL"; fx report values-unscored "$EVAL"
OUT="$(mon status 2>&1)"
check "model slipped, code held: amber"  has "! side-door test: model 5/6 · code 5/5" "$OUT"
check "unscored values: amber"           has "! values test: not scored" "$OUT"
rm -f "$EVAL"/values-*; fx report old "$EVAL"
check "20-day-old report: amber"         has "! values test: last run 20 days ago" "$(mon status 2>&1)"

echo "==> Tailscale"
OUT="$(TAILSCALE_BIN="$TMP/nope" mon status 2>&1)"
check "can't read Tailscale: amber"      has "! can't read Tailscale status" "$OUT"
printf '{"BackendState": "Stopped", "Self": {"HostName": "zenstudio"}}' > "$TMP/ts.json"
check "Tailscale stopped: amber"         has "! Tailscale isn't running" "$(mon status 2>&1)"
fx tailscale "$TMP/ts.json"

echo "==> read-only"
fingerprint() { find "$VAULT_DIR" "$DR_ROOT" -exec stat -c '%n %a %s %Y' {} + 2>/dev/null \
  || find "$VAULT_DIR" "$DR_ROOT" -exec stat -f '%N %Lp %z %m' {} +; }
fx ledger trouble "$L"
BEFORE="$(fingerprint)$(cat "$L")"
mon status >/dev/null 2>&1; mon status --json >/dev/null 2>&1; mon status --days 30 >/dev/null 2>&1
check "vault unchanged after 3 runs"     test "$BEFORE" = "$(fingerprint)$(cat "$L")"
chmod -R a-w "$VAULT_DIR"
check "runs on a read-only vault"        has "Agents" "$(mon status 2>&1)"
chmod -R u+w "$VAULT_DIR"
# Python's audit hook sees every file open and file change, even as root (where chmod can't stop writes)
WATCH="$(python3 - "$HERE" <<'EOF' 2>&1
import sys
hits = []
def hook(ev, args):
    if ev == "open" and isinstance(args[1], str) and any(c in args[1] for c in "wax+"):
        hits.append(f"{ev} {args[0]} {args[1]}")
    elif ev in ("os.remove", "os.rename", "os.chmod", "os.mkdir", "os.rmdir", "os.truncate", "shutil.rmtree"):
        hits.append(f"{ev} {args[0]}")
sys.path.insert(0, sys.argv[1])
import monitor
sys.addaudithook(hook)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    monitor.render(monitor.snapshot(days=30))
print("WRITES:", len(hits), *hits)
EOF
)"
check "audit hook: no writes, no changes" has "WRITES: 0" "$WATCH"
SRC="$(grep -v '^\s*#' "$HERE/monitor.py")"
check "one open(), read-binary"          test "$(grep -cE '(^|[^a-z_.])open\(' <<<"$SRC")" = 1
check "it opens with 'rb'"               has 'with open(path, "rb")' "$SRC"
for W in .write_text .write_bytes .unlink .mkdir .chmod .rename os.remove shutil.rm "method=\"POST\""; do
  check "no $W"                          hasnt "$W" "$SRC"
done

echo "==> one source of truth: the monitor and memory.py agree on the vault"
if command -v uv >/dev/null 2>&1; then
  A="$(cd "$HERE/../03-memory" && uv run --quiet --no-project --with numpy python3 -c 'import memory; print(memory.S["vault"])' 2>/dev/null)"
  B="$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import monitor; print(monitor.S['vault'])")"
  check "same vault path"                test -n "$A" -a "$A" = "$B"
else
  echo "  SKIP  same vault path (uv not found)"
fi

echo
echo "Results: $PASS pass · $FAIL fail"
[ "$FAIL" -eq 0 ]
