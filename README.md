# Building My Personal AI

The build notes for a personal AI, made one layer at a time on my own Macs.

- **The why** lives on the blog: [aishree.me/personal-ai](https://www.aishree.me/personal-ai)
- **The how** lives here: setup steps, scripts, and code you can run yourself
- **The framework** behind it: [One Self, Many Agents](https://learn.aishree.me/one_self_many_agents.html)

---

## The steps

| # | Step | What gets built | Status |
|---|---|---|---|
| 1 | [The Workbench](01-environment/) | A clean, verified AI environment on every Mac | ✅ Ready |
| 2 | A Local Model | A private model running on the Mac Studio | Next |
| 3 | Memory | A memory layer that belongs to me | Planned |
| 4 | Values | A short set of rules the AI must follow | Planned |
| 5 | First Agent | One agent that does one useful thing | Planned |

Each step folder has its own README with exact commands, what to expect, and what went wrong along the way.

---

## The setup

| Machine | Role |
|---|---|
| Mac Studio | Model server: runs the AI |
| iMac | Desk work and learning |
| MacBook | Coding and travel |

The Macs talk to each other over Tailscale, a private network. AI requests go between my own machines, not to an outside service.

---

## Follow along

You don't need three Macs. One Mac with Apple Silicon and enough free disk is enough to start. If it's your only Mac, use the `studio` profile in Step 1: it runs the models and uses them on the same machine.

Questions or ideas: [aishree.me](https://www.aishree.me)
