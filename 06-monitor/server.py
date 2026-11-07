"""
server.py: the monitor's web page. Start it with  python3 monitor.py serve

    http://zenstudio:8765      from the iMac, the MacBook or the iPhone (Tailscale)
    http://localhost:8765      on the Studio itself

Rules (in code):
  1. Listens on this Mac (127.0.0.1) and its Tailscale address only. Never 0.0.0.0, never home Wi-Fi.
     If Tailscale isn't up yet (just after a restart), it keeps trying in the background.
  2. GET only. Five fixed addresses: /, /app.js, /app.css, /api/snapshot, /api/events.
     No file names in URLs, so no way to ask for any other file.
  3. Only answers to names it knows (zenstudio, localhost, its own addresses). A web page
     elsewhere can't point a made-up name at it and read the answers (DNS rebinding).
  4. Everything it sends comes from monitor.snapshot() or monitor.safe_event(): the same
     privacy rules as the terminal view. The page builds text only, never HTML from data.
  5. Live: /api/events tails the ledger once a second and sends each new row as it lands.
     The agents don't know the page exists. Read-only, like the rest of the monitor.
"""

import ipaddress
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import monitor

WEB = monitor.HERE / "web"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}
MAX_STREAMS = 8                                              # open pages at once (phones, Macs, tabs)
TICK = float(os.environ.get("MONITOR_TICK", "1"))           # how often the ledger is checked, seconds
SNAPSHOT_EVERY = float(os.environ.get("MONITOR_SNAPSHOT_EVERY", "15"))   # model server, Tailscale, tests
CACHE_SECONDS = 5                                            # many pages share one snapshot
TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILNET_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
                               "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                               "form-action 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def allowed_bind(addr):
    """This Mac or Tailscale. Never everywhere, never the home network."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_loopback or ip in TAILNET_V4 or ip in TAILNET_V6


def tailscale_names():
    """This Mac's Tailscale IPv4 address and the names it goes by: (address or None, {names})."""
    st, _ = monitor.tailscale_status()
    me = (st or {}).get("Self") or {}
    if (st or {}).get("BackendState") != "Running":
        return None, set()
    v4 = [a for a in me.get("TailscaleIPs") or [] if ":" not in a and allowed_bind(a)]
    names = {n.lower() for n in (me.get("HostName"), (me.get("DNSName") or "").rstrip(".")) if n}
    names |= {n.split(".")[0] for n in names}
    return (v4[0] if v4 else None), names


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.hosts = {"localhost", "127.0.0.1"}
        self.streams = 0
        self.cache = {}

    def snapshot(self, days):
        with self.lock:
            hit = self.cache.get(days)
            if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
                return hit[1]
        snap = monitor.snapshot(days=days)
        with self.lock:
            self.cache[days] = (time.monotonic(), snap)
        return snap


STATE = State()
PAGES = {}


