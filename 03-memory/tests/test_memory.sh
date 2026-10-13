#!/bin/bash
# =====================================================================
# test_memory.sh: test the memory plumbing without the real model
#
# Usage (any Mac, or Linux):   bash tests/test_memory.sh
#
# Uses a throwaway vault and a stand-in embedding server, so it never
# touches ~/vault or the Studio. Prints PASS / FAIL per check.
# =====================================================================

set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
PORT=11999
export VAULT_DIR="$TMP/vault"
export MODEL_BASE_URL="http://127.0.0.1:$PORT"
PASS=0; FAIL=0
check() {  # check "name" command...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "  PASS  $name"; PASS=$((PASS+1))
  else echo "  FAIL  $name"; FAIL=$((FAIL+1)); fi
}
mem() { (cd "$HERE" && uv run --quiet memory.py "$@"); }

python3 "$HERE/tests/mock_ollama.py" "$PORT" & MOCK=$!
trap 'kill $MOCK 2>/dev/null; rm -rf "$TMP"' EXIT
sleep 1

echo "==> setup"
bash "$HERE/vault_setup.sh" >/dev/null
check "vault created"            test -d "$VAULT_DIR/me"
check "vault is 700"             test "$(stat -c %a "$VAULT_DIR" 2>/dev/null || stat -f %Lp "$VAULT_DIR")" = 700
(cd "$HERE/tests" && uv run --quiet make_samples.py "$VAULT_DIR") >/dev/null

echo "==> ingest"
OUT="$(mem ingest)"
check "pdf indexed"              grep -q "new     inbox/electric-bill-sept.pdf" <<<"$OUT"
check "docx indexed"             grep -q "new     inbox/auto-renewal.docx" <<<"$OUT"
check "email indexed"            grep -q "new     inbox/reminder.eml" <<<"$OUT"
check "markdown indexed"         grep -q "new     inbox/trip-ideas.md" <<<"$OUT"
check "scan flagged, not indexed" grep -q "scan    inbox/scanned-receipt.pdf" <<<"$OUT"
check "template skipped (_name)" bash -c "! grep -q '_template.md' <<<\"\$1\"" _ "$OUT"
check "index file exists"        test -f "$VAULT_DIR/.index/memory.db"

echo "==> search"
check "exact words: kWh -> bill pdf, page 2" bash -c "mem(){ cd '$HERE' && uv run --quiet memory.py \"\$@\"; }; mem search kWh --mode words | head -1 | grep -q 'electric-bill-sept.pdf · p.2'"
check "meaning: 'invoice' -> bill" bash -c "cd '$HERE' && uv run --quiet memory.py search 'when is the invoice due' --mode meaning | head -1 | grep -q electric-bill"
check "meaning: 'doctor' -> email" bash -c "cd '$HERE' && uv run --quiet memory.py search 'doctor visit' | head -1 | grep -q reminder.eml"
check "docx table text searchable" bash -c "cd '$HERE' && uv run --quiet memory.py search deductible | head -1 | grep -q auto-renewal.docx"
check "found by both"            bash -c "cd '$HERE' && uv run --quiet memory.py search 'Kyoto temples' | head -1 | grep -q 'meaning+words'"

echo "==> part 3: cleaner passages"
check "repeated PDF header stripped" bash -c "cd '$HERE' && ! uv run --quiet memory.py search 'Sample Bank Year-End Summary' --mode words -k 10 | grep -q 'Includes charges from January'"
check "page with the total ranks first" bash -c "cd '$HERE' && uv run --quiet memory.py search 'total spending 2025' | head -1 | grep -q 'year-end-summary.pdf · p.1'"
check "blank template lines not indexed" bash -c "cd '$HERE' && ! uv run --quiet memory.py search 'comfort ranges' --mode words | grep -q 'me/money.md'"
echo "- Comfort ranges note: a big trip is fine up to a set amount." >> "$VAULT_DIR/me/money.md"
mem ingest >/dev/null
check "filled-in line is indexed"  bash -c "cd '$HERE' && uv run --quiet memory.py search 'comfort ranges' --mode words | head -1 | grep -q 'me/money.md'"

echo "==> part 3: ask"
OUT="$(mem ask 'what was my total spending in 2025')"
check "answer cites a passage"   grep -q "\[1\]" <<<"$OUT"
check "sources listed with page" grep -q "\[1\] inbox/year-end-summary.pdf p.1" <<<"$OUT"
check "timing reported"          grep -q "first word" <<<"$OUT"

echo "==> re-ingest, change, delete"
OUT="$(mem ingest)"
check "nothing re-embedded when unchanged" grep -q "new 0 · changed 0" <<<"$OUT"
echo "Iceland in winter: northern lights." >> "$VAULT_DIR/inbox/trip-ideas.md"
rm "$VAULT_DIR/inbox/reminder.eml"
OUT="$(mem ingest)"
check "changed file re-indexed"  grep -q "changed inbox/trip-ideas.md" <<<"$OUT"
check "deleted file removed"     grep -q "removed inbox/reminder.eml" <<<"$OUT"
check "deleted file not found"   bash -c "cd '$HERE' && ! uv run --quiet memory.py search physician --mode words | grep -q reminder.eml"
check "new text found"           bash -c "cd '$HERE' && uv run --quiet memory.py search 'northern lights' | head -1 | grep -q trip-ideas.md"

echo "==> rebuild"
BEFORE="$(mem search 'when is the invoice due' | head -1)"
mem rebuild >/dev/null
AFTER="$(mem search 'when is the invoice due' | head -1)"
check "same top answer after rebuild" test "$BEFORE" = "$AFTER"

echo "==> reader version change re-reads files"
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"UPDATE meta SET value='1' WHERE key='chunker'\"); c.commit()" "$VAULT_DIR/.index/memory.db"
OUT="$(mem ingest)"
check "old index re-read after upgrade" grep -q "Re-reading every file" <<<"$OUT"
python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"DELETE FROM meta WHERE key='chunker'\"); c.commit()" "$VAULT_DIR/.index/memory.db"
OUT="$(mem ingest)"
check "index with no version (built before v2) re-read" grep -q "v1 -> v2" <<<"$OUT"

echo "==> model guard"
check "refuses to mix embedding models" bash -c "cd '$HERE' && ! MODEL_EMBED=other-model uv run --quiet memory.py ingest"

echo
echo "pass=$PASS fail=$FAIL"
exit "$FAIL"
