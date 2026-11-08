"""Ledger v2 checks: read a ledger written by the test run and print one line per fact.

    python3 ledger_checks.py LEDGER
"""
import datetime as dt
import json
import re
import sys

KINDS = {"no such tool", "not on this agent's list", "tool tier not allowed", "arguments refused",
         "tool budget reached", "refused"}
rows = [json.loads(line) for line in open(sys.argv[1])]
text = open(sys.argv[1]).read()


def say(name, ok):
    print(f"{name}: {'yes' if ok else 'NO'}")


say("every row v2", all(r.get("v") == 2 for r in rows))
say("every time has a zone", all(dt.datetime.fromisoformat(r["time"]).tzinfo is not None for r in rows))
say("every row has a run id", all(re.fullmatch(r"[0-9a-f]{6}", str(r.get("run"))) for r in rows))

questions = [r["run"] for r in rows if r["event"] == "question"]
answers = {r["run"] for r in rows if r["event"] in ("answer", "error")}
say("one run per question", len(questions) == len(set(questions)) and len(questions) > 5)
say("every question has its own answer or error", all(q in answers for q in questions))
say("every tool row belongs to a question", all(r["run"] in questions for r in rows if r["event"] in ("tool", "blocked")))
say("direct runs have their own id", all(r["run"] not in questions for r in rows if r["event"] == "direct"))

blocked = [r for r in rows if r["event"] == "blocked"]
say("block reasons are kinds only", bool(blocked) and all(r["reason"] in KINDS for r in blocked))
say("blocked rows keep no arguments", all("args" not in r for r in blocked))
say("send_email recorded as no such tool", any(r.get("tool") == "send_email" and r["reason"] == "no such tool" for r in blocked))
say("bad ticker recorded as arguments refused", any(r["reason"] == "arguments refused" for r in blocked))
say("budget recorded", any(r["reason"] == "tool budget reached" for r in blocked))
say("what the model sent is not in the ledger", "passwd" not in text and "someone@example.com" not in text)

tools = [r for r in rows if r["event"] == "tool"]
say("tool rows show declared args only", all(set(r["args"]) <= {"tickers"} for r in tools))
say("watchlist reads show no args", all(r["args"] == {} for r in tools if r["tool"] == "read_watchlist"))
say("tickers still shown", any(r["args"].get("tickers") == ["NVDA", "AAPL"] for r in tools))
