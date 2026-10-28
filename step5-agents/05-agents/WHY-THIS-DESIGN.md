# Why this design: Step 5, First Agents

| Decision | Choice | Why |
|---|---|---|
| First agent | Earnings dates for stock tickers | Small, useful every week, public data. If something goes wrong, nothing private leaks and nothing irreversible happens |
| Framework | None. Plain Python and Ollama's tool calling | About 350 lines I can read end to end. The guards are mine, in one function, not inside a library |
| Model | `qwen3.6:35b-a3b` (from `standard.sh`) | Already loaded, supports tools. Swapping it is still one line |
| Who decides | The model chooses a tool. The code decides if it's allowed | A model can be talked around. A guard in code can't (Step 4: values say, code does) |
| Tiers | `read` only in Phase 1. `draft` and `act` come later | Every new tier gets its own guard before any tool uses it |
| Send, delete, pay, trade | Not built | A tool that doesn't exist can't be misused. Trading stays mine, always |
| Facts | Printed by the code from the tool's results, under the model's sentence | The model writes the sentence. The numbers come from the source, unchanged |
| Date check | Every YYYY-MM-DD in the answer must appear in the tool's results | Catches a made-up date. Same idea as "cite every fact" in Step 3 |
| Budget | 4 tool calls per question | A loop costs time and calls to Yahoo. 4 covers watchlist + dates with room to spare |
| Ledger | `~/vault/.agents/ledger.jsonl`, append only, 600 | Who did what, when. The seed of Phase 2's "accounting". Stores question length, not words |
| Data source | Yahoo Finance via yfinance | No key, no account. Unofficial, so it can break or be wrong; the facts table names the source |
| Window vs date | Two dates from Yahoo = "window, not confirmed" | An estimate shouldn't look like a fact |
| Constitution | Reused from `03-memory/memory.py` (`load_constitution`) | One check, one place. A changed constitution stops the agent like it stops `ask` |
| Watchlist | A line counts only if every word on it is a ticker as written | Text in my own files must never become instructions or tickers. This is the first side-door guard |
| `--direct` | Same tool without the model | A baseline. If the agent and the direct run disagree, the agent is wrong |
| Run | On demand, from the command line | Scheduling (a brief before 4 am) comes after the real runs look right |
