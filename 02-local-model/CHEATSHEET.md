# Cheat Sheet: Talking to the Model

The models live on the Mac Studio. Every other device reaches them over Tailscale.

| | Value |
|---|---|
| Server address | `http://zenstudio:11434` |
| Main model (depth) | `qwen3.6:35b-a3b` |
| Fast model (quick tasks) | `gemma4:e4b` |
| Works from | Anywhere, as long as **Tailscale is on** and the **Studio is awake** |

---

## Mac Studio

```bash
ollama run qwen3.6:35b-a3b                  # chat with the main model
ollama run gemma4:e4b                       # chat with the fast model
ollama run qwen3.6:35b-a3b --think=false    # skip the "thinking" part, answer directly
ollama run gemma4:e4b "Your question here"  # one question, no chat
```

---

## MacBook and iMac

**One-time setup** (on each Mac):

```bash
brew install ollama
echo 'export OLLAMA_HOST=zenstudio:11434' >> ~/.zshrc
exec zsh
```

This installs only the `ollama` command. Models are **not** downloaded; every question goes to the Studio.

**Then, same commands as on the Studio:**

```bash
ollama run qwen3.6:35b-a3b
ollama run gemma4:e4b "Your question here"
ollama ps        # which models are loaded on the Studio right now
ollama list      # which models the Studio has
```

**No-install option** (any Mac, one question):

```bash
curl -s $MODEL_BASE_URL/api/generate \
  -d '{"model":"gemma4:e4b","prompt":"Your question here","stream":false,"think":false}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["response"])'
```

---

## iPhone

1. **Tailscale** from the App Store. Sign in with the **same account** as the Macs, and turn it on.
2. **A chat app that connects to your own Ollama server**, for example:
   - **Reins** (free download; some features need a subscription)
   - **Enchanted** (free, open source; check it is still being updated before relying on it)
3. In the app, add a server: `http://zenstudio:11434`
   - If the name doesn't work, use the Studio's Tailscale IP instead (shown in the Tailscale app next to `zenstudio`), e.g. `http://100.x.y.z:11434`
4. Pick a model: start with `gemma4:e4b` on the phone (fastest), `qwen3.6:35b-a3b` for harder questions.

Your questions go from the phone to the Studio over Tailscale. No cloud AI service sees them. The app itself is third-party, so check its privacy policy.

---

## Chat commands (inside `ollama run`)

| Type | Does |
|---|---|
| `/bye` | Leave the chat |
| `/clear` | Forget the conversation so far |
| `/set nothink` | Turn off "thinking" for this chat |
| `/show info` | Details about the current model |
| `"""` | Start/end a multi-line message |

---

## When it doesn't work

| Symptom | Check |
|---|---|
| Can't connect at all | Tailscale on? `ping zenstudio` from a Mac |
| Worked earlier, not now | Studio asleep or logged out. Wake it; log in once after a restart |
| First answer slow, then fast | Normal. The model loads into memory, then stays for 30 min |
| `model not found` | Check the exact name: `ollama list` |
| iPhone app can't reach `zenstudio` | Use the Studio's Tailscale IP instead of the name |

**Remember:** the server has no password yet. Anyone on your home Wi-Fi could use it. Guests go on a separate Wi-Fi until Phase 2.
