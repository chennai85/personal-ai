#!/usr/bin/env python3
"""
monitor.py: watch my agents, on the Mac Studio. Read-only.

    python3 monitor.py status           what's happening: alerts, model server, agents, tests
    python3 monitor.py status --days 30 look further back (default 7)
    python3 monitor.py status --json    the same, as JSON (what the web page reads)
    python3 monitor.py serve            the web page: http://zenstudio:8765 (this Mac + Tailscale only)

The agents never know the monitor exists. They write to the ledger; the monitor reads it.
So an agent run by hand today and one run on a schedule later show up the same way.

Rules (in code):
  1. Read-only. Files are opened for reading only; the model server gets GET requests only.
  2. Never shows question text. The ledger only holds a question's length, and the monitor
     shows nothing it wasn't told is safe: model-written text (tool arguments, block reasons)
     is reduced to a category or a count.
  3. Checks the constitution itself. A changed constitution stops the agents before they
     write anything, so a quiet ledger is not proof that all is well.
  4. Stdlib only. Nothing to install; runs with the Mac's python3.

Sources: the ledger (~/vault/.agents/ledger.jsonl), the constitution fingerprint, the model
server (Ollama), Tailscale, test reports (~/vault/.eval/) and verify.sh audits.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STANDARD = HERE.parent / "01-environment" / "standard.sh"

UNFINISHED_AFTER = dt.timedelta(minutes=10)   # a question with no answer after this = unfinished
STALE_AFTER_DAYS = 14                         # a test report older than this = amber
RECENT_EVENTS = 50                            # how many events the activity list shows

TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,11}$")    # NVDA, BRK.B: short, no spaces
NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")                # earnings, read_watchlist
MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:_\-/]{0,59}$")  # qwen3.6:35b-a3b

# Which tool arguments are safe to show, per agent. Everything else is shown as a count.
# Default deny: a new agent (life admin) shows no arguments until it is listed here.
SAFE_ARGS = {
    "earnings": {"earnings_dates": {"tickers"}, "direct": {"tickers"}},
}

# Ledger v2 writes the kind of block itself, from this list. Anything else is mapped below.
KINDS = {"no such tool", "not on this agent's list", "tool tier not allowed", "arguments refused",
         "tool budget reached", "refused"}
ERRNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,39}$")      # URLError, ValueError: a type, never a message

# v1 block reasons can carry model-written text ("not a ticker: '...'"). Show the category only.
REASONS = [
    (re.compile(r"^no such tool"), "no such tool"),
    (re.compile(r"is not on the .* list"), "not on this agent's list"),
    (re.compile(r"Phase 1 allows"), "tool tier not allowed"),
    (re.compile(r"^tool budget"), "tool budget reached"),
]


# ---------------------------------------------------------------------
# Settings: read from standard.sh the same way memory.py does; environment can override.
# (memory.py needs numpy; the monitor needs nothing, so it reads the file itself.
#  The tests check that both agree on where the vault is.)
# ---------------------------------------------------------------------
def load_settings():
    vals = {}
    if STANDARD.exists():
        for line in STANDARD.read_text().splitlines():
            m = re.match(r'^([A-Z_]+)=("([^"]*)"|(\S+))', line.strip())
            if m:
                vals[m.group(1)] = m.group(3) if m.group(3) is not None else m.group(4)
    home = str(Path.home())

    def get(key, default):
        v = os.environ.get(key) or vals.get(key) or default
        v = re.sub(r"\$\{(\w+):-([^}]*)\}", lambda m: os.environ.get(m.group(1)) or m.group(2), v)
        v = v.replace("$HOME", home)
        for k, kv in vals.items():
            v = v.replace(f"${k}", os.environ.get(k) or kv.replace("$HOME", home))
        return v

    root = Path(get("DR_ROOT", f"{home}/driving-range"))
    profile = os.environ.get("DR_PROFILE") or ""
    if not profile and (root / ".dr_profile").exists():
        profile = (root / ".dr_profile").read_text().strip()
    return {
        "vault": Path(get("VAULT_DIR", f"{home}/vault")),
        "model_url": get("MODEL_BASE_URL", "http://localhost:11434").rstrip("/"),
        "models": [get("MODEL_MAIN", "qwen3.6:35b-a3b"), get("MODEL_FAST", "gemma4:e4b"),
                   get("MODEL_EMBED", "qwen3-embedding:0.6b")],
        "root": root,
        "profile": profile or "studio",
    }


S = load_settings()
LEDGER = S["vault"] / ".agents" / "ledger.jsonl"
EVAL_DIR = S["vault"] / ".eval"
CONSTITUTION = S["vault"] / "values" / "constitution.md"
APPROVED_HASH = S["vault"] / ".values" / "approved.sha256"
AUDITS = S["root"] / "scripts" / "audits"


def read_bytes(path, offset=0):
    with open(path, "rb") as f:          # the only way the monitor opens a file
        f.seek(offset)
        return f.read()


def alert(level, what, detail=""):
    return {"level": level, "what": what, "detail": detail}


def ago(t, now):
    s = int((now - t).total_seconds())
    if s < 90:
        return f"{max(s, 0)} s ago"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 172800:
        return f"{s // 3600} h ago"
    return f"{s // 86400} d ago"


# ---------------------------------------------------------------------
# The ledger: read whole lines only (an agent may be writing the last one)
# ---------------------------------------------------------------------
def parse_time(s):
    try:
        t = dt.datetime.fromisoformat(str(s))
        return t.astimezone().replace(tzinfo=None) if t.tzinfo else t   # local time, like v1 rows
    except (ValueError, OverflowError, OSError):
        return None


def read_ledger(path=None):
    try:
        data = read_bytes(path or LEDGER)
    except FileNotFoundError:
        return [], 0, False
    rows, bad, _ = parse_lines(data)
    return rows, bad, True


def parse_lines(data):
    """Whole lines only (an agent may be writing the last one). Returns rows, bad, bytes used."""
    complete = data[: data.rfind(b"\n") + 1]
    rows, bad = [], 0
    for line in complete.splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            bad += 1
            continue
        t = parse_time(r.get("time")) if isinstance(r, dict) else None
        if t is None or not isinstance(r.get("agent"), str) or not isinstance(r.get("event"), str):
            bad += 1
            continue
        for k in ("agent", "event"):            # an odd name is counted as "(unknown)", never dropped
            if not NAME.match(r[k]):
                r[k] = "(unknown)"
        r["_t"] = t
        rows.append(r)
    return rows, bad, len(complete)


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def safe_args(agent, key, args, allowed=None):
    """Only fields declared safe, and only short tokens. Anything else: a count.

    v1 rows: the monitor's own SAFE_ARGS list. v2 rows: the agent already kept only the fields
    its tool declares ("show" in agent.py); the monitor still lets through short tokens only.
    """
    if allowed is None:
        allowed = SAFE_ARGS.get(agent, {}).get(key, set())
    shown, hidden = {}, 0
    if not isinstance(args, dict):
        return shown, (1 if args else 0)
    for k, v in args.items():
        items = v if isinstance(v, list) else [v]
        if k in allowed:
            ok = [str(x) for x in items if isinstance(x, str) and TOKEN.match(x)]
            hidden += len(items) - len(ok)
            if ok:
                shown[k] = ok
        else:
            hidden += len(items)
    return shown, hidden


def reason_category(reason):
    if not isinstance(reason, str):
        return "refused"
    if reason in KINDS:
        return reason
    for pat, label in REASONS:
        if pat.search(reason):
            return label
    return "arguments refused"


def safe_event(r):
    """What the monitor may show about one ledger row. Built up from nothing, field by field."""
    agent, event = r["agent"], r["event"]                 # already checked in read_ledger
    e = {"time": r["_t"].strftime("%Y-%m-%d %H:%M:%S"), "agent": agent, "event": event}
    if isinstance(r.get("run"), str) and TOKEN.match(r["run"]):
        e["run"] = r["run"]
    if event == "question":
        e["chars"] = num(r.get("chars"))
        if isinstance(r.get("model"), str) and MODEL.match(r["model"]):
            e["model"] = r["model"]
    elif event in ("tool", "blocked"):
        tool = r.get("tool")
        e["tool"] = tool if isinstance(tool, str) and NAME.match(tool) else ("(none)" if tool is None else "(hidden)")
        if event == "tool":
            e["ok"] = r.get("ok") is True
            e["seconds"] = num(r.get("seconds"))
            if isinstance(r.get("error"), str) and ERRNAME.match(r["error"]):
                e["error"] = r["error"]
            args = r.get("args")
            if r.get("v") == 2 and isinstance(args, dict):
                e["args"], e["hidden"] = safe_args(agent, tool, args, allowed=set(args))
                e["hidden"] += num(r.get("args_hidden")) or 0
            else:
                e["args"], e["hidden"] = safe_args(agent, tool, args)
        else:
            e["reason"] = reason_category(r.get("reason"))
            e["hidden"] = 1 if r.get("args") else 0        # blocked args: never shown
    elif event == "answer":
        for k in ("tool_calls", "blocked", "unverified", "seconds"):
            e[k] = num(r.get(k))
    elif event == "error":
        e["where"] = r["where"] if isinstance(r.get("where"), str) and NAME.match(r["where"]) else "(hidden)"
        e["error"] = r["error"] if isinstance(r.get("error"), str) and ERRNAME.match(r["error"]) else "(hidden)"
        e["seconds"] = num(r.get("seconds"))
    elif event == "direct":
        e["args"], e["hidden"] = safe_args(agent, "direct", {"tickers": r.get("tickers")})
    return e


# ---------------------------------------------------------------------
# Runs: question → tools → answer. v2 rows carry a run id; v1 rows are grouped by order.
# ---------------------------------------------------------------------
def build_runs(rows, now):
    runs, open_by_key = [], {}

    def start(r, key):
        run = {"agent": r["agent"], "start": r["_t"], "end": None, "tool_calls": 0, "blocked": 0,
               "unverified": 0, "seconds": None, "failed_tools": 0, "finished": False, "superseded": False,
               "error": False}
        runs.append(run)
        open_by_key[key] = run
        return run

    for r in rows:
        ev = r["event"]
        if ev == "direct":
            continue
        key = ("run", r["run"]) if isinstance(r.get("run"), str) else ("agent", r["agent"])
        run = open_by_key.get(key)
        if ev == "question":
            if run is not None and key[0] == "agent":
                run["superseded"] = True        # v1: a new question before the last answer
            run = start(r, key)
            continue
        if run is None:
            run = start(r, key)                 # an orphan row: count it, don't lose it
        if ev == "tool":
            run["tool_calls"] += 1
            run["failed_tools"] += 0 if r.get("ok") is True else 1
        elif ev == "blocked":
            run["blocked"] += 1
        elif ev == "error":                     # v2: the run ended, and said why
            run["finished"], run["error"], run["end"] = True, True, r["_t"]
            open_by_key.pop(key, None)
        elif ev == "answer":
            run["finished"], run["end"] = True, r["_t"]
            run["seconds"] = num(r.get("seconds"))
            run["unverified"] = num(r.get("unverified")) or 0
            run["blocked"] = max(run["blocked"], num(r.get("blocked")) or 0)
            open_by_key.pop(key, None)
    for run in runs:
        run["unfinished"] = not run["finished"] and (run["superseded"] or now - run["start"] > UNFINISHED_AFTER)
        run["running"] = not run["finished"] and not run["unfinished"]
    return runs


def agent_stats(rows, runs, now, days):
    since, today = now - dt.timedelta(days=days), now.replace(hour=0, minute=0, second=0, microsecond=0)
    names = sorted({r["agent"] for r in rows}, key=lambda n: (n == "(unknown)", n))   # odd names last
    out = []
    for name in names:
        rs = [r for r in runs if r["agent"] == name and r["start"] >= since]
        secs = [r["seconds"] for r in rs if r["seconds"] is not None]
        last = max((r["_t"] for r in rows if r["agent"] == name), default=None)
        out.append({
            "agent": name,
            "runs_today": sum(r["start"] >= today for r in rs),
            "runs": len(rs),
            "direct": sum(1 for r in rows if r["agent"] == name and r["event"] == "direct" and r["_t"] >= since),
            "tool_calls": sum(r["tool_calls"] for r in rs),
            "failed_tools": sum(r["failed_tools"] for r in rs),
            "blocked": sum(r["blocked"] for r in rs),
            "unverified": sum(r["unverified"] for r in rs),
            "unfinished": sum(r["unfinished"] for r in rs),
            "errors": sum(r["error"] for r in rs),
            "running": sum(r["running"] for r in rs),
            "typical_s": round(statistics.median(secs), 1) if secs else None,
            "slowest_s": round(max(secs), 1) if secs else None,
            "last": last.strftime("%Y-%m-%d %H:%M:%S") if last else None,
            "last_ago": ago(last, now) if last else None,
        })
    return out


def ledger_alerts(stats, bad, days):
    a = []
    for s in stats:
        n = s["agent"]
        if s["blocked"]:
            a.append(alert("red", f"{n}: {s['blocked']} blocked call(s)", f"last {days} days. See Live for the category"))
        if s["unverified"]:
            a.append(alert("red", f"{n}: {s['unverified']} unverified date(s) in answers",
                           f"last {days} days. A date the tool didn't give"))
        if s["failed_tools"]:
            a.append(alert("red", f"{n}: {s['failed_tools']} tool call(s) not ok", f"last {days} days"))
        if s["errors"]:
            a.append(alert("red", f"{n}: {s['errors']} run(s) ended in an error",
                           f"last {days} days. Model server down, or a bad reply. See Live"))
        if s["unfinished"]:
            a.append(alert("amber", f"{n}: {s['unfinished']} run(s) with no answer",
                           "crashed, stopped, or the model server went away"))
    if bad:
        a.append(alert("amber", f"ledger: {bad} line(s) I couldn't read", "skipped, not shown"))
    return a


# ---------------------------------------------------------------------
# The constitution: checked here too, because a red flag stops the agents before the ledger
# ---------------------------------------------------------------------
def check_constitution():
    has_text, has_hash = CONSTITUTION.exists(), APPROVED_HASH.exists()
    if not has_text and has_hash:
        return {"state": "missing"}, alert("red", "BIG RED FLAG: the constitution is missing",
                                            "it was approved once. Agents won't run (uv run memory.py values)")
    if not has_text:
        return {"state": "none"}, alert("amber", "no constitution yet", "Step 4")
    if not has_hash:
        return {"state": "not approved"}, alert("amber", "constitution not approved", "uv run memory.py values approve")
    now_hash = hashlib.sha256(read_bytes(CONSTITUTION)).hexdigest()
    if now_hash != read_bytes(APPROVED_HASH).decode().strip():
        return {"state": "changed"}, alert("red", "BIG RED FLAG: the constitution has changed",
                                            "agents won't run until you decide (uv run memory.py values)")
    return {"state": "approved, unchanged"}, None


def check_permissions():
    want = [(S["vault"], 0o700, "vault"), (LEDGER.parent, 0o700, "agents folder"), (LEDGER, 0o600, "ledger")]
    out, alerts = [], []
    for path, mode, label in want:
        if not path.exists():
            out.append({"what": label, "mode": None, "want": oct(mode)[2:], "ok": None})
            continue
        m = path.stat().st_mode & 0o777
        ok = m == mode
        out.append({"what": label, "mode": oct(m)[2:], "want": oct(mode)[2:], "ok": ok})
        if not ok:
            alerts.append(alert("red", f"{label} permissions are {oct(m)[2:]}", f"want {oct(mode)[2:]} (chmod {oct(mode)[2:]} {path})"))
    return out, alerts


# ---------------------------------------------------------------------
# The model server: GET only
# ---------------------------------------------------------------------
def get_json(path, timeout=3):
    req = urllib.request.Request(S["model_url"] + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def check_model_server():
    info = {"url": S["model_url"], "up": False, "version": None, "installed": [], "loaded": []}
    try:
        info["version"] = get_json("/api/version").get("version")
        info["up"] = True
        names = {m.get("name") for m in get_json("/api/tags").get("models", [])}
        info["installed"] = [{"model": m, "ok": m in names} for m in S["models"]]
        for m in get_json("/api/ps").get("models", []):
            info["loaded"].append({"model": m.get("name"),
                                   "gb": round((m.get("size_vram") or m.get("size") or 0) / 1e9, 1),
                                   "until": (m.get("expires_at") or "")[:19].replace("T", " ")})
    except Exception as e:
        info["error"] = type(e).__name__
    alerts = []
    if not info["up"]:
        alerts.append(alert("red", "model server not answering", f"{S['model_url']} ({info.get('error', '')}). Agents can't run"))
    for m in info["installed"]:
        if not m["ok"]:
            alerts.append(alert("red", f"model missing: {m['model']}", "re-run 02-local-model/server_setup.sh"))
    return info, alerts


# ---------------------------------------------------------------------
# Machines: Tailscale's own view. Names, online, last seen. No addresses.
# ---------------------------------------------------------------------
TAILSCALE_PLACES = [                                   # where Tailscale's command lives on a Mac
    "/usr/local/bin/tailscale",                        # "Install CLI" from the Tailscale menu
    "/opt/homebrew/bin/tailscale",                     # brew install tailscale
    "/Applications/Tailscale.app/Contents/MacOS/Tailscale",   # inside the app itself
]


def tailscale_candidates():
    if os.environ.get("TAILSCALE_BIN"):                # tests, or a place I name myself
        return [p for p in [os.environ["TAILSCALE_BIN"]] if Path(p).exists()]
    places = os.environ.get("TAILSCALE_CANDIDATES", "").split(":") if os.environ.get("TAILSCALE_CANDIDATES") else \
        [shutil.which("tailscale")] + TAILSCALE_PLACES
    seen = []
    for p in places:
        if p and p not in seen and Path(p).exists():
            seen.append(p)
    return seen


def first_line(text, width=80):
    line = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return line[:width]


def tailscale_try(exe):
    """Run one Tailscale command. Returns (status JSON or None, what happened)."""
    env = dict(os.environ)
    if exe.endswith(".app/Contents/MacOS/Tailscale"):
        env["TAILSCALE_BE_CLI"] = "1"                  # the app's own binary: act as the command, not the app
    try:
        out = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, env=env,
                             timeout=float(os.environ.get("TAILSCALE_TIMEOUT", "10")))
    except subprocess.TimeoutExpired:
        return None, "timed out"
    except OSError as e:
        return None, f"can't run it ({e.strerror})"
    try:
        st = json.loads(out.stdout)
        if isinstance(st, dict) and "BackendState" in st:
            return st, "ok"
    except json.JSONDecodeError:
        pass
    if out.returncode:
        return None, f"exit {out.returncode}: {first_line(out.stderr) or first_line(out.stdout) or 'no message'}"
    return None, f"not status JSON: {first_line(out.stdout, 60) or first_line(out.stderr, 60) or 'empty'}"


def tailscale_attempts():
    """Try each place in turn; the first that answers wins. Returns (status or None, [(place, what happened)])."""
    tried = []
    for exe in tailscale_candidates():
        st, what = tailscale_try(exe)
        tried.append((exe, what))
        if st is not None:
            return st, tried
    return None, tried


def tailscale_status():
    """Tailscale's own JSON, or (None, why)."""
    st, tried = tailscale_attempts()
    if st is not None:
        return st, None
    if not tried:
        return None, "missing"
    return None, "; ".join(f"{Path(p).name}: {w}" for p, w in tried)


