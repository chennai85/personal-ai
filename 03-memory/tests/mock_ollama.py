"""
A stand-in for Ollama's embedding endpoint, for testing memory.py without a Mac Studio.

It is NOT a real model. It hashes words into 256 numbers and folds a few
synonyms together, so "invoice" and "bill" land near each other. Enough to test
the plumbing: ingest, index, search, change and delete. Real quality is measured
on the Studio with the real model.

    python3 mock_ollama.py 11999
"""
import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DIM = 256
SYNONYMS = {"invoice": "bill", "payment": "bill", "statement": "bill",
            "vacation": "trip", "travel": "trip", "holiday": "trip",
            "physician": "doctor", "appointment": "doctor", "clinic": "doctor",
            "automobile": "car", "vehicle": "car", "insurance": "policy"}


def vec(text):
    v = [0.0] * DIM
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        w = SYNONYMS.get(w, w)
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        v[h % DIM] += 1.0
    return v


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
        if self.path == "/api/tags":
            self._send({"models": [{"name": "qwen3-embedding:0.6b"}]})
        else:
            self._send({"version": "mock"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        inputs = req["input"] if isinstance(req["input"], list) else [req["input"]]
        # strip the query instruction, like a real model would read past it
        inputs = [t.split("Query: ", 1)[-1] for t in inputs]
        self._send({"model": req["model"], "embeddings": [vec(t) for t in inputs]})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
