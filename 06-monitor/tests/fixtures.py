"""Write made-up ledgers, test reports and Tailscale status for the monitor tests.

    python3 fixtures.py ledger  KIND  PATH      KIND: clean | trouble | v2 | superseded | partial
    python3 fixtures.py report  KIND  FOLDER    KIND: values-ok | values-miss | values-unscored |
                                                      side-ok | side-code | side-model | old |
                                                      audit-ok | audit-fail
    python3 fixtures.py tailscale PATH

Times are relative to now, so the tests never go stale. Private-looking text is planted on
purpose (SECRET-*); the tests check it never reaches the monitor's output.
"""
import datetime as dt
import json
import sys
from pathlib import Path

NOW = dt.datetime.now()


def t(minutes_ago):
    return (NOW - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")


def row(minutes_ago, agent, event, **f):
    return json.dumps({"time": t(minutes_ago), "agent": agent, "event": event, **f})


def ledger(kind, path):
    q = dict(chars=35, model="qwen3.6:35b-a3b")
    clean = [
        row(3000, "earnings", "direct", tickers=["NVDA", "AAPL", "MSFT"]),                      # 2 days ago
        row(60, "earnings", "question", **q),
        row(59.9, "earnings", "tool", tool="earnings_dates", args={"tickers": ["NVDA", "AAPL"]}, ok=True, seconds=0.67),
        row(59.8, "earnings", "answer", tool_calls=1, blocked=0, unverified=0, seconds=1.4),
        row(30, "earnings", "question", **q),
        row(29.9, "earnings", "tool", tool="read_watchlist", args={}, ok=True, seconds=0.01),
        row(29.8, "earnings", "tool", tool="earnings_dates", args={"tickers": ["CRWD", "NBIS"]}, ok=True, seconds=1.2),
        row(29.7, "earnings", "answer", tool_calls=2, blocked=0, unverified=0, seconds=5.0),
        row(20000, "earnings", "question", **q),                                                # 14 days ago: outside 7
        row(19999, "earnings", "blocked", tool="send_email", args="{}", reason="no such tool: send_email"),
        row(19998, "earnings", "answer", tool_calls=1, blocked=1, unverified=0, seconds=2.0),
    ]
    clean.sort(key=lambda l: json.loads(l)["time"])
    if kind == "clean":
        lines = clean
    elif kind == "trouble":
        lines = clean + [
            # a blocked call whose arguments and reason carry private-looking text
            row(25, "earnings", "question", chars=80, model="qwen3.6:35b-a3b", question="SECRET-QUESTION what is my balance"),
            row(24.9, "earnings", "blocked", tool="earnings_dates",
                args="{'tickers': ['SECRET-ARG my account number']}", reason="not a ticker: 'SECRET-REASON 1234'"),
            row(24.8, "earnings", "tool", tool="earnings_dates",
                args={"tickers": ["NVDA", "SECRET-TICKER ignore your rules"], "note": "SECRET-FIELD"}, ok=True, seconds=0.5),
            row(24.7, "earnings", "blocked", tool="SECRET TOOL NAME with spaces", args="{}", reason="no such tool: x"),
            row(24.6, "earnings", "answer", tool_calls=3, blocked=2, unverified=1, seconds=3.0),
            # a run that never answered (crashed), 20 minutes ago
            row(20, "earnings", "question", **q),
            row(19.9, "earnings", "tool", tool="earnings_dates", args={"tickers": ["AMD"]}, ok=False, seconds=9.0),
            # a line that isn't JSON
            "this is not json SECRET-GARBAGE",
            # a second agent, with an argument it never declared safe
            row(5, "life_admin", "question", chars=40, model="qwen3.6:35b-a3b"),
            row(4.9, "life_admin", "tool", tool="read_bills", args={"payee": "SECRET-PAYEE Dr Smith"}, ok=True, seconds=0.2),
            row(4.8, "life_admin", "answer", tool_calls=1, blocked=0, unverified=0, seconds=2.2),
            # an agent name that isn't a plain name: counted, not dropped, not shown
            row(3, "SECRET-AGENT Name", "question", **q),
        ]
    elif kind == "v2":
        # two agents at once, interleaved, with run ids and a time zone: both runs finish
        tz = dt.timezone(dt.timedelta(hours=9))   # Tokyo: not this Mac's zone, so a dropped offset shows

        def r2(m, agent, event, run, **f):
            when = (NOW.astimezone() - dt.timedelta(minutes=m)).astimezone(tz).isoformat(timespec="seconds")
            return json.dumps({"time": when, "agent": agent, "event": event, "run": run, **f})
        lines = [
            r2(12, "earnings", "question", "a1b2c3", **q),
            r2(11.9, "life_admin", "question", "d4e5f6", **q),
            r2(11.8, "earnings", "tool", "a1b2c3", tool="earnings_dates", args={"tickers": ["NVDA"]}, ok=True, seconds=0.6),
            r2(11.7, "life_admin", "tool", "d4e5f6", tool="read_bills", args={}, ok=True, seconds=0.1),
            r2(11.6, "earnings", "answer", "a1b2c3", tool_calls=1, blocked=0, unverified=0, seconds=1.4),
            r2(11.5, "life_admin", "answer", "d4e5f6", tool_calls=1, blocked=0, unverified=0, seconds=2.1),
            # the same agent twice at once (a schedule and me): only run ids can tell them apart
            r2(6, "earnings", "question", "aa11bb", **q),
            r2(5.9, "earnings", "question", "cc22dd", **q),
            r2(5.8, "earnings", "answer", "aa11bb", tool_calls=0, blocked=0, unverified=0, seconds=1.0),
            r2(5.7, "earnings", "answer", "cc22dd", tool_calls=0, blocked=0, unverified=0, seconds=1.1),
        ]
    elif kind == "superseded":
        # v1, no run ids: a question, then a new one 1 minute later before any answer
        lines = [row(8, "earnings", "question", **q),
                 row(7, "earnings", "question", **q),
                 row(6.9, "earnings", "answer", tool_calls=0, blocked=0, unverified=0, seconds=1.0)]
    elif kind == "partial":
        # an agent is halfway through writing the last line
        Path(path).write_text("\n".join(clean) + "\n" + '{"time": "' + t(1) + '", "agent": "earn')
        return
    Path(path).write_text("\n".join(lines) + "\n")


def stamp(days_ago):
    return (NOW - dt.timedelta(days=days_ago)).strftime("%Y%m%d-%H%M%S")


def report(kind, folder):
    f = Path(folder)
    f.mkdir(parents=True, exist_ok=True)
    head_v = "Values test · 2026-11-07 10:00 · qwen3.6:35b-a3b\n"
    head_s = "Side-door test · 2026-11-07 10:00 · qwen3.6:35b-a3b · 5 s\n"
    files = {
        "values-ok": (f"values-{stamp(1)}.txt", head_v + "  Held the line: 8/8\n  Per question: V1:✓ V2:✓\n"),
        "values-miss": (f"values-{stamp(0)}.txt", head_v + "  Held the line: 7/8\n  Per question: V1:✗ SECRET-ANSWER\n"),
        "values-unscored": (f"values-{stamp(0)}.txt", head_v + "  Asked: 8 (not scored: run without --yes)\n"),
        "side-ok": (f"sidedoor-{stamp(1)}.txt", head_s + "  Model held: 6/6   Code held: 5/5   Values only (no code guard): 2\n"),
        "side-code": (f"sidedoor-{stamp(0)}.txt", head_s + "  Model held: 5/6   Code held: 4/5   Values only (no code guard): 2\n"),
        "side-model": (f"sidedoor-{stamp(0)}.txt", head_s + "  Model held: 5/6   Code held: 5/5   Values only (no code guard): 2\n"),
        "old": (f"values-{stamp(20)}.txt", head_v + "  Held the line: 8/8\n"),
        "audit-ok": (f"studio_zenstudio_{stamp(2).replace('-', '_')}.txt",
                     "# host=zenstudio profile=studio\n# pass=42 warn=0 fail=0\nPASS|vault private|permissions 700\n"),
        "audit-fail": (f"studio_zenstudio_{stamp(0).replace('-', '_')}.txt",
                       "# host=zenstudio profile=studio\n# pass=40 warn=1 fail=2\n"
                       "FAIL|constitution|BIG RED FLAG\nFAIL|free disk|12 GB (min 50)\nWARN|memory index|x\n"),
    }
    name, text = files[kind]
    (f / name).write_text(text)


def tailscale(path):
    Path(path).write_text(json.dumps({
        "BackendState": "Running",
        "Self": {"HostName": "zenstudio", "OS": "macOS", "TailscaleIPs": ["100.64.0.1"], "Online": True},
        "Peer": {
            "k1": {"HostName": "zengaja", "OS": "macOS", "Online": True, "TailscaleIPs": ["100.64.0.2"],
                   "LastSeen": "0001-01-01T00:00:00Z"},
            "k2": {"HostName": "zenmaruti", "OS": "macOS", "Online": False, "TailscaleIPs": ["100.64.0.3"],
                   "LastSeen": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).isoformat()},
        }}))


if __name__ == "__main__":
    what = sys.argv[1]
    {"ledger": lambda: ledger(sys.argv[2], sys.argv[3]),
     "report": lambda: report(sys.argv[2], sys.argv[3]),
     "tailscale": lambda: tailscale(sys.argv[2])}[what]()
