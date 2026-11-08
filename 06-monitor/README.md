# 06-monitor: watching my agents

Home scale, not enterprise. One Mac Studio, a few agents, one person watching.

**Status:** Parts 1–3 of 4: terminal view, the web page with live updates, and ledger v2 in `agent.py`.

## The idea

The agents never know the monitor exists. They append to the ledger; the monitor reads it.
An agent I run by hand today and one that runs on a schedule later show up the same way.

## Rules

| Rule | How |
|---|---|
| Everything stays on my machines | No cloud, no dashboard service, no CDN. Stdlib Python only |
| Read-only | One `open()`, read-binary. GET requests only. Tests watch every file call with Python's audit hook |
| Never shows question text | The ledger stores a question's length only. Model-written text (tool arguments, block reasons, odd names) becomes a category or a count |
| Default deny | Each tool declares which arguments are safe (`"show"` in `agent.py`); the ledger keeps only those (v2). Old rows: the monitor's own `SAFE_ARGS`. Either way, only short tokens are shown |
| Checks the constitution itself | A changed constitution stops the agents before they write anything. A quiet ledger is not proof all is well |

## What it reads

| Source | Shows |
|---|---|
| `~/vault/.agents/ledger.jsonl` | Runs per agent, tool calls, blocked, unverified, unfinished, typical and slowest time, latest events |
| `~/vault/values/constitution.md` + `.values/approved.sha256` | Approved and unchanged, or BIG RED FLAG |
| Vault, agents folder, ledger | Permissions still 700 / 700 / 600 |
| Ollama `/api/version`, `/api/tags`, `/api/ps` | Up, models installed, models loaded |
| `tailscale status --json` | Each Mac: online, or when last seen. No addresses. Tries PATH, `/usr/local/bin`, `/opt/homebrew/bin`, then the app's own binary; the first that answers wins |
| `~/vault/.eval/values-*`, `sidedoor-*` | Score line and age. Never the answers |
| `~/driving-range/scripts/audits/studio_*` | verify.sh pass / warn / fail, and which checks failed |

## The page (Part 2)

`http://zenstudio:8765` from the iMac, MacBook or iPhone (Tailscale on). `http://localhost:8765` on the Studio.

| Tab | Shows |
|---|---|
| Alerts | Red and amber, with a count on the tab |
| Now | Constitution, model server, models loaded, machines, permissions |
| Agents | One card per agent: runs, tool calls, time, blocked, unverified, no answer |
| Live | Every event, newest first. New rows appear as the agents write them (about 1 s) |
| Tests | Values, side-door, verify.sh: score, when, ok / old / missed |

How live works: the page holds one connection open (Server-Sent Events). The server checks the
ledger once a second and sends each new whole line through the same privacy filter as the terminal
view. Every 15 s it also sends a fresh snapshot (model server, Tailscale, tests). Ad hoc runs today
and scheduled runs later look the same.

| Guard (in code) | Stops |
|---|---|
| Listens on 127.0.0.1 and the Tailscale address only; refuses 0.0.0.0 and home-network addresses | Guests on the home Wi-Fi |
| Answers only to its own names (zenstudio, localhost, its addresses) | A web page elsewhere pointing a made-up name at it (DNS rebinding) |
| GET only; five fixed addresses; no file names in URLs | Changing anything; reading any other file |
| Content-Security-Policy: own scripts only, nothing from outside, no framing | Injected scripts; the page loading anything from the internet |
| Text only, never HTML from data | A ledger value turning into page code |
| At most 8 live pages; no request log | Running out of threads; keeping a record of who looked |

## Alerts

| Red | Amber |
|---|---|
| Constitution changed or missing | Constitution not approved yet |
| Blocked call, unverified date, tool not ok, run ended in an error (last 7 days) | Run with no answer (crashed or stopped) |
| Permissions loosened | Ledger line I couldn't read |
| Model server down, model missing | Test never run, or older than 14 days |
| Values test missed, side-door code guard slipped, verify.sh failed | Side-door: the model slipped but the code held |

Exit code: 1 if anything is red, else 0.

## Run it (on the Studio)

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
cd 06-monitor
bash tests/test_monitor.sh          # stand-ins only; never touches ~/vault
bash tests/test_server.sh           # the page, the same way
python3 monitor.py status
python3 monitor.py tailscale        # where it looks for Tailscale, and what each place answered
python3 monitor.py serve --dry-run  # where it would listen
bash install_service.sh             # keep it running (LaunchAgent com.drivingrange.monitor)
bash install_service.sh status
```

Then open `http://zenstudio:8765` on the iMac or the iPhone. If macOS asks whether python3 may
accept incoming connections, allow it: that's the Tailscale side. `bash install_service.sh remove`
takes it out.

Safe to share: the Alerts, Now and Agents sections, and the tickers in Latest.

## Tests

| File | Checks | Mutations caught |
|---|---|---|
| `tests/test_monitor.sh` | 110: rules, privacy, read-only, settings, finding Tailscale, ledger v2 | 43 / 43 |
| `tests/test_server.sh` | 78: addresses, Host names, methods, paths, headers, live rows, half lines, a replaced ledger, limits, read-only, the LaunchAgent file | 18 / 18 |

Stand-ins only: a fake model server that writes down every method it sees, a fake Tailscale, made-up
ledgers and reports. Private-looking text is planted on purpose (`SECRET-*`); none of it may reach
the terminal, the JSON or the live stream. Python's audit hook watches every file call (works even as root).

## Known limits

- Old (v1) rows have no run id. If the same agent ran twice at once before ledger v2, the first
  run looks unfinished. New rows (v2, from `agent.py` on Nov 7) carry `run` and a time zone.
- The tool name in a `blocked` row is chosen by the model. It's shown only if it looks like a
  plain name (`send_email`); anything else shows as `(hidden)`.
- No password. Anyone on my Tailscale network can open the page; today that's only my devices.
  Same stance as the model server in Phase 1.
- The install script and the page's look were checked on Linux and in a headless browser at
  390 px and desktop width. The LaunchAgent itself only runs on the Studio.
