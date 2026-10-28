"""
A stand-in for Ollama's chat endpoint with tool calling, for testing agent.py without a Mac Studio.

It is NOT a real model. It reads the question and behaves in fixed ways:
  - names tickers (capital words)  → calls earnings_dates with them, then answers from the results
  - mentions "watchlist"           → calls read_watchlist first
  - "CALL_SEND"                    → tries a tool that doesn't exist (send_email)
  - "BAD_ARGS"                     → passes a ticker that isn't a ticker
  - "LOOP"                         → keeps asking for tools forever
  - "MAKE_UP"                      → answers with a date the tool never gave
  - "NO_TOOL"                      → answers straight away, no tool

    python3 mock_agent_ollama.py 11998
"""
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

SKIP = {"CALL_SEND", "BAD_ARGS", "LOOP", "MAKE_UP", "NO_TOOL", "I", "AND", "WHEN", "DO", "DOES"}


def call(name, args):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def say(text):
    return {"role": "assistant", "content": text}


def reply(messages):
    q = next(m["content"] for m in messages if m["role"] == "user")
    tools_done = [m for m in messages if m["role"] == "tool"]
    if "NO_TOOL" in q:
        return say("NVDA reports on 2026-11-19.")
    if "LOOP" in q:
        return call("earnings_dates", {"tickers": ["NVDA"]})
    if not tools_done:
        if "CALL_SEND" in q:
            return call("send_email", {"to": "someone@example.com", "body": "hi"})
        if "BAD_ARGS" in q:
            return call("earnings_dates", {"tickers": ["../etc/passwd"]})
        if "watchlist" in q.lower():
            return call("read_watchlist", {})
        tickers = [w for w in re.findall(r"\b[A-Z]{1,5}\b", q) if w not in SKIP]
        return call("earnings_dates", {"tickers": tickers})
    last = json.loads(tools_done[-1]["content"])
    if "blocked" in last:
        return say(f"I couldn't do that: {last['blocked']}")
    if "tickers" in last and "results" not in last:      # watchlist came back
        return call("earnings_dates", {"tickers": last["tickers"]})
    lines = []
    for r in last.get("results", []):
        lines.append(f"{r['ticker']}: {' to '.join(r['dates']) or 'no date'} ({r['status']})")
    if "MAKE_UP" in q:
        lines.append("Also AMD on 2099-12-01.")
    return say("\n".join(lines))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "qwen3.6:35b-a3b"}]})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != "/api/chat":
            return self._send({"error": "not mocked"})
        if not req.get("tools"):
            return self._send({"error": "agent must send tools"})
        self._send({"model": req["model"], "message": reply(req["messages"]), "done": True})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
