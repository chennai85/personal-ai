#!/bin/bash
# =====================================================================
# test_server.sh: test the monitor's web page with stand-ins
#
# Usage (any Mac, or Linux):   bash tests/test_server.sh
#
# Throwaway vault, made-up ledger, stand-in model server and Tailscale.
# Starts the page on 127.0.0.1 only. Never touches ~/vault, Ollama or Tailscale.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
PORT=11994; WEB=11993
export VAULT_DIR="$TMP/vault" DR_ROOT="$TMP/dr" DR_PROFILE="studio"
export MODEL_BASE_URL="http://127.0.0.1:$PORT" TAILSCALE_BIN="$TMP/tailscale"
export MONITOR_TICK=0.2 MONITOR_SNAPSHOT_EVERY=2
PASS=0; FAIL=0
check() {
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  PASS  $name"; PASS=$((PASS+1))
  else echo "  FAIL  $name"; FAIL=$((FAIL+1)); fi
}
has()   { grep -qF -- "$1" <<<"$2"; }
hasnt() { ! grep -qF -- "$1" <<<"$2"; }
fx()    { python3 "$HERE/tests/fixtures.py" "$@"; }
U="http://127.0.0.1:$WEB"
code()  { curl -s -o /dev/null -w '%{http_code}' "$@"; }
L="$VAULT_DIR/.agents/ledger.jsonl"

python3 "$HERE/tests/mock_ollama.py" "$PORT" "$TMP/methods.txt" & MOCK=$!
fx tailscale "$TMP/ts.json"
printf '#!/bin/bash\ncat "%s"\n' "$TMP/ts.json" > "$TAILSCALE_BIN"; chmod +x "$TAILSCALE_BIN"
mkdir -p "$VAULT_DIR/.agents"; chmod 700 "$VAULT_DIR" "$VAULT_DIR/.agents"
fx ledger clean "$L"; chmod 600 "$L"
fx report values-ok "$VAULT_DIR/.eval"; fx report side-ok "$VAULT_DIR/.eval"; fx report audit-ok "$DR_ROOT/scripts/audits"

python3 "$HERE/monitor.py" serve --bind 127.0.0.1 --port "$WEB" > "$TMP/serve.log" 2>&1 & SRV=$!
trap 'kill $MOCK $SRV 2>/dev/null; wait $MOCK $SRV 2>/dev/null; rm -rf "$TMP"' EXIT
for _ in $(seq 1 30); do [ "$(code "$U/")" = 200 ] && break; sleep 0.2; done

echo "==> where it listens"
OUT="$(python3 "$HERE/monitor.py" serve --dry-run --port "$WEB")"
check "this Mac + Tailscale address"   has "Would listen on: 127.0.0.1:$WEB 100.64.0.1:$WEB" "$OUT"
check "answers to its Tailscale name"  has "zenstudio" "$OUT"
for B in 0.0.0.0 :: 192.168.1.20 10.0.0.5 8.8.8.8; do
  OUT="$(python3 "$HERE/monitor.py" serve --bind "$B" --port "$WEB" --dry-run 2>&1)"; RC=$?
  check "refuses $B"                   test "$RC" = 2 -a -n "$(grep Refused <<<"$OUT")"
done
printf '{"BackendState": "Stopped", "Self": {"HostName": "zenstudio", "TailscaleIPs": ["100.64.0.1"]}}' > "$TMP/ts.json"
check "Tailscale down: this Mac only"  has "Would listen on: 127.0.0.1:$WEB"$'\n' "$(python3 "$HERE/monitor.py" serve --dry-run --port "$WEB")"
fx tailscale "$TMP/ts.json"
check "startup line says read-only"    has "Read-only" "$(cat "$TMP/serve.log")"

echo "==> the page"
OUT="$(curl -s -D - "$U/")"
check "page loads"                     has "<title>My Agents</title>" "$OUT"
check "no CDN: only its own scripts"   bash -c "! grep -qiE 'src=\"https?:|href=\"https?:' '$HERE/web/index.html'"
check "CSP: nothing by default"        has "Content-Security-Policy: default-src 'none'" "$OUT"
check "CSP: own scripts only"          has "script-src 'self'" "$OUT"
check "CSP: no framing"                has "frame-ancestors 'none'" "$OUT"
check "no caching"                     has "Cache-Control: no-store" "$OUT"
check "no CORS header"                 hasnt "Access-Control" "$OUT"
check "app.js is JavaScript"           has "text/javascript" "$(curl -s -D - -o /dev/null "$U/app.js")"
check "app.css is CSS"                 has "text/css" "$(curl -s -D - -o /dev/null "$U/app.css")"
check "page text only, never HTML"     bash -c "! grep -qE 'innerHTML|outerHTML|insertAdjacentHTML|document.write|eval\(' '$HERE/web/app.js'"

