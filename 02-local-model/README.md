# Step 2: A Local Model

A private model running on the Mac Studio, shared with the iMac and MacBook over Tailscale.

> **Status:** model chosen, build in progress.
> Read first: [Why this model](WHY-THIS-MODEL.md)

---

## The plan

| # | Task | Done when |
|---|---|---|
| 1 | Install Ollama on the Mac Studio | `ollama --version` works |
| 2 | Pull the models: `qwen3.6:35b-a3b` and `gemma4:e4b` | Both appear in `ollama list` |
| 3 | Let the other Macs reach it over Tailscale | The iMac gets an answer from `http://zenstudio:11434` |
| 4 | Measure real speed on the Studio | Tokens per second, written down |
| 5 | Re-run `verify.sh` on all three Macs | "model server reachable" turns from WARN to PASS |

Commands, scripts, and results will be added here as each task is done.
