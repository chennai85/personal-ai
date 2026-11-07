"""A stand-in model server for the monitor tests. Answers GET only, and writes down every method it saw.

    python3 mock_ollama.py PORT METHODS_FILE
    MOCK_MISSING=gemma4:e4b   leave one model out of /api/tags
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT, SEEN = int(sys.argv[1]), sys.argv[2]
MODELS = ["qwen3.6:35b-a3b", "gemma4:e4b", "qwen3-embedding:0.6b"]
MISSING = os.environ.get("MOCK_MISSING", "")


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def note(self):
        with open(SEEN, "a") as f:
            f.write(f"{self.command} {self.path}\n")

    def send(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.note()
        if self.path == "/api/version":
            self.send({"version": "0.40.3"})
        elif self.path == "/api/tags":
            self.send({"models": [{"name": m} for m in MODELS if m != MISSING]})
        elif self.path == "/api/ps":
            self.send({"models": [{"name": MODELS[0], "size_vram": 24_000_000_000,
                                   "expires_at": "2026-11-07T13:10:00.0-05:00"}]})
        else:
            self.send_response(404)
            self.end_headers()

    def refuse(self):
        self.note()
        self.send_response(405)
        self.end_headers()

    do_POST = do_PUT = do_DELETE = refuse


HTTPServer(("127.0.0.1", PORT), H).serve_forever()
