# Step 5: First Agents

Until now, the AI could only read my files and answer. An agent can use tools. So this step starts with the smallest useful agent I could think of, and puts the guards in place before it does anything bigger.

**Part 1: the earnings-date agent.** Ask it when companies report earnings. It looks up the dates and tells me, with the facts printed by the code underneath.

```bash
uv run agent.py earnings "When do NVDA, AAPL and MSFT report?"
```

First real run on the Studio, Oct 28 2026 (before the estimate fix):

```
MSFT: 2026-10-28 (today)
AAPL: 2026-11-02
NVDA: 2026-11-17

Facts  (from the tool, printed by the code: check these, not the sentence)
  Ticker  Earnings date                  In  Note
  MSFT    2026-10-28                    0 d
  AAPL    2026-11-02                    5 d
  NVDA    2026-11-17                   20 d

(1 tool call(s) · 1.4 s · qwen3.6:35b-a3b · ledger: ~/vault/.agents/ledger.jsonl)
```

All three matched the companies' own announcements. 11.2 s the first time (the model loading), 1.4 s after.

Since Nov 7 each row also says **confirmed** (with *before open* / *after close*), **Yahoo's estimate, not announced**, or **window, not confirmed**.

Research only. It never says buy, sell or hold. I make the calls.

---

## How it works

```
my question
   │
   ▼
constitution check (Step 4)  ── changed? → BIG RED FLAG, nothing runs
   │
   ▼
model (Qwen 3.6) ── "call earnings_dates with [NVDA, AAPL]"
   │
   ▼
GUARD (code)  ── tool exists? on this agent's list? read-only tier? tickers look like tickers? under budget?
   │                 no → BLOCKED, written in the ledger, model told why
   ▼
tool runs ── Yahoo Finance → dates, days until, window or confirmed
   │
   ▼
model writes one line per ticker
   │
   ▼
code prints the facts table + checks every date in the answer came from the tool
```

The model chooses. The code decides. The tool fetches. The code prints the facts.

| Piece | In this step |
|---|---|
| Agent | `earnings`: a purpose and a list of two tools. Nothing else |
| Tools | `earnings_dates` (Yahoo Finance via yfinance: dates, estimate or confirmed, time of day; tickers fetched 6 at a time), `read_watchlist` (`~/vault/trading/watchlist.md`, at most 25 tickers, and it says so when there are more). Both **read** tier |
| Tiers | `read` allowed. `draft` and `act` not allowed in Phase 1. Send, delete, pay and trade aren't built at all |
| Ledger | `~/vault/.agents/ledger.jsonl`: every question (length only, not the words), every tool call, every block. Private (600) |

## Guards, in code

| Guard | What it stops | Tested by |
|---|---|---|
| Constitution check first | An agent running under changed rules | Add a line → red flag, exit 2, ledger unchanged |
| Tool must exist | A made-up tool (`send_email`) | Stand-in model asks for it → BLOCKED |
| Tool must be on this agent's list | One agent borrowing another's tools | Direct check |
| Read tier only | Any tool that writes, sends or acts | Direct check, even when added to the list |
| Arguments checked | `../etc/passwd` as a ticker | BLOCKED before the tool runs |
| Budget: 4 tool calls per question | A model stuck in a loop | Stand-in loops → stopped at 4 |
| Dates must come from the tool | A date the model made up | Flagged with CHECK |
| No tool called = flagged | An answer from the model's own memory | Flagged |
| Watchlist reads tickers only | Words in my files becoming instructions or tickers ("ignore your rules…") | Prose lines skipped, never read as tickers |
| Estimates are labelled | A guess shown as a fact | Yahoo's `isEarningsDateEstimate`, tested on Apple's real answer |
| The cap says so | Tickers past 25 vanishing silently | 28 tickers → NOTE "only the first 25 of 28" |

## Run it (Mac Studio)

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
cd 05-agents
bash tests/test_agent.sh                                  # 56 checks, stand-in model, made-up dates
uv run agent.py tools                                     # what it can and can't do
uv run agent.py earnings --direct NVDA AAPL MSFT          # facts only, no model: the baseline
uv run agent.py earnings "When do NVDA, AAPL and MSFT report?"
uv run agent.py ledger                                    # what just happened
```

The first run installs yfinance (a few seconds). The first answer may be slow if Qwen isn't loaded yet.

**Optional: a watchlist.** One ticker per line, or a few per line with commas. `#` starts a comment.

```bash
mkdir -p ~/vault/trading
printf 'NVDA\nAAPL, MSFT\n' > ~/vault/trading/watchlist.md
uv run agent.py earnings "When does my watchlist report?"
```

## Commands

| Command | Does |
|---|---|
| `earnings "QUESTION"` | The agent: model picks tools, code guards them, facts printed underneath |
| `earnings --direct T1 T2 …` | No model. Same tool, same guards on tickers, same facts table. To compare against the agent |
| `tools` | Every agent, its tools, each tool's tier |
| `ledger [-n 20]` | The last lines of the ledger |

## Tested (stand-in model)

`bash tests/test_agent.sh`: 56 checks, all pass. Never touches `~/vault`, Yahoo or the Studio. `03-memory/tests/test_memory.sh` still passes 79/79.

To check the tests themselves, I broke each guard on purpose and re-ran them. Every break was caught. The first time, removing the "on this agent's list" check changed nothing: with one agent, every tool is on its list. That check is now tested directly.

## What the real runs found

| Run | Found | Fixed |
|---|---|---|
| Oct 28, 3 tickers | Right dates, but Yahoo's day has no hour: "MSFT 0 d" didn't say "after close" | Confirmed dates now show before open / after close |
| Nov 7, my 24-ticker watchlist | MSFT and AAPL showed late-January dates as if certain. Yahoo's raw answer says `"isEarningsDateEstimate": true`; yfinance's `.calendar` drops it | Read the raw answer; estimates labelled |
| Nov 7 | 24 tickers, cap of 25: two more and some would vanish without a word | A NOTE when the watchlist is cut |
| Nov 7 | 21 s for 24 tickers, one lookup after another | Lookups 6 at a time |
| Nov 7 | The model's sentence put AAPL (82 d) above MSFT (81 d) | Nothing to fix: that's why the code prints the table |

The guard checked that every date came from the source. It didn't check how sure the source was.

## Not tested here

- Real Yahoo data and real timing: the cloud workspace can't reach Yahoo. That's the first run on the Studio.
- How Qwen actually picks tools. The stand-in follows a script. The real model may call a tool twice, or skip it; the guards and the CHECK lines are there for that.
- Yahoo's dates are Yahoo's. A date can move. The tool shows a window when Yahoo only has a window.

## Files

| File | What |
|---|---|
| `agent.py` | The agent, tools, guards, ledger |
| `tests/test_agent.sh` | 56 checks with a stand-in model and made-up dates |
| `tests/mock_agent_ollama.py` | Stand-in model that calls tools in fixed ways (and misbehaves on purpose) |
| `tests/guard_checks.py` | Direct checks: guards a single read-only agent never reaches, time-of-day conversion, and the Yahoo parser fed Apple's real answer |
| `WHY-THIS-DESIGN.md` | The decisions, and why |
