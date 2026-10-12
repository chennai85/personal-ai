# Step 2: A Local Model

A private model running on the Mac Studio, shared with the iMac and MacBook over Tailscale.

> **Why these models:** [WHY-THIS-MODEL.md](WHY-THIS-MODEL.md)
> **The story** is on the blog: [aishree.me/personal-ai](https://www.aishree.me/personal-ai)

---

## The idea

```
 MacBook (zenmaruti) ─┐
                      ├── Tailscale ──► Mac Studio (zenstudio) : Ollama : port 11434
 iMac    (zengaja)   ─┘                   ├─ qwen3.6:35b-a3b   (main, ~24 GB)
                                          └─ gemma4:e4b        (fast, ~7 GB)
```

**Ollama** is the model server: a small program that loads models into memory and answers requests. The Studio runs it in the background; the other Macs send it questions using the `MODEL_BASE_URL` set in Step 1.

---

## The plan

| # | Task | Script | Done when |
|---|---|---|---|
| 1 | Install Ollama, run it as a background service, open it to your Macs | `server_setup.sh` (Studio) | Service loaded, server answering |
| 2 | Download both models | `server_setup.sh` (Studio) | Both appear in `ollama list` |
| 3 | Measure real speed | `speedtest.sh` (any Mac) | Tokens per second, saved to a file |
| 4 | Check every Mac | `verify.sh` (all three) | "model server reachable" and both models PASS |

---

## Before you start (Mac Studio)

The Studio is now a server. Two settings keep it available:

1. **Stay awake:** System Settings → Energy → turn on **Prevent automatic sleeping when the display is off**
2. **Stay logged in:** the model service runs in your user session. After a restart, log in once (or turn on automatic login, if FileVault allows it).

Then update the scripts:

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
```

---

## 1–2. Set up the server (Mac Studio)

```bash
cd ~/driving-range/ai-experiments/personal-ai/02-local-model
bash server_setup.sh
```

What it does:

| Part | Detail |
|---|---|
| Installs Ollama | With Homebrew: `brew install ollama` |
| Background service | `~/Library/LaunchAgents/com.drivingrange.ollama.plist`. Starts at login, restarts if it stops. |
| Settings (from `standard.sh`) | Listen on `0.0.0.0:11434`, 32K context, keep models loaded 30 min, 2 requests at once |
| Downloads | `qwen3.6:35b-a3b` (~24 GB) and `gemma4:e4b` (~7 GB) |
| Log | `~/driving-range/scripts/logs/ollama.log` |

The download takes a while. Safe to re-run: it skips what's already done.

**Why a background service, not the Ollama app?** Ollama's documented way to open the app to your network (`launchctl setenv`) doesn't survive a restart. A service file keeps the settings permanent and checkable.

Quick test on the Studio:

```bash
ollama run gemma4:e4b "Say hello in five words."
```

---

## 3. Measure speed (any Mac)

```bash
bash speedtest.sh
```

Run it **twice**. The first run includes loading the model into memory; the second shows everyday speed.

| Column | Meaning |
|---|---|
| `load_s` | Seconds to load the model (0 when already loaded) |
| `read_tok_s` | How fast it reads your prompt |
| `write_tok_s` | **How fast it writes the answer. The number you feel.** |
| `total_s` | Request to finished answer |

Run it on the Studio *and* the MacBook: the difference is the cost of the network.

Results are saved to `~/driving-range/scripts/audits/speedtest_*.txt`.

**Results:** *(to be filled in)*

| From | Model | Write speed | Total |
|---|---|---|---|
| Studio | qwen3.6:35b-a3b | | |
| Studio | gemma4:e4b | | |
| MacBook | qwen3.6:35b-a3b | | |

---

## 4. Verify (all three Macs)

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
bash 01-environment/verify.sh
```

New checks in Standard v1.2:

| Check | Where |
|---|---|
| `model server reachable` | All Macs |
| `model available` (both models) | All Macs |
| `tool ollama`, `ollama service`, `ollama listens` | Studio only |

**Done when:** all of these PASS on every Mac.

---

## Security note: read this

Ollama has **no password**. Listening on `0.0.0.0` means any device that can reach the Studio can use it:

| Who can reach it | Okay? |
|---|---|
| Your Macs over Tailscale | ✅ Intended |
| Other devices on your home Wi-Fi (phones, TVs, guests) | ⚠️ Yes, they could too |
| The internet | ❌ No. Your router doesn't forward this port, and Tailscale is private |

For Phase 1 (just me, at home) that's an acceptable trade-off. It's also exactly what **Phase 2** fixes: who can log in, who can do what, and a record of who did it. Until then: **don't put guests on the same Wi-Fi as the Studio**, or use your router's guest network for them.

---

## Changing models later

1. Edit `MODEL_MAIN` / `MODEL_FAST` in `01-environment/standard.sh`
2. On the Studio: `bash server_setup.sh`
3. Optional: remove an old model with `ollama rm <name>`

---

## Gotchas

| Symptom | Fix |
|---|---|
| `server_setup.sh` stops: profile is not studio | Run it on the Mac Studio only |
| Port already in use | The Ollama desktop app is also running. Quit it and remove it from Login Items. |
| MacBook can't reach the server | Tailscale on both Macs? Studio awake? Try `ping zenstudio` |
| First answer is slow, later ones fast | Normal: the model loads into memory first, then stays for 30 min |
| Studio feels sluggish | Both models loaded use ~31 GB plus working memory. Close other heavy apps, or set `OLLAMA_MAX_LOADED_MODELS=1` |

---

**Next:** Step 3, Memory