def check_machines(now):
    st, why = tailscale_status()
    if why == "missing":
        return [], [alert("amber", "can't see Tailscale", "not installed here, or not on the PATH")]
    if st is None:
        return [], [alert("amber", "can't read Tailscale status", f"{why} (python3 monitor.py tailscale)")]
    machines, alerts = [], []
    me = st.get("Self") or {}
    if st.get("BackendState") != "Running":
        alerts.append(alert("amber", "Tailscale isn't running on this Mac", "the other Macs can't reach the model"))
    machines.append({"name": me.get("HostName", "?"), "os": me.get("OS", ""), "online": st.get("BackendState") == "Running",
                     "seen": "this Mac"})
    for p in (st.get("Peer") or {}).values():
        seen = parse_time((p.get("LastSeen") or "").replace("Z", "+00:00"))
        online = bool(p.get("Online"))
        machines.append({"name": p.get("HostName", "?"), "os": p.get("OS", ""), "online": online,
                         "seen": "now" if online else (ago(seen, now) if seen and seen.year > 2000 else "never")})
    return machines, alerts


# ---------------------------------------------------------------------
# Tests: the newest report of each kind. Score lines only, never the answers.
# ---------------------------------------------------------------------
def newest(folder, pattern):
    files = sorted(folder.glob(pattern)) if folder.is_dir() else []
    return files[-1] if files else None            # names carry the time, so sorted = oldest first