class Handler(BaseHTTPRequestHandler):
    server_version = "monitor"
    sys_version = ""
    timeout = 15                                             # a client that sends nothing is dropped

    def log_message(self, *args):                            # no request log: nothing to keep
        pass

    # ---- the guards ----
    def host_ok(self):
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):
            host = host[1:host.find("]")]
        elif host.count(":") == 1:
            host = host.split(":")[0]
        return host in STATE.hosts

    def plain(self, code, text):
        body = (text + "\n").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in HEADERS.items():
            self.send_header(k, v)
        if code == 405:
            self.send_header("Allow", "GET")
        self.end_headers()
        self.wfile.write(body)

    def refuse(self):
        self.plain(405, "Read-only: GET only.")

    do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = do_TRACE = do_CONNECT = refuse

    def do_GET(self):
        if not self.host_ok():
            return self.plain(421, "Unknown host name.")
        url = urlsplit(self.path)
        if url.path in FILES:
            return self.send_file(url.path)
        if url.path in ("/api/snapshot", "/api/events"):
            days = parse_qs(url.query).get("days", ["7"])[0]
            if not days.isdigit() or not 1 <= int(days) <= 90:
                return self.plain(400, "days must be 1 to 90.")
            if url.path == "/api/snapshot":
                return self.send_json(STATE.snapshot(int(days)))
            return self.stream(int(days))
        return self.plain(404, "Not here.")

    # ---- answers ----
    def send_body(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        name, ctype = FILES[path]
        self.send_body(PAGES[name], ctype)

    def send_json(self, data):
        self.send_body(json.dumps(data).encode(), "application/json; charset=utf-8")

    def event(self, name, data):
        self.wfile.write(f"event: {name}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    def stream(self, days):
        with STATE.lock:
            if STATE.streams >= MAX_STREAMS:
                busy = True
            else:
                busy, STATE.streams = False, STATE.streams + 1
        if busy:
            return self.plain(503, f"{MAX_STREAMS} pages are open already. Close one.")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            for k, v in HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.tail(days)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass                                             # the page was closed
        finally:
            with STATE.lock:
                STATE.streams -= 1

    def tail(self, days):
        """Send a snapshot, then every new ledger row as it lands, and a fresh snapshot now and then."""
        opened = monitor.dt.datetime.now() - monitor.dt.timedelta(seconds=2)   # the ledger keeps whole seconds
        ino, offset = self.where()
        self.event("snapshot", STATE.snapshot(days))
        next_snap, next_ping = time.monotonic() + SNAPSHOT_EVERY, time.monotonic() + 15
        while True:
            time.sleep(TICK)
            now_ino, size = self.where()
            if now_ino != ino or size < offset:              # a new or replaced ledger: read it from the top
                ino, offset = now_ino, 0
                next_snap = time.monotonic()
            if size > offset:
                rows, _bad, used = monitor.parse_lines(monitor.read_bytes(monitor.LEDGER, offset))
                offset += used
                for r in rows:
                    if r["_t"] >= opened:                    # only rows newer than this page
                        self.event("row", monitor.safe_event(r))
                if rows:
                    next_snap = min(next_snap, time.monotonic() + 1)   # counts changed: refresh soon
            if time.monotonic() >= next_snap:
                with STATE.lock:
                    STATE.cache.pop(days, None)
                self.event("snapshot", STATE.snapshot(days))
                next_snap = time.monotonic() + SNAPSHOT_EVERY
                next_ping = time.monotonic() + 15
            elif time.monotonic() >= next_ping:
                self.wfile.write(b": ping\n\n")              # keeps phones and proxies from hanging up
                self.wfile.flush()
                next_ping = time.monotonic() + 15

    @staticmethod
    def where():
        try:
            st = os.stat(monitor.LEDGER)
            return st.st_ino, st.st_size
        except FileNotFoundError:
            return None, 0


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, port):
        if ":" in addr:
            self.address_family = socket.AF_INET6
        super().__init__((addr, port), Handler)


def listen(addr, port):
    srv = Server(addr, port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def wait_for_tailscale(port, every=30):
    """Just after a restart Tailscale may not be up. Keep trying; the Studio's own page works meanwhile."""
    while True:
        time.sleep(every)
        addr, names = tailscale_names()
        if addr:
            try:
                listen(addr, port)
            except OSError:
                continue
            with STATE.lock:
                STATE.hosts |= names | {addr}
            print(f"Tailscale is up: also on http://{sorted(names)[0] if names else addr}:{port}", flush=True)
            return


def main(args):
    for name, _ in FILES.values():
        PAGES[name] = monitor.read_bytes(WEB / name)
    if args.bind:
        binds, names = args.bind, set()
    else:
        ts, names = tailscale_names()
        binds = ["127.0.0.1"] + ([ts] if ts else [])
    bad = [b for b in binds if not allowed_bind(b)]
    if bad:
        print(f"Refused: {', '.join(bad)}. The monitor listens on this Mac and Tailscale only "
              f"(127.0.0.1, 100.64.0.0/10).", file=sys.stderr)
        return 2
    STATE.hosts |= names | set(binds)
    if args.dry_run:
        print("Would listen on: " + " ".join(f"{b}:{args.port}" for b in binds))
        print("Answers to: " + " ".join(sorted(STATE.hosts)))
        return 0
    try:
        for b in binds:
            listen(b, args.port)
    except OSError as e:
        print(f"Can't listen on port {args.port}: {e.strerror}. Is the monitor already running?", file=sys.stderr)
        return 1
    if not args.bind and len(binds) == 1:
        print("Tailscale isn't up yet. Studio only for now; trying again every 30 s.", flush=True)
        threading.Thread(target=wait_for_tailscale, args=(args.port,), daemon=True).start()
    shown = sorted(n for n in STATE.hosts if "." not in n and n != "localhost")
    where = " and ".join([f"http://localhost:{args.port}"] + [f"http://{n}:{args.port}" for n in shown])
    print(f"Monitor on {where}. Read-only. Ctrl-C to stop.", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0
