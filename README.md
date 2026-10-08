# Building My Personal AI

The build notes for a personal AI, made one layer at a time on my own Macs.

- **The why** lives on the blog: [aishree.me/personal-ai](https://www.aishree.me/personal-ai)
- **The how** lives here: setup steps, scripts, and code you can run yourself
- **The framework** behind it: [One Self, Many Agents](https://learn.aishree.me/one_self_many_agents.html)

---

## The three phases

| Phase | User | Goal |
|---|---|---|
| **1. Personal** | Just me | A private AI that works for one person |
| **2. Household** | Family | Safe for several people: who can log in, who can see and do what, a record of who did what, and the rules around it |
| **3. Product** | Small businesses | A sales and business-development assistant a small business runs itself |

A small business is a household with employees, so Phase 2 is the foundation for Phase 3.

---

## Phase 1 steps

| # | Step | What gets built | Status |
|---|---|---|---|
| 1 | [The Workbench](01-environment/) | A clean, verified AI environment on every Mac | ✅ Done on all three Macs |
| 2 | [A Local Model](02-local-model/) | A private model on the Mac Studio, shared with the other Macs | Next. [Why this model](02-local-model/WHY-THIS-MODEL.md) |
| 3 | Memory | A memory layer that belongs to me | Planned |
| 4 | Values | A short set of rules the AI must follow | Planned |
| 5 | First Agents | Trading research and life admin | Planned |

Each step folder has its own README with exact commands, what to expect, and what went wrong along the way.

---

## First use cases

| Use case | For | Note |
|---|---|---|
| Trading research | Me | Research and learning only. I decide and execute. |
| Life admin | Me, then the household | Bills, email, documents, subscriptions |
| Sales / BizDev assistant | Small businesses (Phase 3) | An established sales method with a personal touch: Challenger principles, empathy, and the AboutU approach |

---

## The setup

| Machine | Tailscale name | Memory / Disk | Role |
|---|---|---|---|
| Mac Studio | `zenstudio` | 48 GB / 1 TB | Model server: runs the AI |
| iMac | `zengaja` | 24 GB / 256 GB | Desk work and learning |
| MacBook | `zenmaruti` | — | Coding and travel |

The Macs talk to each other over Tailscale, a private network. AI requests go between my own machines, not to an outside service.

---

## Follow along

You don't need three Macs. One Mac with Apple Silicon and enough free disk is enough to start. If it's your only Mac, use the `studio` profile in Step 1: it runs the models and uses them on the same machine.

Questions or ideas: [aishree.me](https://www.aishree.me)