def file_time(path):
    m = re.search(r"(\d{8})[-_](\d{6})", path.name)
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") if m else None


def check_tests(now):
    tests, alerts = [], []

    def add(kind, path, line, ok, why=""):
        t = file_time(path) if path else None
        age = (now - t).days if t else None
        tests.append({"test": kind, "when": t.strftime("%Y-%m-%d %H:%M") if t else None,
                      "age_days": age, "result": line, "ok": ok})
        if path is None:
            alerts.append(alert("amber", f"{kind}: never run", why))
        elif ok is False:
            alerts.append(alert("red", f"{kind}: {line}", why))
        elif ok is None:
            alerts.append(alert("amber", f"{kind}: {line}", why))
        if age is not None and age > STALE_AFTER_DAYS:
            alerts.append(alert("amber", f"{kind}: last run {age} days ago", "run it again"))

    p = newest(EVAL_DIR, "values-*.txt")
    if p is None:
        add("values test", None, "", None, "uv run memory.py values test")
    else:
        text = read_bytes(p).decode(errors="replace")
        m = re.search(r"Held the line: (\d+)/(\d+)", text)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            add("values test", p, f"held the line {a}/{b}", a == b, "read the answers privately")
        else:
            add("values test", p, "not scored", None, "run without --yes to judge each answer")

    p = newest(EVAL_DIR, "sidedoor-*.txt")
    if p is None:
        add("side-door test", None, "", None, "uv run sidedoor.py (in 05-agents)")
    else:
        text = read_bytes(p).decode(errors="replace")
        m = re.search(r"Model held: (\d+)/(\d+)\s+Code held: (\d+)/(\d+)(?:\s+Values only \(no code guard\): (\d+))?", text)
        if not m:
            add("side-door test", p, "can't read the score", None, "")
        else:
            mh, mt, ch, ct = map(int, m.group(1, 2, 3, 4))
            vo = int(m.group(5) or 0)
            line = f"model {mh}/{mt} · code {ch}/{ct} · values only {vo}"
            if ch < ct:
                add("side-door test", p, line, False, "a code guard let something through")
            elif mh < mt:
                add("side-door test", p, line, None, "the model slipped; the code held")
            else:
                add("side-door test", p, line, True)

    p = newest(AUDITS, f"{S['profile']}_*.txt")
    if p is None:
        add("verify.sh", None, "", None, "bash 01-environment/verify.sh")
    else:
        text = read_bytes(p).decode(errors="replace")
        m = re.search(r"pass=(\d+) warn=(\d+) fail=(\d+)", text)
        if not m:
            add("verify.sh", p, "can't read the counts", None, "")
        else:
            ps, w, f = map(int, m.groups())
            failed = [l.split("|")[1] for l in text.splitlines() if l.startswith("FAIL|") and l.count("|") >= 2]
            add("verify.sh", p, f"{ps} pass · {w} warn · {f} fail", f == 0,
                ("failed: " + ", ".join(failed)) if failed else "")
    return tests, alerts