echo "==> the guards"
for M in POST PUT DELETE PATCH OPTIONS; do
  check "$M refused (405)"             test "$(code -X "$M" "$U/api/snapshot")" = 405
done
check "HEAD refused (405)"             test "$(code -I "$U/")" = 405
for P in /index.html /web/app.js /../monitor.py /%2e%2e/monitor.py /api/snapshot/../../monitor.py /monitor.py /.env /api; do
  check "no file: $P (404)"            test "$(code --path-as-is "$U$P")" = 404
done
check "unknown host refused (421)"     test "$(code -H 'Host: evil.example' "$U/")" = 421
check "rebinding name refused"         test "$(code -H 'Host: zenstudio.evil.example:8765' "$U/api/snapshot")" = 421
check "lookalike name refused"         test "$(code -H "Host: localhost.evil.example:$WEB" "$U/")" = 421
check "lookalike address refused"      test "$(code -H "Host: 127.0.0.1.evil.example" "$U/")" = 421
check "localhost name ok"              test "$(code -H "Host: localhost:$WEB" "$U/")" = 200
check "days=abc refused (400)"         test "$(code "$U/api/snapshot?days=abc")" = 400
check "days=0 refused"                 test "$(code "$U/api/snapshot?days=0")" = 400
check "days=91 refused"                test "$(code "$U/api/snapshot?days=91")" = 400
check "days=-1 refused"                test "$(code "$U/api/snapshot?days=-1")" = 400

echo "==> the snapshot"
JS="$(curl -s "$U/api/snapshot?days=7")"
check "valid JSON"                     python3 -c "import json,sys; json.loads(sys.argv[1])" "$JS"
check "same as the terminal view"      python3 -c "
import json,sys,subprocess
a=json.loads(sys.argv[1]); b=json.loads(subprocess.run([sys.executable,'$HERE/monitor.py','status','--json'],capture_output=True,text=True).stdout)
assert a['alerts']==b['alerts'] and a['agents']==b['agents'], 'differ'" "$JS"
check "agents counted"                 has '"runs": 2' "$JS"

echo "==> live: new rows arrive as they land"
curl -sN --max-time 4 "$U/api/events?days=7" > "$TMP/sse.txt" &
CURL=$!; sleep 1
python3 - "$L" <<'EOF'
import json, sys, time
L = sys.argv[1]
now = time.strftime("%Y-%m-%d %H:%M:%S")
rows = [
    {"time": now, "agent": "earnings", "event": "question", "chars": 41, "model": "qwen3.6:35b-a3b", "question": "SECRET-LIVE-Q"},
    {"time": now, "agent": "earnings", "event": "tool", "tool": "earnings_dates", "args": {"tickers": ["LIVEX", "SECRET-LIVE-ARG text"]}, "ok": True, "seconds": 0.4},
    {"time": now, "agent": "earnings", "event": "blocked", "tool": "earnings_dates", "args": "SECRET-LIVE-BLOCK", "reason": "not a ticker: 'SECRET-LIVE-R'"},
]
with open(L, "a") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
    f.flush()
    f.write('{"time": "' + now + '", "agent": "earnings", "event": "answer", "tool_calls"')   # half a line
    f.flush()
    time.sleep(1)
    f.write(': 2, "blocked": 1, "unverified": 0, "seconds": 1.9}\n')                        # the rest
EOF
wait $CURL 2>/dev/null
SSE="$(cat "$TMP/sse.txt")"
check "first a snapshot"               test "$(head -1 <<<"$SSE")" = "event: snapshot"
check "the question, as length"        has '"event": "question", "chars": 41' "$SSE"
check "the tool row, with its ticker"  has '"tickers": ["LIVEX"]' "$SSE"
check "the block, as a category"       has '"reason": "arguments refused"' "$SSE"
ROWS="$(grep -A1 '^event: row' <<<"$SSE" | grep '^data')"
check "four new rows sent"             test "$(grep -c . <<<"$ROWS")" = 4
check "half a line waits, then once"   test "$(grep -c '"event": "answer"' <<<"$ROWS")" = 1
check "fresh snapshot after new rows"  test "$(grep -c '^event: snapshot' <<<"$SSE")" -ge 2
check "and it includes them"           has 'LIVEX' "$(grep -A1 '^event: snapshot' <<<"$SSE" | tail -1)"
check "old rows not resent"            hasnt '"chars": 35' "$ROWS"
for S in SECRET-LIVE-Q SECRET-LIVE-ARG SECRET-LIVE-BLOCK SECRET-LIVE-R; do
  check "never sent: $S"               hasnt "$S" "$SSE"
