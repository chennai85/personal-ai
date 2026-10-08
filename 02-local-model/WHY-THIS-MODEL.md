# Why This Model

A decision record: what I chose, what I compared, and why. Written before Step 2, so the reasoning is captured before the results.

> **The story** is on the blog: [Before the Model, the Use Case](https://www.aishree.me/personal-ai)

---

## Decision

| Role | Model | Ollama tag | Download | License |
|---|---|---|---|---|
| **Main** | Qwen 3.6 35B-A3B | `qwen3.6:35b-a3b` | ~24 GB | Apache 2.0 |
| **Fast / fallback** | Gemma 4 E4B | `gemma4:e4b` | ~7 GB | Apache 2.0 |

Both run on the Mac Studio (`zenstudio`) through Ollama. The fast model also fits the iMac if the Studio is off.

---

## Step 1: Start from the use cases, not the model

The model has to serve what I'll actually use. My first three:

| Use case | What the model must do |
|---|---|
| Trading research (research and learning only; I decide and execute) | Read filings and news, summarize, compare, reason |
| Life admin (bills, email, documents, subscriptions) | Read documents and images, extract dates and amounts, use tools |
| Sales / BizDev assistant for small businesses (later product) | Follow a process, write, use tools, and be legally usable in a product |

How I got to these: [use-case research summary](#use-case-research) below.

---

## Step 2: Requirements

| Requirement | Why |
|---|---|
| Fits in memory with headroom | Studio has 48 GB. macOS uses 6–10 GB, leaving ~38–40 GB. Long conversations need extra memory on top of the model. |
| Fast | Three Macs may ask at once. A slow assistant doesn't become a habit. |
| Tool use | Step 5 agents call calendars, files, and data. |
| Reads images | Statements, screenshots, and receipts arrive as images. |
| Current | Avoid rebuilding in three months. |
| Commercial-friendly license | Phase 3 is a product. |

---

## Step 3: Candidates

| Model | Ollama tag | Download | Type | Verdict |
|---|---|---|---|---|
| **Qwen 3.6 35B-A3B** | `qwen3.6:35b-a3b` | ~24 GB | Mixture of experts: 35B total, ~3B active per word | ✅ Main |
| Qwen 3.6 27B | `qwen3.6:27b` | ~17 GB | Dense: all 27B active | Runner-up. Slightly better quality, slower. Test later. |
| Gemma 4 31B | `gemma4:31b` | ~20 GB | Dense | Solid, slower |
| **Gemma 4 E4B** | `gemma4:e4b` | ~7 GB | Small | ✅ Fast / fallback |
| Llama 3.1 70B | `llama3.1:70b` | ~40 GB | Dense | ❌ Too big for 48 GB, older |

Sizes are the default (4-bit) downloads listed on Ollama in October 2026.

---

## Why Qwen 3.6 35B-A3B

- **Speed from its design.** It has 35B parameters, but only ~3B are used for each word, like a team of specialists where only the right few speak up. Third-party guides estimate roughly 40–70 tokens per second on Macs in this class. *To be measured in Step 2.*
- **Fits with room.** ~24 GB leaves ~14 GB for conversation memory and the OS.
- **Does what the use cases need:** reads text and images, uses tools, and has a step-by-step "thinking" mode.
- **Long context.** It natively handles very long inputs, useful for statements and filings. We'll cap it lower to save memory.
- **Apache 2.0.** Free to use, modify, and build products on.

## Why a second model

- **Speed** for quick tasks (sorting email, short answers).
- **Fallback** when the Studio is busy or off.
- **A different company** (Google vs Alibaba): a built-in comparison, and no single-vendor lock-in.

---

## What I'm not doing (yet)

| Not doing | Why |
|---|---|
| Fine-tuning a model on my data | Memory and retrieval (Step 3) give most of the personal touch, without retraining. |
| Picking "the best" model | There isn't one for long. Good enough plus easy to swap beats perfect. |
| Running everything locally forever | Some tasks (deep research, long writing) may go to a cloud model, by my choice. Local is the default, not a rule. |

---

## How to change this decision later

The model is the most replaceable part of the system. Switching should take one command:

```bash
ollama pull <new-model>
```

Then point the scripts at the new tag. Step 2 makes the tag a single setting.

**Revisit when:** a new model fits the same memory and is clearly better at tool use or speed on *my* tasks, measured on the Studio rather than taken from a leaderboard.

---

## Use-case research

A short summary of what shaped the list (October 2026):

| Finding | Source |
|---|---|
| Money is the top stress for Americans (~40% rank it top-two) | APA Stress in America |
| 64% of US adults use AI; 25% daily; parents 84% vs non-parents 56% | Menlo Ventures, *State of Consumer AI 2026* |
| AI use for paying bills and health care navigation is low (~23–25% of people doing those tasks) | Menlo Ventures |
| The barrier is **trust**, not capability. 76% of non-users cite privacy. | Menlo Ventures |
| People want AI that anticipates needs (66%) and explains instead of just answering (67%) | Prophet 2026; Menlo Ventures |

**Takeaway:** the most painful problems are the most private ones. A private, local AI addresses exactly that gap.

---

## Sources

- [Ollama: qwen3.6 tags](https://ollama.com/library/qwen3.6/tags)
- [Ollama: gemma4 tags](https://ollama.com/library/gemma4/tags)
- [Qwen3.6-35B-A3B release overview (NYU Shanghai RITS)](https://rits.shanghai.nyu.edu/ai/qwen3-6-35b-a3b-alibaba-open-sources-a-frontier-class-agentic-coder/)
- [Gemma 4 under Apache 2.0 (Google Open Source Blog)](https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html)
- [Best Local LLM for 48GB RAM (2026)](https://openclawdc.com/blog/best-local-llms-48gb-ram/)
- [Menlo Ventures: State of Consumer AI 2026](https://menlovc.com/perspective/2026-the-state-of-consumer-ai/)
- [Prophet: 2026 AI Consumer Report](https://prophet.com/2026/04/the-2026-ai-powered-consumer-report/)
- [APA stress data via Stacker](https://stacker.com/health/these-were-biggest-sources-stress-americans-last-year)