# ---------------------------------------------------------------------
# Everything, in one snapshot
# ---------------------------------------------------------------------
def snapshot(days=7, now=None):
    now = now or dt.datetime.now()
    alerts = []
    constitution, a = check_constitution()
    if a:
        alerts.append(a)
    perms, a = check_permissions()
    alerts += a
    server, a = check_model_server()
    alerts += a
    machines, a = check_machines(now)
    alerts += a
    rows, bad, exists = read_ledger()
    runs = build_runs(rows, now)
    stats = agent_stats(rows, runs, now, days)
    alerts += ledger_alerts(stats, bad, days)
    tests, a = check_tests(now)
    alerts += a
    since = now - dt.timedelta(days=days)
    recent = [safe_event(r) for r in rows if r["_t"] >= since][-RECENT_EVENTS:]
    alerts.sort(key=lambda x: x["level"] != "red")
    return {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"), "days": days,
        "alerts": alerts,
        "constitution": constitution, "permissions": perms,
        "model_server": server, "machines": machines,
        "ledger": {"exists": exists, "rows": len(rows), "unreadable": bad},
        "agents": stats, "recent": recent, "tests": tests,
    }


# ---------------------------------------------------------------------
# The terminal view
# ---------------------------------------------------------------------
def render(s):
    tty = sys.stdout.isatty()
    red, amber, green, dim, bold, reset = (("\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[1m", "\033[0m")
                                          if tty else ("",) * 6)
    out = [f"{bold}Agent monitor · {s['time']} · last {s['days']} days{reset}", ""]
    reds = [a for a in s["alerts"] if a["level"] == "red"]
    out.append(f"{bold}Alerts{reset}  {len(reds)} red · {len(s['alerts']) - len(reds)} amber")
    if not s["alerts"]:
        out.append(f"  {green}✓ all clear{reset}")
    for a in s["alerts"]:
        c, mark = (red, "✗") if a["level"] == "red" else (amber, "!")
        out.append(f"  {c}{mark} {a['what']}{reset}" + (f"{dim}  · {a['detail']}{reset}" if a["detail"] else ""))

    m = s["model_server"]
    out += ["", f"{bold}Now{reset}"]
    out.append(f"  constitution   {s['constitution']['state']}")
    out.append("  model server   " + (f"up · Ollama {m['version']} · {m['url']}" if m["up"] else f"{red}down{reset} · {m['url']}"))
    for l in m["loaded"]:
        out.append(f"    loaded       {l['model']} · {l['gb']} GB · until {l['until']}")
    if m["up"] and not m["loaded"]:
        out.append(f"    loaded       {dim}nothing (first answer will be slow){reset}")
    out.append("  permissions    " + "  ".join(
        f"{p['what']} {p['mode'] or '—'}{'' if p['ok'] is not False else ' ✗'}" for p in s["permissions"]))
    for mc in s["machines"]:
        out.append(f"  {mc['name']:<14} {('online' if mc['online'] else 'offline'):<8} {dim}{mc['os']} · {mc['seen']}{reset}")

    out += ["", f"{bold}Agents{reset}  ({s['ledger']['rows']} ledger rows)"]
    if not s["agents"]:
        out.append(f"  {dim}nothing in the ledger yet{reset}")
    for a in s["agents"]:
        timing = f"typical {a['typical_s']} s · slowest {a['slowest_s']} s" if a["typical_s"] is not None else "no answers yet"
        out.append(f"  {a['agent']:<12} {a['runs']} runs ({a['runs_today']} today) · {a['direct']} direct · "
                   f"{a['tool_calls']} tool calls · {timing}")
        out.append(f"  {'':<12} blocked {a['blocked']} · unverified {a['unverified']} · unfinished {a['unfinished']}"
                   f"{' · errors ' + str(a['errors']) if a['errors'] else ''}"
                   f"{' · running ' + str(a['running']) if a['running'] else ''} · last {a['last_ago']}")

    out += ["", f"{bold}Tests{reset}"]
    for t in s["tests"]:
        state = "never run" if t["when"] is None else f"{t['result']} · {t['when']} ({t['age_days']} d)"
        out.append(f"  {t['test']:<15} {state}")

    out += ["", f"{bold}Latest{reset}"]
    for e in s["recent"][-10:]:
        out.append(f"  {e['time'][5:]}  {e['agent']:<10} {e['event']:<9} {describe(e)}")
    return "\n".join(out)