done

echo "==> live: a replaced ledger, a missing ledger"
curl -sN --max-time 3 "$U/api/events?days=7" > "$TMP/sse2.txt" & CURL=$!; sleep 0.8
mv "$L" "$TMP/old-ledger"; sleep 0.6
python3 - "$L" <<'EOF2'
import json, sys, time
old = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600))
new = time.strftime("%Y-%m-%d %H:%M:%S")
with open(sys.argv[1], "w") as f:   # a replaced ledger: one row from before the page opened, one after
    f.write(json.dumps({"time": old, "agent": "earnings", "event": "question", "chars": 777, "model": "m"}) + "\n")
    f.write(json.dumps({"time": new, "agent": "life_admin", "event": "question", "chars": 12, "model": "m"}) + "\n")
EOF2
wait $CURL 2>/dev/null
ROWS2="$(grep -A1 '^event: row' "$TMP/sse2.txt" | grep '^data')"
check "keeps going, reads the new one" has '"agent": "life_admin", "event": "question"' "$ROWS2"
check "older rows not replayed"        hasnt '"chars": 777' "$ROWS2"
check "server still up"                test "$(code "$U/")" = 200

echo "==> limits"
PIDS=""
for _ in 1 2 3 4 5 6 7 8; do curl -sN --max-time 4 "$U/api/events" >/dev/null & PIDS="$PIDS $!"; done
sleep 1
check "9th live page refused (503)"    test "$(code --max-time 2 "$U/api/events")" = 503
check "snapshot still served"          test "$(code "$U/api/snapshot")" = 200
wait $PIDS 2>/dev/null
sleep 0.5
check "slots free again"               test "$(curl -s --max-time 1 -o /dev/null -w '%{http_code}' "$U/api/events")" = 200

echo "==> read-only, watched by Python's audit hook"
WATCH="$(python3 - "$HERE" "$((WEB+10))" <<'EOF' 2>&1
import sys, threading, time, urllib.request
sys.path.insert(0, sys.argv[1]); port = int(sys.argv[2])
import monitor, server
hits = []
def hook(ev, args):
    if ev == "open" and isinstance(args[1], str) and any(c in args[1] for c in "wax+"):
        hits.append(f"{ev} {args[0]} {args[1]}")
    elif ev in ("os.remove", "os.rename", "os.chmod", "os.mkdir", "os.rmdir", "os.truncate", "shutil.rmtree"):
        hits.append(f"{ev} {args[0]}")
sys.addaudithook(hook)
class A: bind = ["127.0.0.1"]; port = port; dry_run = False
threading.Thread(target=server.main, args=(A,), daemon=True).start(); time.sleep(0.5)
for p in ("/", "/app.js", "/app.css", "/api/snapshot?days=30"):
    urllib.request.urlopen(f"http://127.0.0.1:{port}{p}").read()
try:
    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/events", timeout=1.5).read()
except Exception:
    pass
print("WRITES:", len(hits), *hits)
EOF
)"
check "no writes, no changes"          has "WRITES: 0" "$WATCH"
SRC="$(grep -v '^\s*#' "$HERE/server.py")"
check "server opens no files itself"   test "$(grep -cE '(^|[^a-z_.])open\(' <<<"$SRC")" = 0
for W in .write_text .write_bytes .unlink .mkdir .chmod .rename os.remove; do
  check "server: no $W"                hasnt "$W" "$SRC"
done
check "GET only to the model server"   bash -c "! grep -qv '^GET ' '$TMP/methods.txt'"

echo "==> the service file"
OUT="$(bash "$HERE/install_service.sh" --print)"
check "LaunchAgent is valid XML"       python3 -c "import plistlib,sys; d=plistlib.loads(sys.argv[1].encode()); assert d['Label']=='com.drivingrange.monitor' and d['KeepAlive'] and d['RunAtLoad']" "$OUT"
check "runs monitor.py serve"          has "<string>serve</string>" "$OUT"
check "no address forced open"         hasnt "0.0.0.0" "$OUT"
check "install refuses off macOS"      bash -c "[ \"\$(uname)\" = Darwin ] || ! bash '$HERE/install_service.sh' install"

echo
echo "Results: $PASS pass · $FAIL fail"
[ "$FAIL" -eq 0 ]
