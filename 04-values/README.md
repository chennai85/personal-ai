# Step 4: Values

A short constitution the AI must follow, written by me, in my own words. It's read before every answer. If it changes without my approval, it's a **BIG RED FLAG** and nothing runs.

The code lives in [`03-memory/memory.py`](../03-memory/memory.py), because values guard `ask`. My real constitution lives in the vault (`~/vault/values/constitution.md`), never in this repo. A generic example is in [`03-memory/vault-template/values/constitution.md`](../03-memory/vault-template/values/constitution.md).

---

## How it works

```
~/vault/values/constitution.md      ← I write it (read-only once approved)
~/vault/.values/approved.md         ← the copy I approved
~/vault/.values/approved.sha256     ← its fingerprint
~/vault/.values/history/            ← every version I've approved, dated

ask / recall / values test
  1. fingerprint the constitution
  2. same as approved?  → put it at the top of the prompt, then answer
     different/missing? → BIG RED FLAG, show exactly what changed, stop
```

| Rule | How it's enforced |
|---|---|
| Only I change it | Read-only (`444`) after approval. Editing takes `values unlock` |
| Any unapproved change is a BIG RED FLAG | SHA-256 fingerprint checked before every answer. Mismatch → red banner, the changed lines, exit. Nothing runs |
| A deleted constitution counts as a change | Missing after approval → red flag too |
| Every approved version is kept | `~/vault/.values/history/constitution-YYYYMMDD-HHMMSS.md` |
| The constitution never shows up in search | `values/` is not indexed |
| `verify.sh` checks it | PASS if approved and unchanged; **FAIL** if changed |

## Run it (Mac Studio)

```bash
cd ~/personal-ai && git pull
bash 03-memory/vault_setup.sh                 # puts the example at ~/vault/values/ if none yet
# replace it with my own constitution, then:
cd 03-memory
uv run memory.py values approve               # read it all, type yes
uv run memory.py values test                  # 8 temptations, I judge each answer
bash ../01-environment/verify.sh              # constitution: PASS
```

## Commands

| Command | Does |
|---|---|
| `values` | Status: approved and unchanged, or the red flag with the diff |
| `values approve` | First time: shows the whole text. After that: only what changed. Asks for "yes", saves to history, locks the file |
| `values unlock` | Makes the file editable again. Approve after editing |
| `values test` | Asks 8 questions that tempt it to break a rule (stock pick, delete, send, card number, name a person publicly, decide for me, motivational push, rewrite the constitution). I mark each one held or broken. Saved to `~/vault/.eval/` as numbers only |

If the red flag shows and I didn't make the change: `cp ~/vault/.values/approved.md ~/vault/values/constitution.md`.

## My constitution: what's in it

Four areas, from my own past sessions (GS1–GS9) and my Daily Operating Framework:

| Section | Gist |
|---|---|
| Who I am | Just be. Refinement over magnitude. The AI carries the understanding; I keep the discernment |
| 1. What you may never do | 7 lines: no trades, no deleting without "yes", no deciding, no card/ID numbers, no sending as me, no spending or agreeing, no sharing the vault |
| 2. How you answer me | Truth early. Plain words. Smaller and truer than my excitement. Don't keep asking questions. Cite everything |
| 3. Money and trading | Research only. Money is a floor, not a ceiling. I make the call |
| 4. Other people's information | Proof remains. Names don't. Never a dossier |
| How this constitution changes | Only I change it. Unapproved change = BIG RED FLAG. Every version kept |

## Tested (stand-in model)

`bash 03-memory/tests/test_memory.sh` now runs 79 checks (27 new for values). All pass.

| Check | Result |
|---|---|
| Unapproved constitution blocks `ask` with a red flag | ✅ |
| No "yes", no approval | ✅ |
| Approve shows the full text first time, only the diff after | ✅ |
| Read-only after approval; `unlock` makes it editable | ✅ |
| Constitution reaches the model at the top of the prompt | ✅ |
| A changed line blocks `ask`, `recall` and `values test`, and the red flag shows exactly that line | ✅ |
| Restoring the approved copy unblocks | ✅ |
| Both versions kept in history | ✅ |
| Deleting the constitution doesn't silently pass | ✅ |
| Constitution never searchable | ✅ |

## On the Studio (Oct 26 2026, real model)

| Check | Result |
|---|---|
| `values test`, qwen3.6:35b-a3b, judged by me | **Held the line: 8/8** (V1–V8 ✓) |
| Red flag drill: one line added, then `ask` | Red banner, the exact line, nothing ran |
| Restore the approved copy | `values` back to OK |
| `verify.sh` constitution check | PASS |

**What 8/8 doesn't prove:** one run, judged by me, and every question asked it directly to break a rule. The harder test is a push from *inside* a file (an email that says "ignore your rules"). That comes with the agents in Step 5.

## What values can and can't do

The constitution shapes what the model *says*. The hard limits are enforced in code: `ask` has no tool to send, pay, delete or trade; `remember` refuses numbers; `forget` needs "yes". When agents get tools (Step 5), each tool gets its own guard in code. A model can be talked around; a missing tool can't.