def describe(e):
    ev = e["event"]
    hidden = f" (+{e['hidden']} hidden)" if e.get("hidden") else ""
    args = " ".join(" ".join(v) for v in e.get("args", {}).values())
    if ev == "question":
        return f"{e.get('chars')} chars · {e.get('model', '')}"
    if ev == "tool":
        state = "ok" if e["ok"] else "NOT OK" + (f" ({e['error']})" if e.get("error") else "")
        return " · ".join(x for x in (f"{e['tool']} {state}", f"{e.get('seconds')} s", args) if x) + hidden
    if ev == "error":
        return f"{e['where']} · {e['error']} · {e.get('seconds')} s"
    if ev == "blocked":
        return f"{e['tool']} · {e['reason']}"
    if ev == "answer":
        return f"{e.get('tool_calls')} calls · {e.get('blocked')} blocked · {e.get('unverified')} unverified · {e.get('seconds')} s"
    if ev == "direct":
        return f"{args}{hidden}"
    return ""


def cmd_tailscale():
    st, tried = tailscale_attempts()
    if not tried:
        print("No Tailscale command found in: " + ", ".join(["PATH"] + TAILSCALE_PLACES))
        return 1
    for p, what in tried:
        print(f"  {'✓' if what == 'ok' else '✗'} {p}\n      {what}")
    if st is None:
        print("\nNone answered. Paste the lines above (no addresses in them).")
        return 1
    print(f"\nUsing it. Tailscale is {st.get('BackendState')}. Machines:")
    for m in check_machines(dt.datetime.now())[0]:
        print(f"  {m['name']:<14} {'online' if m['online'] else 'offline':<8} {m['seen']}")
    return 0


def main():
    p = argparse.ArgumentParser(description="Watch my agents. Read-only.")
    sub = p.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status", help="alerts, model server, agents, tests")
    st.add_argument("--days", type=int, default=7)
    st.add_argument("--json", action="store_true")
    sub.add_parser("tailscale", help="where I look for Tailscale, and what each place answered")
    sv = sub.add_parser("serve", help="the web page, on this Mac and over Tailscale only")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--bind", action="append", help="address to listen on (default: 127.0.0.1 + this Mac's Tailscale address)")
    sv.add_argument("--dry-run", action="store_true", help="say where it would listen, then stop")
    args = p.parse_args()
    if args.cmd == "tailscale":
        return cmd_tailscale()
    if args.cmd == "serve":
        import server
        return server.main(args)
    s = snapshot(days=args.days)
    print(json.dumps(s, indent=2) if args.json else render(s))
    return 1 if any(a["level"] == "red" for a in s["alerts"]) else 0


if __name__ == "__main__":
    sys.exit(main())
