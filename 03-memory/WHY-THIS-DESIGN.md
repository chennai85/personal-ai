# Step 3: Memory · Decision Record

Oct 13, 2026

---

## The question

The model from Step 2 forgets everything when the answer ends. Step 3 gives it a memory that belongs to me: on my machine, in files I can read, copy and delete.

This is the shift I call **BuWe**: the machine carries the understanding (buddhi); I keep the discernment (viveka). Memory is what makes the machine's understanding *mine* rather than generic.

---

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Source of truth | **Plain files** in `~/vault` | Readable without software. The index is derived and disposable |
| Where | Mac Studio only, `chmod 700`, FileVault, never in a git repo | Code goes to GitHub. Data never does. `verify.sh` checks all of it |
| Search | **Hybrid**: meaning (vectors) + exact words (SQLite FTS5), merged by rank | Meaning finds "invoice" for "statement"; words find `kWh`, names, amounts |
| Embedding model | `qwen3-embedding:0.6b` (639 MB) | Small, long context (32K), multilingual, served by the same Ollama |
| Alternative | `embeddinggemma-2:270m` | Released Oct 2026; confirm its license before using. A bake-off on my own files decides |
| Vector store | Vectors in the same SQLite file, searched with NumPy | One file, no extra dependency. Fast enough for tens of thousands of passages. Move to `sqlite-vec` only if it gets slow |
| Passage size | ~500 words, 80 overlap | Big enough for context, small enough to be specific. One setting in `standard.sh` |
| Loaded models | `OLLAMA_MAX_LOADED_MODELS` 2 → 3 | Otherwise the embedding model evicts Qwen or Gemma on every search |
| Settings | All in `standard.sh` (v1.3); `memory.py` reads it | One source of truth, same as Steps 1–2 |
| Model change | Refused until `rebuild` | Vectors from two models can't be compared |
| Scans | Flagged, not read | Reading images (Qwen vision) comes later |
| Testing | A stand-in embedding server + made-up files | The plumbing is tested anywhere; quality is measured on the Studio |

---

## Not yet

| Later | Why |
|---|---|
| Answers with citations (`ask`) | Part 3: the model reads the passages and cites file and page |
| `remember`, `forget`, `why` | Part 4: write-back and control |
| Access from the other Macs and the phone | A small service on the Studio, over Tailscale only |
| Encrypted backup + restore test | Before real data goes in |
| Scans and photos | Qwen's vision, as a separate reading step |
