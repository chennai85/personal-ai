# 06-monitor: watching my agents

Home scale, not enterprise. One Mac Studio, a few agents, one person watching.

**Status:** Part 1 of 4 (terminal view). The web page comes in Part 2.

## The idea

The agents never know the monitor exists. They append to the ledger; the monitor reads it.
An agent I run by hand today and one that runs on a schedule later show up the same way.

## Rules

| Rule | How |
|---|---|
| Everything stays on my machines | No cloud, no dashboard service, no CDN. Stdlib Python only |
| Read-only | One `open()`, read-binary. GET requests only. Tests watch every file call with Python's audit hook |
| Never shows question text | The ledger stores a question's length only. Model-written text (tool arguments, block reasons, odd names) becomes a category or a count |
| Default deny | Each agent declares which tool arguments are safe to show (`SAFE_ARGS`). A new agent shows none until it's listed |
| Checks the constitution itself | A changed constitution stops the agents before they write anything. A quiet ledger is not proof all is well |

## What it reads

| Source | Shows |
|---|---|
| `~/vault/.agents/ledger.jsonl` | Runs per agent, tool calls, blocked, unverified, unfinished, typical and slowest time, latest events |
| `~/vault/values/constitution.md` + `.values/approved.sha256` | Approved and unchanged, or BIG RED FLAG |
| Vault, agents folder, ledger | Permissions still 700 / 700 / 600 |
| Ollama `/api/version`, `/api/tags`, `/api/ps` | Up, models installed, models loaded |
| `tailscale status --json` | Each Mac: online, or when last seen. No addresses |
| `~/vault/.eval/values-*`, `sidedoor-*` | Score line and age. Never the answers |
| `~/driving-range/scripts/audits/studio_*` | verify.sh pass / warn / fail, and which checks failed |

## Alerts

| Red | Amber |
|---|---|
| Constitution changed or missing | Constitution not approved yet |
| Blocked call, unverified date, tool not ok (last 7 days) | Run with no answer (crashed or stopped) |
| Permissions loosened | Ledger line I couldn't read |
| Model server down, model missing | Test never run, or older than 14 days |
| Values test missed, side-door code guard slipped, verify.sh failed | Side-door: the model slipped but the code held |

Exit code: 1 if anything is red, else 0.

## Run it (on the Studio)

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
cd 06-monitor
bash tests/test_monitor.sh          # stand-ins only; never touches ~/vault
python3 monitor.py status
python3 monitor.py status --days 30
```

Safe to share: the Alerts, Now and Agents sections, and the tickers in Latest.

## Tests

`tests/test_monitor.sh`: 86 checks with a stand-in model server, a stand-in Tailscale and made-up
ledgers and reports. Private-looking text is planted on purpose (`SECRET-*`) and must never reach
the output. Mutation-checked: each guard and rule was broken on purpose (30 ways) and the tests caught every one.

## Known limits (Part 1)

- Ledger v1 has no run id. If the same agent runs twice at once, the first run looks unfinished.
  Part 3 adds `run` and a time zone to every row; the monitor already reads both.
- The tool name in a `blocked` row is chosen by the model. It's shown only if it looks like a
  plain name (`send_email`); anything else shows as `(hidden)`.
