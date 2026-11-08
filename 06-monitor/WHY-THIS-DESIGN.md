# Why this design: Step 6, Watching My Agents

| Decision | Choice | Why |
|---|---|---|
| Scale | Home, not enterprise: one Mac Studio, a few agents, one person | Enterprise monitoring brings servers, accounts and a cloud. I need to know when to look |
| Shape | A SPAN port, not an inline box. The agents write a logbook (the ledger); the monitor only reads it | Something in the path can slow agents down, break them or change them. Watching a copy can't. The agents don't know the monitor exists |
| Real time | The page reads new logbook lines every second and pushes them to the browser (Server-Sent Events) | Agents run by hand today and on a schedule later. Both write the same lines, so nothing changes when the schedule arrives |
| Where it runs | The Mac Studio, as a LaunchAgent (`com.drivingrange.monitor`), like the model server | The agents and the vault are there. It starts at login and restarts if it stops |
| Who can open it | The Studio itself and my Tailscale network. Refuses `0.0.0.0` and home-network addresses | Not the guests' Wi-Fi, not the internet. No password in Phase 1, same as the model server |
| Host names | Answers only to its own names (localhost, `zenstudio`, its addresses) | A web page elsewhere can't point a made-up name at it and read the answers (DNS rebinding) |
| Read-only | One file-open in the code, read-only. GET requests only, to five fixed addresses. No file names in URLs | It can't change an agent, a file or the model server. Tests check every file call with Python's audit hook |
| No CDN | The page's own CSS and plain JavaScript. A Content-Security-Policy allows only its own scripts | Works with the internet off and loads nothing from outside. The learn pages use React and Tailwind from a CDN; this page can't |
| Dependencies | Python's standard library only | Nothing to install, nothing to update. Runs with the Mac's own `python3` |
| Question text | Never seen. The logbook stores a question's length only | The monitor can't leak what it never has |
| Tool inputs | Each tool declares which inputs are safe to show (`"show"` in `agent.py`). Undeclared inputs become a count. Even declared ones must be short tokens | Default deny. Tickers are public; a payee on a bill is not. A new agent shows nothing until I decide |
| Block reasons | One of five kinds. The model's own words are never stored | The first logbook kept 200 characters of what the model asked for. The thing meant to watch the side door had become one |
| Logbook v2 | Run id, time zone, declared inputs only, block kinds, error rows. Contract in the `05-agents` README | Two runs at once stay apart; a crash leaves a line, not a gap; times work when other Macs run agents |
| Constitution | Checked by the monitor itself, every snapshot | A changed constitution stops the agents before they write anything. A quiet logbook isn't an all-clear |
| Alerts | Red needs me now; amber can wait. Exit code 1 from `status` if anything is red | Most days it should be green, so I don't have to watch |
| Odd values | An odd agent name is counted as `(unknown)`; an odd tool name or error shows as `(hidden)` | Skipping is hiding. Count what can't be shown |
| Live pages | Up to 8 streams. A 9th takes the oldest's place, never refused. A ping every 10 s; a page that hears nothing for 35 s reconnects | A refused browser gives up for good. Found when the page stopped refreshing on my Mac |
| Tailscale | Tries PATH, `/usr/local/bin`, `/opt/homebrew/bin`, then the app's own binary. `monitor.py tailscale` shows what each answered. Never shows addresses | First run on my Studio: "can't read Tailscale status", with no reason given. Now the error says what it saw |
| Test reports | Newest values test, side-door test and `verify.sh` report: score lines only | The answers can contain my constitution. Scores are safe to show |
| No request log | The page keeps no record of who looked | One less log to protect |
| Tests | Stand-ins only: a fake model server that records every request method, a fake Tailscale, made-up logbooks with planted `SECRET-*` text | Never touches my vault. The planted text must never reach any output |
| Mutation check | Broke the code on purpose 80 ways; 79 caught. The one left (a closed stream's slot not freed at once) changes nothing a page can see | A test that can't fail isn't a test. Two that couldn't were found and fixed |
