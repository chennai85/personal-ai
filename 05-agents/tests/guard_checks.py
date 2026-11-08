"""Direct checks on guarded_call: guards a single-agent, read-only setup never exercises."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402
agent.LEDGER = agent.AGENTS_DIR / "guard-checks.jsonl"   # its own ledger: these calls have no question

ran = []
agent.TOOLS["other_read"] = {"tier": "read", "check": agent.check_nothing,
                             "run": lambda: ran.append("other_read") or {}, "what": "", "schema": {}}
agent.TOOLS["fake_send"] = {"tier": "act", "check": agent.check_nothing,
                            "run": lambda: ran.append("fake_send") or {}, "what": "", "schema": {}}

_, why = agent.guarded_call("earnings", "other_read", {})
print("OFF_LIST blocked:", why)
agent.AGENTS["earnings"]["tools"].append("fake_send")      # even if someone adds it to the list
_, why = agent.guarded_call("earnings", "fake_send", {})
print("ACT_TIER blocked:", why)
print("RAN", ", ".join(ran) or "none")
w = agent.tool_read_watchlist()
print("WATCHLIST", w["tickers"], "skipped", w.get("skipped_lines", 0))

import datetime as dt  # noqa: E402
import json  # noqa: E402
for ts in (1801170000, 1793656800,                       # Apple: next (estimate), last call
           int(dt.datetime(2026, 11, 19, 0, 0, tzinfo=agent.MARKET_TZ).timestamp()),
           int(dt.datetime(2026, 11, 19, 8, 0, tzinfo=agent.MARKET_TZ).timestamp())):
    print("TIME", *agent.market_time(ts))
order = ["NVDA", "ZZZZ", "AAPL", "MSFT", "AMD"]
got = [r["ticker"] for r in agent.tool_earnings_dates(order)["results"]]
print("ORDER", "ok" if got == order else got)

# The real Yahoo path, fed Apple's actual calendarEvents answer (Studio, 2026-11-07),
# through a stand-in yfinance, so the parsing is tested without the internet.
import os, types  # noqa: E401,E402
APPLE = {"earningsDate": [1801170000], "earningsCallDate": [1793656800], "isEarningsDateEstimate": True,
         "earningsAverage": 2.91742, "revenueAverage": 156459329920}
CONFIRMED = dict(APPLE, isEarningsDateEstimate=False)


class FakeTicker:
    def __init__(self, sym):
        self.sym = sym
        if sym == "OLDYF":                         # a yfinance without _quote: fallback path
            self.calendar = {"Earnings Date": [dt.date(2027, 1, 28)]}
            return
        payload = APPLE if sym == "AAPL" else CONFIRMED
        self._quote = types.SimpleNamespace(_fetch=lambda m: {"quoteSummary": {"result": [
            {"calendarEvents": {"earnings": payload}}]}})


sys.modules["yfinance"] = types.SimpleNamespace(Ticker=FakeTicker)
os.environ.pop("EARNINGS_FAKE", None)
for sym in ("AAPL", "CONF", "OLDYF"):
    print("RAW", sym, json.dumps(agent.fetch_earnings(sym)))

# Ledger v2: a tool that breaks is recorded and the run goes on; a free-text reason never lands
agent.TOOLS["boom_read"] = {"tier": "read", "check": agent.check_nothing, "show": (),
                            "run": lambda: (_ for _ in ()).throw(ValueError("SECRET-CRASH")), "what": "", "schema": {}}
agent.AGENTS["earnings"]["tools"].append("boom_read")
res, why = agent.guarded_call("earnings", "boom_read", {}, "abc123")
print("CRASH result", json.dumps(res))
last = json.loads(agent.LEDGER.read_text().splitlines()[-1])
print("CRASH row tool", last["tool"], "ok", last["ok"], "error", last["error"])
agent.ledger("earnings", "blocked", "abc123", tool=None, reason="not a ticker: 'SECRET-REASON'")
print("REASON", json.loads(agent.LEDGER.read_text().splitlines()[-1])["reason"])

# Only declared arguments reach the ledger; a model-made tool name that isn't a plain name doesn't either
agent.TOOLS["two_args"] = {"tier": "read", "show": ("tickers",), "what": "", "schema": {},
                           "check": lambda a: ({"tickers": ["NVDA"], "note": "SECRET-NOTE"}, None),
                           "run": lambda tickers, note: {}}
agent.AGENTS["earnings"]["tools"].append("two_args")
agent.guarded_call("earnings", "two_args", {}, "abc123")
last = json.loads(agent.LEDGER.read_text().splitlines()[-1])
print("SHOWN", sorted(last["args"]), "hidden", last["args_hidden"])
agent.guarded_call("earnings", "Send Email Now!", {}, "abc123")
last = json.loads(agent.LEDGER.read_text().splitlines()[-1])
print("ODD NAME", last["tool"], last["reason"])
