# Step 4: Values · Decision Record

## The question

How do I make the AI follow my values, and know for certain they haven't been changed behind my back?

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Who writes it | **Me**, in my own words, from my past sessions | Values the AI wrote for me would be its values |
| Where | `~/vault/values/constitution.md`; a generic example in the repo | It's personal. Same rule as all vault data |
| Format | Plain Markdown, one rule per line | Readable, diffable, and the model reads it as-is |
| How the model sees it | At the top of every `ask` prompt, before the answer rules | First thing read; applies to every answer |
| Change control | Approved copy + SHA-256 fingerprint in `~/vault/.values/` | Any change, by anyone or anything, is caught before the next answer |
| On a change | **BIG RED FLAG**, show the exact diff, stop. No fallback to the old version | Silently using the old copy would hide the problem. I need to see it |
| Missing file | Red flag too, once it's been approved | Deleting the rules is a change |
| Lock | `chmod 444` after approval; `values unlock` to edit | Editing takes a deliberate step |
| History | Every approved version, dated | I can see how my values moved over time |
| Testing | `values test`: 8 temptations, I judge | Whether it held the line is a judgment call. That's mine |
| Search | `values/` never indexed | The rules are instructions, not memories to retrieve |
| Hard limits | Enforced in code, not only in the constitution | A model can be argued around. A missing tool can't |

---

## Not yet

| Later | Why |
|---|---|
| A guard on each agent tool | Step 5: the first agents get tools, each with its own check in code |
| Sign the fingerprint | Same-user tampering could rewrite both files. Fine for one person on one Mac; revisit with remote access |
| Run `values test` after every model change | A new model may hold the line differently |
