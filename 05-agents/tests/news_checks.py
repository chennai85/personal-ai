"""news_checks.py: the news feeds and shaping, checked on stand-in feeds. Run by test_agent.sh.

Needs NEWS_FAKE (the stand-in feeds folder), NEWS_NOW (a pinned "now") and VAULT_DIR (a throwaway vault).
Prints PASS/FAIL lines; exits 1 if anything failed.
"""
import contextlib
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import news  # noqa: E402

PASS = FAIL = 0


def check(name, ok):
    global PASS, FAIL
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    PASS, FAIL = PASS + bool(ok), FAIL + (not ok)


def no_secret(obj):
    return "SECRET-" not in json.dumps(obj, ensure_ascii=False)


now = news.now_utc()

# --- one feed, shaped -------------------------------------------------
bbc = news.read_feed("bbc", now)
titles = [s["title"] for s in bbc["stories"]]
links = [s["link"] for s in bbc["stories"]]
check("bbc: feed read", bbc["ok"] and not bbc["stale"])
check("bbc: fresh stories kept", "Nvidia shares climb on AI chip demand" in titles)
check("bbc: query and fragment dropped from links", "https://www.bbc.com/news/articles/c1ceasefire" in links
      and not any("?" in l or "#" in l for l in links))
check("bbc: story older than FRESH_HOURS dropped", "Story from three days ago" not in titles)
check("bbc: link on another domain dropped", "Link goes somewhere else" not in titles)
check("bbc: story with no date dropped", "No date on this one" not in titles)
check("bbc: link with a login part dropped", "Login link" not in titles)
check("bbc: story from the future dropped", "From the future" not in titles)
check("bbc: javascript: link dropped", "Script link" not in titles)
zw = [t for t in titles if t.startswith("Hidden")]
check("bbc: zero-width and right-to-left characters removed",
      zw and "​" not in zw[0] and "‮" not in zw[0] and "Hidden text here" in zw[0])
check("bbc: counts add up", bbc["seen"] == len(bbc["stories"]) + bbc["dropped"])

npr = news.read_feed("npr", now)
check("npr: full article text (content:encoded) never read", npr["ok"] and no_secret(npr))
check("npr: summary kept", any(s["summary"] == "India's central bank steps in." for s in npr["stories"]))
check("npr: time with a zone becomes UTC", any(s["time"] == "2026-11-08T11:00+00:00" for s in npr["stories"]))

g = news.read_feed("guardian", now)
gs = {s["title"][:6]: s for s in g["stories"]}
cairo = gs.get("Cairo ", {}).get("summary", "")
check("guardian: HTML stripped from the summary", cairo.startswith("Envoys gathered on Sunday.") and "<" not in cairo)
check("guardian: script and style blocks removed with their contents", no_secret(g) and "color:red" not in cairo)
check("guardian: twice-escaped HTML still stripped", gs.get("Double", {}).get("title") == "Double escaped title")
check("guardian: long summary capped", len(gs.get("Double", {}).get("summary", "")) <= news.SUMMARY_MAX
      and gs.get("Double", {}).get("summary", "").endswith("…"))

dw = news.read_feed("dw", now)
check("dw: RDF (RSS 1.0) read, ISO date", dw["ok"] and "Germany weighs new chip subsidies" in [s["title"] for s in dw["stories"]])

f24 = news.read_feed("france24", now)
check("france24: Atom read, alternate link chosen", f24["ok"] and f24["stories"]
      and f24["stories"][0]["link"] == "https://www.france24.com/en/sport/golf-dubai")
check("france24: Atom <content> never read", no_secret(f24))

# --- feeds that are broken, stale or hostile ----------------------------
cnn = news.read_feed("cnn", now)
check("cnn: stale feed flagged, no stories", cnn["ok"] and cnn["stale"] and not cnn["stories"])
bomb = news.read_feed("npr-biz", now)
check("DOCTYPE/ENTITY feed refused unread", bomb["error"] == "FeedRefused" and no_secret(bomb))
broken = news.read_feed("npr-tech", now)
check("broken XML: error type only", broken["error"] == "FeedNotUnderstood" and not broken["stories"])
page = news.read_feed("bbc-tech", now)
check("an HTML page is not a feed", page["error"] == "FeedNotUnderstood" and no_secret(page))
missing = news.read_feed("gdn-tech", now)
check("missing feed: error, no crash", missing["error"] == "LookupError")
big = Path(os.environ["NEWS_FAKE"]) / "guardian-biz.xml"
big.write_bytes(b"<rss>" + b" " * (news.MAX_BYTES + 10) + b"</rss>")
too_big = news.read_feed("guardian-biz", now)
big.unlink()
check("feed over MAX_BYTES refused", too_big["error"] == "FeedTooBig")
try:
    news.fetch("evil")
    ok = False
except KeyError:
    ok = True
check("a feed name not in FEEDS is never fetched", ok)
check("Al Jazeera removed from the feed list", "aljazeera" not in news.FEEDS
      and not any("aljazeera" in f["url"] for f in news.FEEDS.values()))

ie = news.read_feed("indianexp", now)
check("indianexp: headline-only feed kept, empty summary, full text never read",
      ie["ok"] and len(ie["stories"]) == 1 and ie["stories"][0]["summary"] == "" and no_secret(ie))
import re as _re
TOKEN = _re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,11}$")      # 06-monitor/monitor.py
check("every feed name is a token the monitor can show", all(TOKEN.match(n) for n in news.FEEDS))
check("every feed in use is https", all(f["url"].startswith("https://") for f in news.FEEDS.values() if f["use"]))

