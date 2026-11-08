# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26", "pypdf>=4.0", "python-docx>=1.1", "fonttools>=4.40"]
# ///
"""
news.py: the news agent's feeds and shaping, on the Mac Studio.

    uv run news.py feeds            check every feed: works, stale, failed (counts only)
    uv run news.py preview          the stories the brief would start from, ranked by my interests (no model)

Rules (in code):
  1. Only the feeds in FEEDS are ever fetched. Never an article page, never a URL from the model.
     No logins, no paywall tricks. A paywalled outlet gets its headline, its feed summary and a link.
  2. Shaped before anything else reads it: title, outlet, time, summary. HTML stripped, entities
     unescaped, hidden characters removed, lengths capped. Full article text in a feed is thrown away.
  3. A link counts only if it's on that outlet's own domain. Query strings and fragments are dropped.
  4. A feed with a DOCTYPE or ENTITY is refused unread (feeds never need them; XML bombs do).
  5. Old stories are dropped (FRESH_HOURS). A feed whose newest story is older than STALE_DAYS is
     "stale": it looks alive but isn't (CNN's world feed stopped in Sept 2023).
  6. The same event from several outlets is grouped. One outlet only = "thin".

Interests come from ~/vault/me/interests.md (my words). Briefs are saved under ~/vault/_news/,
which memory.py ingest skips, so outside text never reaches memory search.
"""

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "03-memory"))
import memory  # noqa: E402  settings, one source of truth

S = memory.S
INTERESTS = S["vault"] / "me" / "interests.md"
BRIEFS = S["vault"] / "_news"          # "_" = memory.py ingest skips it

FRESH_HOURS = 36        # older stories are dropped (NPR's business feed is quiet on weekends)
STALE_DAYS = 7          # newest story older than this = the feed is stale
MAX_BYTES = 2_000_000   # a feed bigger than this is refused
TITLE_MAX = 200
SUMMARY_MAX = 400
BRIEF_SIZE = 12         # stories in a brief
SURPRISE_DEFAULT = 2    # big stories outside my interests, unless interests.md says otherwise
FETCH_WORKERS = 6
TIMEOUT = 15
USER_AGENT = "personal-ai-news/1.0 (one person's morning brief; reads RSS only)"

