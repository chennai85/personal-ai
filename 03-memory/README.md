# Step 3: Memory

A memory that belongs to me. My files live in `~/vault` on the Mac Studio. The AI builds a search index from them, finds the passages that matter, and answers from them with citations.

**Status:** ✅ Step 3 closed (Oct 26 2026). All 4 parts run on the Studio with the real models: vault, ingest and search, answers with sources, remember and forget. Recall test: right file in the top 3 for 6/6 questions, answers right 4/6, honest 1/1. Left open on purpose: backup, scans, access from other devices, 16 passages.

---

## How it works

```
~/vault (my files)  ->  read  ->  split into passages  ->  embed  ->  index
                                                         (meaning)    (SQLite)
question  ->  search by meaning  +  search by exact words  ->  best 8 passages  ->  Qwen answers, citing [1] [2]…
```

| Piece | What it does | Choice |
|---|---|---|
| Vault | My files, readable without any software | `~/vault`, permissions 700, FileVault, never in a git repo |
| Read | Pulls the text out of each file | `.md` `.txt` `.pdf` `.docx` `.eml` `.html`. Scans are flagged, not read yet |
| Split | Long files become ~500-word passages that overlap by 80 | Each passage keeps its file name and page |
| Embed | Turns each passage into numbers that capture its meaning | `qwen3-embedding:0.6b` on the Studio's Ollama (639 MB) |
| Index | Stores passages for fast search | One SQLite file: FTS5 for exact words, vectors for meaning |
| Search | Finds the best passages for a question | Both searches, merged by rank (reciprocal rank fusion) |
| Answer | The main model reads the passages and answers | `qwen3.6:35b-a3b`. Only from the passages, cites each fact, says "Not in my memory" otherwise |

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
| `ask "..."` | Qwen answers from the best 8 passages, with sources. `-k 12` to read more; `--think` to let it reason first (slower) |
| `remember "..."` | Save something I tell it, in my own words, to `~/vault/notes/YYYY-MM.md`. Searchable at once. Refuses card, account and Social Security numbers, and passwords |
| `forget FILE` | Delete a file from the vault **and** from memory (asks first) |
| `forget --note "words"` | Remove remembered lines containing those words (asks first) |
| `recall` | Score my own test questions: right file in the top 3? Right answer? "Not in my memory" when it should? `--no-ask` checks search only (fast) |
| `status` | What's indexed, what was skipped and why, is the model reachable |
| `rebuild` | Delete the index and build it again (needed after changing the embedding model) |

Files and folders starting with `.` or `_` are skipped (`.index/`, `people/_template.md`).

**Cleaning before indexing (v2):**
- Template lines I haven't filled in (`⟪ ⟫`) are left out, so blank templates don't show up in search.
- Header and footer lines that repeat on most pages of a PDF are removed, so the page with the answer isn't buried among look-alike pages. Found on a real year-end card statement: the page with the total didn't make the top 5.
- When this cleaning changes, `ingest` re-reads every file once by itself.

---

## First run on the Studio (Oct 13 2026, real model)