# --- links: the rule on its own ------------------------------------------
cl = news.clean_link
check("link: http on the right domain becomes https", cl("http://www.cnn.com/a", ("cnn.com",)) == "https://www.cnn.com/a")
check("link: look-alike domain refused", cl("https://notbbc.com/a", ("bbc.com",)) is None)
check("link: only http/https", cl("gopher://www.bbc.com/a", ("bbc.com",)) is None and cl("ftp://www.bbc.com/a", ("bbc.com",)) is None)
check("link: odd port refused", cl("https://www.bbc.com:8443/a", ("bbc.com",)) is None)
check("link: odd characters removed from the path", cl('https://www.bbc.com/a"><b>', ("bbc.com",)) == "https://www.bbc.com/ab")

# --- gather: repeats dropped, events grouped, thin labelled ------------
got = news.gather(["bbc", "bbc-india", "npr", "guardian", "france24-biz", "dw", "france24", "cnn", "npr-biz"], now)
groups = got["groups"]
all_links = [s["link"] for gr in groups for s in gr["members"]]
check("gather: same link in two BBC feeds kept once", all_links.count("https://www.bbc.com/news/articles/c1ceasefire") == 1)
cg = [gr for gr in groups if any("ceasefire" in s["title"].lower() for s in gr["members"])]
check("gather: one event from four outlets grouped", len(cg) == 1 and cg[0]["outlets"] == ["BBC", "France 24", "NPR", "The Guardian"])
fl = [gr for gr in groups if any("Flood" in s["title"] for s in gr["members"])]
check("gather: same event worded differently grouped", len(fl) == 1 and len(fl[0]["outlets"]) == 2)
dwg = [gr for gr in groups if gr["lead"]["outlet"] == "DW"]
check("gather: one outlet only = thin, even with two of its stories", len(dwg) == 1 and len(dwg[0]["members"]) == 2 and dwg[0]["thin"])
near = ({"title": "Bank of England holds interest rates steady amid inflation worries"},
        {"title": "Football: England beat Brazil as fans complain about ticket rates"})
check("same event: two shared words in long titles is not enough", not news.same_event(*near))
check("gather: different stories not grouped", not any(
    {"Nvidia shares climb on AI chip demand", "Germany weighs new chip subsidies"} <= {s["title"] for s in gr["members"]} for gr in groups))
check("gather: nothing secret anywhere", no_secret(got))

# --- interests and ranking -------------------------------------------------
vault = Path(os.environ["VAULT_DIR"])
(vault / "me").mkdir(parents=True, exist_ok=True)
ip = vault / "me" / "interests.md"
ip.write_text("""---
about: test
---
- Follow closely: AI, Nvidia, rupee
- Sometimes: golf, chip
- Never show me: celebrity
- Surprise me with: 1 story in 12
- Something else: ⟪ unfilled ⟫
""")
it = news.read_interests(ip)
check("interests: read from my file", it["close"] == ["AI", "Nvidia", "rupee"] and it["some"] == ["golf", "chip"]
      and it["never"] == ["celebrity"] and it["surprise"] == 1)
tmpl = news.read_interests(HERE.parent.parent / "03-memory" / "vault-template" / "me" / "interests.md")
check("interests: unfilled template lines skipped", tmpl["found"] and not tmpl["close"] and not tmpl["never"])
check("interests: missing file is not an error", news.read_interests(vault / "nope.md")["found"] is False)
check("match: whole words only ('AI' not in 'said')", news.matches(["AI"], "officials said") == []
      and news.matches(["AI"], "AI chip") == ["AI"])
check("match: plurals count ('chip' finds 'chips')", news.matches(["chip"], "new chips plant") == ["chip"]
      and news.matches(["chip"], "chipmaker") == [])
chosen = news.rank(groups, it, size=5)
ctitles = [c["lead"]["title"] for c in chosen]
check("rank: 'never' stories removed", not any("Celebrity" in t for t in ctitles))
check("rank: follow-closely first", ctitles[0] == "Nvidia shares climb on AI chip demand")
check("rank: ids s1..sN in order", [c["id"] for c in chosen] == [f"s{i}" for i in range(1, len(chosen) + 1)])
sur = [c for c in chosen if c.get("surprise")]
check("rank: surprise slot = a big story outside my interests", len(sur) == 1 and len(sur[0]["outlets"]) >= 2 and not sur[0]["matched"])
check("rank: never more than the brief size", len(news.rank(groups, {**it, "surprise": 99}, size=3)) == 3
      and len(news.rank(groups, {**it, "surprise": 99}, size=1)) == 1)
allsur = [c for c in news.rank(groups, {**it, "surprise": 99}) if c.get("surprise")]
check("rank: every surprise is from 2+ outlets", allsur and all(len(c["outlets"]) >= 2 for c in allsur))
score = {c["lead"]["title"][:5]: c["score"] for c in news.rank(groups, it, size=20)}
check("rank: follow closely counts 2, sometimes 1", score.get("Rupee") == 2 and score.get("Golf:") == 1)

# --- the command line --------------------------------------------------------
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = news.cmd_feeds(type("A", (), {"names": ["bbc", "cnn", "npr-biz"]})())
out = buf.getvalue()
check("feeds: stale and refused shown", "stale" in out and "failed (FeedRefused)" in out)
check("feeds: counts only, no headlines", "Nvidia" not in out and "Ceasefire" not in out and no_secret(out))
check("feeds: exit 1 when a feed in use needs a look", rc == 1)

print(f"\nnews checks: {PASS} pass · {FAIL} fail")
sys.exit(1 if FAIL else 0)
