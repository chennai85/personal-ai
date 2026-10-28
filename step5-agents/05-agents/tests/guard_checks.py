"""Direct checks on guarded_call: guards a single-agent, read-only setup never exercises."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402

ran = []
agent.TOOLS["other_read"] = {"tier": "read", "check": agent.check_nothing,
                             "run": lambda: ran.append("other_read") or {}, "what": "", "schema": {}}
agent.TOOLS["fake_send"] = {"tier": "act", "check": agent.check_nothing,
                            "run": lambda: ran.append("fake_send") or {}, "what": "", "schema": {}}

_, why = agent.guarded_call("earnings", "other_read", {})
print("OFF_LIST blocked:", why)
agent.AGENTS["earnings"]["tools"].append("fake_send")      # even if someone adds it to the list
_, why = agent.guarded_call("earnings", "fake_send", {})
print("ACT_TIER blocked:", why)
print("RAN", ", ".join(ran) or "none")
w = agent.tool_read_watchlist()
print("WATCHLIST", w["tickers"], "skipped", w.get("skipped_lines", 0))
