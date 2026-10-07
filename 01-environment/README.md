# Step 1: The Workbench

Setting up a Mac for AI work, from a clean machine to a verified environment.

> **The why** is on the blog: [Starting From a Clean Machine](https://www.aishree.me/personal-ai)
> This page is **the how**.

---

## The idea

Three Macs, one standard, one model server.

| Machine | Profile | Role | Local models |
|---|---|---|---|
| Mac Studio | `studio` | Runs the AI models for the whole house | Up to 400 GB |
| iMac | `imac` | Desk work and learning | Up to 20 GB |
| MacBook | `macbook` | Coding and travel | Up to 10 GB |

The Mac Studio does the heavy thinking. The iMac and MacBook send their requests to it over **Tailscale**, a private network between your own devices. Each machine finds the server through one setting: `MODEL_BASE_URL`.

Every machine follows the same **Driving Range Standard**, so a project started on one Mac works on the others.

---

## What gets installed

| Piece | What it is | Why |
|---|---|---|
| Xcode Command Line Tools | Apple's compilers | Needed to build Python and other tools |
| Homebrew | Package manager for Mac | One command to install everything else |
| git | Version control | Track every change, share on GitHub |
| pyenv | Python version manager | One clean Python, not the system one |
| Python 3.13.1 | The language most AI tools use | Pinned so every machine matches |
| uv | Fast Python package manager | Each project gets its own isolated packages |
| Tailscale | Private network | Lets the Macs talk to the model server from anywhere |

What is deliberately **not** installed: Anaconda and the python.org installer. Both put their own Python on your PATH and fight with pyenv.

---

## Folder layout

```
~/driving-range/
├── ml-playground/     machine learning experiments
├── ai-experiments/    AI and agent projects (this series lives here)
├── trading-tools/
├── aboutu/
├── scripts/           setup scripts and audit reports
└── scratch/           throwaway work
```

Type `dr` in any terminal to jump there.

---

## Run it

### 1. Get the files

```bash
mkdir -p ~/driving-range/ai-experiments
cd ~/driving-range/ai-experiments
git clone https://github.com/<your-username>/personal-ai.git
cd personal-ai/01-environment
```

On a brand-new Mac, `git` may not exist yet. Running `git` once will prompt macOS to install the Command Line Tools. Accept, wait, then run the clone again.

### 2. Run setup with the machine's profile

```bash
bash setup.sh imac      # or: macbook, studio
```

The script is safe to run more than once. It only adds what's missing and never deletes anything.

Expect:
- A password prompt when Homebrew installs
- A few minutes while Python builds
- A short "still to do by hand" list at the end (usually Tailscale)

### 3. Install Tailscale (by hand)

1. Download from [tailscale.com/download/mac](https://tailscale.com/download/mac) or the Mac App Store
2. Sign in with the same account on every Mac
3. On the Mac Studio, set its machine name to `mac-studio` in the Tailscale admin console, and make sure **MagicDNS** is on (it's what lets the other Macs reach it by that name)

### 4. Verify

Open a **new** terminal window (so it picks up the new settings), then:

```bash
bash verify.sh
```

You get a report like this, also saved to `~/driving-range/scripts/audits/`:

```
# host=iMac profile=imac time=2026-10-07 19:10:02 standard=v1.1
# pass=30 warn=1 fail=0
PASS|profile declared|imac
INFO|role|desk work and learning
PASS|root dir|/Users/you/driving-range
...
PASS|MODEL_BASE_URL|http://mac-studio:11434
WARN|model server reachable|no answer from http://mac-studio:11434 (expected until step 2)
PASS|free disk|412 GB (min 50)
```

**Done when:** `fail=0`. The one WARN is expected: the model server is set up in Step 2.

---

## Changing the standard

All settings live in one file: [`standard.sh`](standard.sh). Folder names, Python version, profiles, disk limits.

Change a value there, run `setup.sh` again, then `verify.sh`. Both scripts read the same file, so they can't drift apart.

---

## Files

| File | Purpose |
|---|---|
| `standard.sh` | The Driving Range Standard: every setting in one place |
| `setup.sh` | Builds the workbench for a given profile |
| `verify.sh` | Checks a machine against the standard and saves a report |

---

## Gotchas

| Symptom | Fix |
|---|---|
| `python3` points to `/usr/bin/python3` | Open a new terminal. If it persists, check that `~/.zshrc` has the pyenv lines |
| `pyenv install` fails with a build error | Run `xcode-select --install`, then try again |
| `MODEL_BASE_URL` FAIL right after setup | You're in the old terminal. Open a new one |
| `free disk` FAIL | Models are large. Clear space before Step 2 |

---

**Next:** [Step 2: A Local Model](../02-local-model/) (coming soon)