# Checked live from the iMac's browser, Nov 8 2026. "use": False = listed, checked by `feeds`, not read.
# Names are short tokens (letters, digits, "-"; at most 12) so the ledger and the monitor can show them.
FEEDS = {
    "bbc":          {"outlet": "BBC", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "domains": ("bbc.co.uk", "bbc.com"), "use": True},
    "bbc-biz":      {"outlet": "BBC", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "domains": ("bbc.co.uk", "bbc.com"), "use": True},
    "bbc-tech":     {"outlet": "BBC", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "domains": ("bbc.co.uk", "bbc.com"), "use": True},
    "bbc-india":    {"outlet": "BBC", "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "domains": ("bbc.co.uk", "bbc.com"), "use": True},
    "npr":          {"outlet": "NPR", "url": "https://feeds.npr.org/1004/rss.xml", "domains": ("npr.org",), "use": True},
    "npr-biz":      {"outlet": "NPR", "url": "https://feeds.npr.org/1006/rss.xml", "domains": ("npr.org",), "use": True},
    "npr-tech":     {"outlet": "NPR", "url": "https://feeds.npr.org/1019/rss.xml", "domains": ("npr.org",), "use": True},
    "dw":           {"outlet": "DW", "url": "https://rss.dw.com/rdf/rss-en-all", "domains": ("dw.com",), "use": True},
    "france24":     {"outlet": "France 24", "url": "https://www.france24.com/en/rss", "domains": ("france24.com",), "use": True},
    "france24-biz": {"outlet": "France 24", "url": "https://www.france24.com/en/business-tech/rss", "domains": ("france24.com",), "use": True},
    "guardian":     {"outlet": "The Guardian", "url": "https://www.theguardian.com/world/rss", "domains": ("theguardian.com",), "use": True},
    # US and India, checked live Nov 8 (3 pm). LA Times and The Hindu meter their articles; links still work.
    "bbc-us":       {"outlet": "BBC", "url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "domains": ("bbc.co.uk", "bbc.com"), "use": True},
    "nbc":          {"outlet": "NBC News", "url": "https://feeds.nbcnews.com/nbcnews/public/news", "domains": ("nbcnews.com",), "use": True},
    "cbs":          {"outlet": "CBS News", "url": "https://www.cbsnews.com/latest/rss/main", "domains": ("cbsnews.com",), "use": True},
    "cbs-us":       {"outlet": "CBS News", "url": "https://www.cbsnews.com/latest/rss/us", "domains": ("cbsnews.com",), "use": True},
    "latimes":      {"outlet": "Los Angeles Times", "url": "https://www.latimes.com/world-nation/rss2.0.xml", "domains": ("latimes.com",), "use": True, "paywall": True},
    "hindu":        {"outlet": "The Hindu", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "domains": ("thehindu.com",), "use": True, "paywall": True},
    "ndtv":         {"outlet": "NDTV", "url": "https://feeds.feedburner.com/ndtvnews-top-stories", "domains": ("ndtv.com",), "use": True},
    "indianexp":    {"outlet": "Indian Express", "url": "https://indianexpress.com/section/india/feed/", "domains": ("indianexpress.com",), "use": True},
    # Al Jazeera removed Nov 8 (Sri's choice).
    # Not read yet. `feeds` checks them on the Studio; turn one on by setting "use": True.
    "gdn-tech":      {"outlet": "The Guardian", "url": "https://www.theguardian.com/technology/rss", "domains": ("theguardian.com",), "use": False},
    "guardian-biz":  {"outlet": "The Guardian", "url": "https://www.theguardian.com/business/rss", "domains": ("theguardian.com",), "use": False},
    "nyt":          {"outlet": "New York Times", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "domains": ("nytimes.com",), "use": False, "paywall": True},
    # WSJ: stale (newest item Jan 2025). NYT and Times of India: the browser pane won't open them; `feeds` checks them.
    "wsj":          {"outlet": "Wall Street Journal", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "domains": ("wsj.com",), "use": False, "paywall": True},
    "nyt-us":       {"outlet": "New York Times", "url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml", "domains": ("nytimes.com",), "use": False, "paywall": True},
    "toi":          {"outlet": "Times of India", "url": "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms", "domains": ("indiatimes.com",), "use": False},
    "ft":           {"outlet": "Financial Times", "url": "https://www.ft.com/world?format=rss", "domains": ("ft.com",), "use": False, "paywall": True},
    "economist":    {"outlet": "The Economist", "url": "https://www.economist.com/international/rss.xml", "domains": ("economist.com",), "use": False, "paywall": True},
    "cnn":          {"outlet": "CNN", "url": "http://rss.cnn.com/rss/edition_world.rss", "domains": ("cnn.com",), "use": False},
}


class FeedRefused(Exception):
    """A feed with a DOCTYPE or ENTITY: refused unread."""


class FeedTooBig(Exception):
    """A feed over MAX_BYTES."""


class FeedNotUnderstood(Exception):
    """Not RSS, RDF or Atom."""


# ---------------------------------------------------------------------
# Fetch: only the URLs in FEEDS. NEWS_FAKE=dir stands in for the internet in tests (dir/<name>.xml).
# ---------------------------------------------------------------------
def fetch(name):
    feed = FEEDS[name]                     # KeyError for a name that isn't in the table: nothing fetched
    fake = os.environ.get("NEWS_FAKE")
    if fake:
        p = Path(fake) / f"{name}.xml"
        if not p.is_file():
            raise LookupError("no stand-in feed")
        data = p.read_bytes()[:MAX_BYTES + 1]
    else:
        req = urllib.request.Request(feed["url"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise FeedTooBig()
    return data


# ---------------------------------------------------------------------
# Shaping: what's left of a story after this is all anything downstream ever sees
# ---------------------------------------------------------------------
TAG = re.compile(r"<[^>]*>")
DROP_BLOCKS = re.compile(r"<(script|style)\b.*?</\1\s*>", re.I | re.S)


def clean_text(s, limit):
    """Plain text only: no HTML, no entities, no hidden characters, one line, at most `limit` characters."""
    if not s:
        return ""
    for _ in range(2):                     # feeds sometimes escape their HTML twice
        s = DROP_BLOCKS.sub(" ", s)
        s = TAG.sub(" ", s)
        s = html.unescape(s)
    s = DROP_BLOCKS.sub(" ", s)
    s = TAG.sub(" ", s)
    # Control and format characters (zero-width, right-to-left overrides, ...) go: text you can't see
    # is text the model would read and I wouldn't.
    s = "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        cut = s[:limit - 1]
        s = (cut.rsplit(" ", 1)[0] if " " in cut[limit // 2:] else cut) + "…"
    return s


def clean_link(url, domains):
    """https on the outlet's own domain, no login part, no port, no query, no fragment. Else None."""
    try:
        p = urlsplit((url or "").strip())
        host = (p.hostname or "").lower().rstrip(".")
        port = p.port
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or p.username or p.password or port not in (None, 80, 443):
        return None
    if not any(host == d or host.endswith("." + d) for d in domains):
        return None
    path = re.sub(r"[^A-Za-z0-9/._~%!$&'()*+,;=:@-]", "", p.path) or "/"
    return f"https://{host}{path}"


def parse_time(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        t = email.utils.parsedate_to_datetime(s)           # RSS: "Sun, 08 Nov 2026 14:06:19 GMT"
    except (TypeError, ValueError, IndexError):
        try:
            t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))   # Atom, RDF: ISO
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def child(el, *names):
    for c in el:
        if local(c.tag) in names:
            return c
    return None


def parse_feed(data):
    """RSS 2.0, RDF (RSS 1.0) or Atom → raw items. No DTDs, ever."""
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in data.lower():
        raise FeedRefused()
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise FeedNotUnderstood() from None
    if local(root.tag) not in ("rss", "RDF", "feed"):
        raise FeedNotUnderstood()
    out = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        title = child(el, "title")
        link = child(el, "link")
        href = None
        if link is not None:
            href = link.get("href") or link.text
        for c in el:                               # Atom: prefer rel="alternate"
            if local(c.tag) == "link" and c.get("rel", "alternate") == "alternate" and c.get("href"):
                href = c.get("href")
                break
        # The summary only. content:encoded / <content> (full article text) is never read.
        summary = child(el, "description", "summary")
        when = child(el, "pubDate", "published", "updated", "date")
        out.append({"title": title.text if title is not None else "",
                    "link": href, "summary": summary.text if summary is not None else "",
                    "time": when.text if when is not None else ""})
    return out


def now_utc():
    fake = os.environ.get("NEWS_NOW")      # tests pin "now" so stand-in feeds never go stale
    return dt.datetime.fromisoformat(fake) if fake else dt.datetime.now(dt.timezone.utc)


def read_feed(name, now=None):
    """One feed → {"feed", "ok", "stale", "stories", "dropped", "error"}. Never raises."""
    now = now or now_utc()
    feed = FEEDS[name]
    res = {"feed": name, "ok": False, "stale": False, "stories": [], "seen": 0, "dropped": 0, "error": None,
           "newest_hours": None}
    try:
        raw = parse_feed(fetch(name))
    except Exception as e:                 # the error's type only: its message is outside text
        res["error"] = e.__class__.__name__
        return res
    res["ok"] = True
    res["seen"] = len(raw)
    newest = None
    for it in raw:
        title = clean_text(it["title"], TITLE_MAX)
        link = clean_link(it["link"], feed["domains"])
        t = parse_time(it["time"])
        if t and (newest is None or t > newest) and t <= now + dt.timedelta(hours=2):
            newest = t
        if not title or not link or not t or t > now + dt.timedelta(hours=2) \
                or now - t > dt.timedelta(hours=FRESH_HOURS):
            res["dropped"] += 1
            continue
        res["stories"].append({"feed": name, "outlet": feed["outlet"], "title": title,
                               "summary": clean_text(it["summary"], SUMMARY_MAX), "link": link,
                               "time": t.astimezone(dt.timezone.utc).isoformat(timespec="minutes"),
                               "paywall": bool(feed.get("paywall"))})
    if newest is not None:
        res["newest_hours"] = round((now - newest).total_seconds() / 3600, 1)
    if newest is None or now - newest > dt.timedelta(days=STALE_DAYS):
        res["stale"] = True
        res["dropped"] += len(res["stories"])
        res["stories"] = []
    return res


# ---------------------------------------------------------------------
# Grouping: the same event from several outlets becomes one story
# ---------------------------------------------------------------------
STOP = set("""the a an and or but of to in on at for from by with as is are was were be been has have had
its it this that these those after over into about amid says said will would could new more than not
what who why how when where up out off his her their they he she we you your our us live latest""".split())


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP}


def same_event(a, b):
    wa, wb = words(a["title"]), words(b["title"])
    shared = wa & wb
    return len(shared) >= 2 and len(shared) / max(1, len(wa | wb)) >= 0.25


def group(stories):
    """Union of stories that look like the same event. Thin = all from one outlet."""
    parent = list(range(len(stories)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(stories)):
        for j in range(i + 1, len(stories)):
            if same_event(stories[i], stories[j]):     # one outlet's two stories on an event: one story
                parent[find(j)] = find(i)
    groups = {}
    for i, s in enumerate(stories):
        groups.setdefault(find(i), []).append(s)
    out = []
    for members in groups.values():
        members.sort(key=lambda s: s["time"], reverse=True)
        outlets = sorted({s["outlet"] for s in members})
        out.append({"lead": members[0], "members": members, "outlets": outlets, "thin": len(outlets) == 1})
    return out


def gather(names=None, now=None):
    """Read the feeds (in parallel), drop repeats, group. → {"feeds": [...], "groups": [...]}"""
    now = now or now_utc()
    names = names or [n for n, f in FEEDS.items() if f["use"]]
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        feeds = list(pool.map(lambda n: read_feed(n, now), names))
    seen, stories = set(), []
    for f in feeds:
        for s in f["stories"]:
            if s["link"] not in seen:             # BBC lists a story in world and business: keep one
                seen.add(s["link"])
                stories.append(s)
    return {"feeds": feeds, "groups": group(stories)}


# ---------------------------------------------------------------------
# Interests: ~/vault/me/interests.md, my words
# ---------------------------------------------------------------------
KEYS = {"follow closely": "close", "sometimes": "some", "never show me": "never", "surprise me with": "surprise"}


def read_interests(path=None):
    """→ {"close": [terms], "some": [terms], "never": [terms], "surprise": int, "found": bool}"""
    path = Path(path or INTERESTS)
    out = {"close": [], "some": [], "never": [], "surprise": SURPRISE_DEFAULT, "found": path.is_file()}
    if not out["found"]:
        return out
    for line in path.read_text().splitlines():
        line = line.strip().lstrip("-* ").strip()
        if "⟪" in line or ":" not in line:        # unfilled template lines are skipped
            continue
        key, _, rest = line.partition(":")
        kind = KEYS.get(key.strip().lower())
        if not kind or not rest.strip():
            continue
        if kind == "surprise":
            m = re.search(r"(\d+)\s*(?:stor\w*\s*)?in\s*(\d+)", rest)
            n = re.search(r"\d+", rest)
            if m and int(m.group(2)):
                out["surprise"] = max(1, round(BRIEF_SIZE * int(m.group(1)) / int(m.group(2))))
            elif n:
                out["surprise"] = min(int(n.group()), BRIEF_SIZE)
            continue
        out[kind] += [t.strip() for t in rest.split(",") if t.strip()]
    return out


def matches(terms, text):
    """Whole words, any case, plurals too: "chip" finds "chips", "AI" never finds "said"."""
    return [t for t in terms if re.search(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?:s|es)?(?![A-Za-z0-9])", text, re.I)]


def rank(groups, interests, size=BRIEF_SIZE):
    """My interests first (follow closely counts double), more outlets higher, 'never' gone,
    and a few big stories from outside my interests so the brief doesn't become an echo."""
    picked, outside = [], []
    for g in groups:
        text = " ".join(f"{s['title']} {s['summary']}" for s in g["members"])
        if matches(interests["never"], text):
            continue
        close, some = matches(interests["close"], text), matches(interests["some"], text)
        g = {**g, "matched": close + some, "score": 2 * len(close) + len(some)}
        (picked if g["score"] else outside).append(g)
    key = lambda g: (g["score"], len(g["outlets"]), g["lead"]["time"])
    picked.sort(key=key, reverse=True)
    outside = [g for g in outside if len(g["outlets"]) >= 2]      # a surprise must be a big story
    outside.sort(key=lambda g: (len(g["outlets"]), g["lead"]["time"]), reverse=True)
    n_out = min(interests["surprise"], len(outside), size)
    chosen = picked[:size - n_out] + [{**g, "surprise": True} for g in outside[:n_out]]
    for i, g in enumerate(chosen, 1):
        g["id"] = f"s{i}"
    return chosen


# ---------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------
def cmd_feeds(args):
    """Counts only: is each feed alive? Run it on the Studio; the cloud can't reach news sites."""
    names = args.names or list(FEEDS)
    for n in names:
        if n not in FEEDS:
            sys.exit(f"Not run: no feed called {n!r}. Known: {', '.join(FEEDS)}")
    now = now_utc()
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        rows = list(pool.map(lambda n: read_feed(n, now), names))
    print(f"{'Feed':<14}{'Used':<6}{'Status':<22}{'Items':>6}{'Fresh':>7}{'Newest':>10}")
    bad = 0
    for r in rows:
        f = FEEDS[r["feed"]]
        status = (f"failed ({r['error']})" if not r["ok"] else "stale" if r["stale"] else "ok")
        bad += status != "ok" and f["use"]
        age = f"{r['newest_hours']:.0f} h" if r["newest_hours"] is not None else "-"
        print(f"{r['feed']:<14}{'yes' if f['use'] else 'no':<6}{status:<22}{r['seen']:>6}"
              f"{len(r['stories']):>7}{age:>10}" + ("  paywall" if f.get("paywall") else ""))
    print(f"\nFresh = stories from the last {FRESH_HOURS} h with a title, a time and a link on the "
          f"outlet's own site.\nStale = newest story older than {STALE_DAYS} days.")
    if bad:
        print(f"{bad} feed(s) in use need a look.")
    return 1 if bad else 0


def cmd_preview(args):
    """The stories a brief would start from. My terminal only: never the ledger."""
    got = gather()
    interests = read_interests()
    if not interests["found"]:
        print(f"NOTE  no interests file at {INTERESTS}: every story counts as outside my interests.")
    chosen = rank(got["groups"], interests)
    for g in chosen:
        lead = g["lead"]
        tag = "surprise" if g.get("surprise") else ", ".join(g["matched"])
        print(f"[{g['id']}] {lead['title']}")
        print(f"      {' · '.join(g['outlets'])}{'  (thin: one outlet)' if g['thin'] else ''}  [{tag}]")
        for s in g["members"]:
            print(f"      {s['outlet']}: {s['link']}")
    ok = sum(f["ok"] and not f["stale"] for f in got["feeds"])
    print(f"\n{ok}/{len(got['feeds'])} feeds · {sum(len(g['members']) for g in got['groups'])} fresh stories "
          f"· {len(got['groups'])} events · {len(chosen)} chosen")
    if args.json:
        print(json.dumps(chosen, indent=1))


def main():
    p = argparse.ArgumentParser(description="The news agent's feeds")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("feeds", help="check every feed (counts only)")
    f.add_argument("names", nargs="*", help="only these feeds")
    f.set_defaults(f=cmd_feeds)
    pr = sub.add_parser("preview", help="the ranked stories, no model")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(f=cmd_preview)
    a = p.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
