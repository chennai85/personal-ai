# Step 3: Memory

A memory that belongs to me. My files live in `~/vault` on the Mac Studio. The AI builds a search index from them, finds the passages that matter, and (next) answers from them with citations.

**Status:** parts 1–2 of 4 built and tested with a stand-in model: the vault, ingest, and search. Next: answers with citations, then remember / forget / why.

---

## How it works

```
~/vault (my files)  ->  read  ->  split into passages  ->  embed  ->  index
                                                         (meaning)    (SQLite)
question  ->  search by meaning  +  search by exact words  ->  best passages  ->  (next) the model answers
```

| Piece | What it does | Choice |
|---|---|---|
| Vault | My files, readable without any software | `~/vault`, permissions 700, FileVault, never in a git repo |
| Read | Pulls the text out of each file | `.md` `.txt` `.pdf` `.docx` `.eml` `.html`. Scans are flagged, not read yet |
| Split | Long files become ~500-word passages that overlap by 80 | Each passage keeps its file name and page |
| Embed | Turns each passage into numbers that capture its meaning | `qwen3-embedding:0.6b` on the Studio's Ollama (639 MB) |
| Index | Stores passages for fast search | One SQLite file: FTS5 for exact words, vectors for meaning |
| Search | Finds the best passages for a question | Both searches, merged by rank (reciprocal rank fusion) |

**Why two searches:** meaning finds "the invoice" when the file says "statement." Exact words find `kWh`, names, amounts and dates that meaning search can blur. Each catches what the other misses.

**Why the index can be thrown away:** it's built from the files. Delete it, run `rebuild`, get the same answers. The files are the memory.

---

## Run it (Mac Studio)

```bash
cd ~/driving-range/ai-experiments/personal-ai && git pull
bash 02-local-model/server_setup.sh     # v1.3: pulls the embedding model, allows 3 loaded models
cd 03-memory
bash vault_setup.sh                     # creates ~/vault, checks privacy
uv run memory.py ingest                 # build the index
uv run memory.py search "when is my car insurance due"
uv run memory.py status
bash ../01-environment/verify.sh        # new vault checks
```

`server_setup.sh` must run again: v1.3 raises the loaded-model limit from 2 to 3. Without that, the embedding model pushes Qwen or Gemma out of memory on every search.

Put files anywhere in `~/vault` (for example `~/vault/inbox/`), then run `ingest` again. Only new and changed files are read; deleted files leave the index.

---

## Commands

| Command | Does |
|---|---|
| `ingest` | Index new and changed files, drop deleted ones |
| `search "..."` | Top 5 passages. `-k 10` for more. `--mode meaning` or `--mode words` to see each search alone |
| `status` | What's indexed, what was skipped and why, is the model reachable |
| `rebuild` | Delete the index and build it again (needed after changing the embedding model) |

Files and folders starting with `.` or `_` are skipped (`.index/`, `people/_template.md`).

---

## Tested (stand-in model, Oct 13 2026)

`bash tests/test_memory.sh` runs 21 checks in a throwaway vault with a stand-in embedding server. All pass.

| Check | Result |
|---|---|
| PDF, Word (incl. tables), email, Markdown indexed | ✅ |
| A scanned PDF is flagged, not indexed | ✅ |
| "kWh" finds the bill, page 2 (exact words) | ✅ |
| "when is the invoice due" finds a file that says "statement" (meaning) | ✅ |
| Unchanged files aren't re-embedded | ✅ |
| Changed file re-indexed; deleted file disappears from search | ✅ |
| Same top answer after `rebuild` | ✅ |
| Refuses to mix two embedding models in one index | ✅ |

**Not tested yet:** the real `qwen3-embedding` model, speed on the Studio, and the macOS-only checks (FileVault, `stat -f`). The stand-in proves the plumbing, not the quality.

## To measure on the Studio

| Test | How |
|---|---|
| Speed | `ingest` prints passages and seconds. Note it for 10, then 100 files |
| Recall | Write 10 questions about files I know. Is the right file in the top 3? |
| Meaning vs words | Run a few with `--mode meaning` and `--mode words`. Which misses what? |

---

## Files

| File | What it is |
|---|---|
| `WHY-THIS-DESIGN.md` | Decision record |
| `vault_setup.sh` | Creates `~/vault` from the template, checks privacy and the model |
| `memory.py` | ingest, search, status, rebuild |
| `vault-template/` | The blank vault (safe to be public) |
| `tests/` | `test_memory.sh`, a stand-in model, and made-up sample files |

Changed elsewhere in v1.3: `01-environment/standard.sh` (vault, embedding model, 3 loaded models), `01-environment/verify.sh` (vault checks), `02-local-model/server_setup.sh` (pulls the embedding model).