| Measure | Result |
|---|---|
| `verify.sh` | 42 pass, 0 warn, 0 fail |
| Ingest, 10 template files | 10 passages, 1.2 s (includes loading the model) |
| Ingest, 2 real PDFs | 72 passages, 3.4 s |
| Search | 0.05 s |
| "old course" | Found `me/golf.md` with no shared words: meaning search works |
| A misspelled question about last year's spending | Found the year-end card statement, pages 3–6 |
| What went wrong | A blank template ranked #1, and the page with the total wasn't in the top 5. Both fixed in v2 (above) |
| A 2012 W-2 | A scan: flagged, not read yet |
| After v2 + `rebuild` | Blank templates gone from results. All 8 passages for the spending question came from the right statement, the page with the total among them (#4) |
| `ask` "what is my golf handicap" | **"Not in my memory."** The field is blank, and it didn't guess |
| `ask` "how much did I spend last year" | Answered from the year-end statement, with page citations |
| `ask` speed | First word 1.2–1.7 s · full answer 1.3–2.8 s · `qwen3.6:35b-a3b` |
| Bug found | The v2 upgrade didn't trigger: indexes built before versions were recorded looked "current". Worked around with `rebuild`, fixed so they upgrade by themselves |
| Lesson | Search snippets show what's in the file. Don't paste them into a cloud chat; share file names and pages only |

## Tested (stand-in model)

`bash tests/test_memory.sh` runs 52 checks in a throwaway vault with a stand-in model. All pass.

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
| Repeated PDF header removed; the page with the total ranks first | ✅ |
| Blank template lines not searchable; filled-in lines are | ✅ |
| `ask` streams an answer, cites [1], lists sources with page, reports timing | ✅ |
| Changing the reader version re-reads every file | ✅ |
| An index from before versions were recorded upgrades too | ✅ |
| `remember` saves a plain note, searchable at once | ✅ |
| `remember` refuses card numbers and Social Security numbers | ✅ |
| `forget --note` removes only the matching lines; others stay | ✅ |
| `forget FILE` deletes the file; its text is gone from search and from the index file | ✅ |
| `forget` refuses files outside the vault, and changes nothing without "yes" | ✅ |

**Not measured yet:** recall over a set of questions (is the right page in the top 3?) and answer accuracy. That's the next test.

## Two kinds of memory

| Kind | Where | Written by |
|---|---|---|
| Documents | Anywhere in `~/vault` (usually `inbox/`) | Me, by dropping files in |
| What I tell it | `~/vault/notes/` · one plain file per month | `remember` |

Both are plain files I can open, edit or delete. Both are found by `search` and `ask`.

**Forgetting means gone.** `forget` deletes the file or the lines, removes their passages from the index, and compacts the index file so the text can't be recovered from it. The index also overwrites deleted text with zeros (SQLite secure delete). Copies outside the vault (Time Machine, other backups) are not touched.

## The recall test

My questions about my own files, scored. The questions and results live in `~/vault/.eval/`, inside the vault and never indexed.

```bash
uv run memory.py recall            # first run creates ~/vault/.eval/questions.txt
open -e ~/vault/.eval/questions.txt
uv run memory.py recall --no-ask   # search only: is the right file in the top 3?
uv run memory.py recall            # full: answers stream, I mark each right or wrong
```

One question per line: `question | part of the file name | words the answer must contain (optional)`. Use `NONE` as the file for a question my files can't answer; it passes only if the answer says "Not in my memory".

The summary at the end is numbers only, so it's safe to share. The questions and answers stay on the Studio.

### First result (Oct 23 2026)

Vault: 9 real files, 1,015 passages (about 900 from four books, the rest my own financial files, an NDA and a one-page framework). 7 questions, 8 passages per answer.

| Measure | Result |
|---|---|
| Right file in the top 3 | **6/6** (at #1: 5/6) |
| Answer right | **4/6** |
| Said "Not in my memory" when it should | **1/1** |
| Answer time | 1.0–12.6 s, average 3.4 s (the 12.6 s was the first question: the model loading) |

Both wrong answers had the right file but needed facts spread over several pages: 8 passages weren't enough. Next to try: 16 passages (`-k 16`), then reading the neighbouring pages. Kept at 8 for now.

## To measure on the Studio

| Test | How |
|---|---|
| Speed | `ingest` prints passages and seconds. Note it for 10, then 100 files |
| Recall | Write 10 questions about files I know. Is the right file in the top 3? |
| Answers | Same 10 questions with `ask`. Right answer? Right citation? Does it say "Not in my memory" when it should? |
| Speed | `ask` prints time to first word and full answer |
| Meaning vs words | Run a few with `--mode meaning` and `--mode words`. Which misses what? |

---

## Files

| File | What it is |
|---|---|
| `WHY-THIS-DESIGN.md` | Decision record |
| `vault_setup.sh` | Creates `~/vault` from the template, checks privacy and the model |
| `memory.py` | ingest, search, ask, remember, forget, recall, status, rebuild |
| `vault-template/` | The blank vault (safe to be public) |
| `tests/` | `test_memory.sh`, a stand-in model, and made-up sample files |

Changed elsewhere in v1.3: `01-environment/standard.sh` (vault, embedding model, 3 loaded models), `01-environment/verify.sh` (vault checks), `02-local-model/server_setup.sh` (pulls the embedding model).
