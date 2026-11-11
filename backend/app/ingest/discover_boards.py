"""Find job boards we don't crawl yet, from Common Crawl's public URL index, then check each one live on
its source's public API. Report first; --add appends the good ones to boards.txt.

  python -m app.ingest.discover_boards                       # Greenhouse, report only
  python -m app.ingest.discover_boards --source ashby --check 500
  python -m app.ingest.discover_boards --source lever --add  # also append boards with engineering jobs
"""
import argparse
import gzip
import csv
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.db.models_db import Job
from app.ingest import ashby_ingest, lever_ingest
from app.ingest.boards_ingest import load_slugs
from app.services.places_services import places_in
from app.services.preferences_services import Preferences, allowed

UA = {"User-Agent": "JobMatch board discovery (https://jobmatch.bbenard.dev)"}
NOT_SLUGS = {"embed", "jobs", "v1", "api", "static", "assets", "favicon.ico", "robots.txt"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")
US_STATE = re.compile(r",\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b")      # "Columbia, MO"
BOARDS = Path(__file__).resolve().parents[2] / "boards.txt"
REPORT = Path("/tmp/discovered_boards.csv")


def get(url: str, tries: int = 6) -> str:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == tries - 1:
                raise                                       # 4xx is an answer (e.g. past the last page)
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(3 * 2 ** i)                              # busy server: 3, 6, 12, 24, 48 s


def slug_of(url: str, keep_case: bool = False) -> str | None:
    u = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    first = u.path.strip("/").split("/")[0]
    if first.lower() == "embed":                           # boards.greenhouse.io/embed/job_board?for=<slug>
        first = (urllib.parse.parse_qs(u.query).get("for") or [""])[0]
    first = urllib.parse.unquote(first) if keep_case else urllib.parse.unquote(first).lower()
    return first if first.lower() not in NOT_SLUGS and SLUG.match(first.lower()) else None


DATA = "https://data.commoncrawl.org/"
# SURT keys (reversed host, sorted) per source, and how a board key is written in boards.txt.
SURTS = {
    "greenhouse": ("io,greenhouse,boards)/", "io,greenhouse,job-boards)/"),
    "ashby": ("com,ashbyhq,jobs)/",),
    "lever": ("co,lever,jobs)/",),
}
KEY_PREFIX = {"greenhouse": "", "ashby": "ashby:", "lever": "lever:"}
FALLBACK_CRAWL = "CC-MAIN-2026-43"


def chunk(url: str, start: int, end: int) -> bytes:
    """Bytes start..end of a remote file (HTTP Range), with retries."""
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if i == 4:
                raise
            time.sleep(3 * 2 ** i)


def size_of(url: str) -> int:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA, method="HEAD"), timeout=60) as r:
        return int(r.headers["Content-Length"])


def key_at(url: str, pos: int, size: int) -> str:
    """The first whole index line at or after byte pos -> its sort key."""
    data = chunk(url, pos, min(pos + 8191, size - 1))
    if pos:
        data = data[data.index(b"\n") + 1:]                               # skip the partial line we landed in
    return data.split(b"\n", 1)[0].decode().split(" ", 1)[0]


def blocks_for(idx_url: str, prefix: str) -> list[list[str]]:
    """Binary search the sorted cluster.idx over HTTP Range requests for the first key >= prefix,
    then read forward and return every block that can hold keys with this prefix."""
    size = size_of(idx_url)
    lo, hi = 0, size
    while hi - lo > 65536:                                                  # ~20 small reads for a few hundred MB
        mid = (lo + hi) // 2
        if key_at(idx_url, mid, size) < prefix:
            lo = mid
        else:
            hi = mid
    blocks, prev, buf, pos, first = [], None, b"", lo, True
    while pos < size:
        data = chunk(idx_url, pos, min(pos + (1 << 20) - 1, size - 1))
        pos += len(data)
        buf += data
        if first and lo:
            buf = buf[buf.index(b"\n") + 1:]
        first = False
        lines = buf.split(b"\n")
        buf = lines.pop()
        for raw in lines:
            parts = raw.decode().split("\t")                               # "SURT TIMESTAMP", file, offset, length, id
            if len(parts) < 4:
                continue
            key = parts[0].split(" ", 1)[0]
            if key < prefix:
                prev = parts                                                # the block just before may hold matches
                continue
            if not key.startswith(prefix):
                return blocks
            if prev is not None:
                blocks.append(prev)
                prev = None
            blocks.append(parts)
    return blocks


def urls_in(crawl: str, block: list[str], prefix: str) -> list[str]:
    """One compressed block of ~3,000 index lines ("surt timestamp {json}") -> the URLs under prefix."""
    off, length = int(block[2]), int(block[3])
    raw = chunk(f"{DATA}cc-index/collections/{crawl}/indexes/{block[1]}", off, off + length - 1)
    out = []
    for line in gzip.decompress(raw).decode(errors="replace").splitlines():
        if line.startswith(prefix):
            try:
                out.append(json.loads(line.split(" ", 2)[2])["url"])
            except Exception:
                continue
    return out


def from_common_crawl(indexes: int, max_blocks: int, crawl: str | None, source: str = "greenhouse") -> set[str]:
    """Companies with a board on this source, from Common Crawl's index FILES (data.commoncrawl.org), which
    stay up when the index search server is overloaded."""
    if crawl:
        crawls = [crawl]
    else:
        try:
            crawls = [c["id"] for c in json.loads(get("https://index.commoncrawl.org/collinfo.json", tries=2))][:indexes]
        except Exception:
            crawls = [FALLBACK_CRAWL]
            print(f"  crawl list unavailable; using {FALLBACK_CRAWL}", file=sys.stderr)
    found: set[str] = set()
    for c in crawls:
        idx = f"{DATA}cc-index/collections/{c}/indexes/cluster.idx"
        for prefix in SURTS[source]:
            blocks = blocks_for(idx, prefix)
            if max_blocks:
                blocks = blocks[:max_blocks]
            print(f"  {c} {prefix}: {len(blocks)} blocks", file=sys.stderr)
            with ThreadPoolExecutor(max_workers=6) as pool:                 # a few at a time: polite, still fast
                for n, urls in enumerate(pool.map(lambda b: urls_in(c, b, prefix), blocks), 1):
                    keep = source != "greenhouse"                 # Ashby/Lever slugs keep their case
                    found.update(filter(None, (slug_of(u, keep) for u in urls)))
                    if n % 20 == 0 or n == len(blocks):
                        print(f"    {n}/{len(blocks)} blocks, {len(found)} companies so far", file=sys.stderr)
    return found


def listing(source: str, slug: str) -> list[tuple[str, str]]:
    """(title, location) of each open job, locations normalized the way the crawler stores them."""
    q = urllib.parse.quote(slug)
    if source == "ashby":
        data = json.loads(get(f"{ashby_ingest.API}/{q}", tries=2))
        jobs = [ashby_ingest.posting(j) for j in data["jobs"] if j.get("isListed") is not False]
        return [(p.title, p.location or "") for p in jobs]
    if source == "lever":
        data = json.loads(get(f"{lever_ingest.API}/{q}?mode=json", tries=2))
        return [(p.title, p.location or "") for p in map(lever_ingest.posting, data)]
    jobs = json.loads(get(f"https://boards-api.greenhouse.io/v1/boards/{q}/jobs", tries=2)).get("jobs", [])
    return [(j.get("title") or "", (j.get("location") or {}).get("name") or "") for j in jobs]


def check(slug: str, source: str = "greenhouse") -> tuple[int, int, int]:
    """(open jobs, jobs our matcher would show, of those: US or remote)."""
    jobs = listing(source, slug)
    eng = [(t, loc) for t, loc in jobs if allowed(Job(title=t), Preferences())]   # same rules as matching
    us = [1 for _, loc in eng
          if loc and ("United States" in places_in(loc) or US_STATE.search(loc) or re.search(r"remote", loc, re.I))]
    return len(jobs), len(eng), len(us)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=sorted(SURTS), default="greenhouse")
    ap.add_argument("--indexes", type=int, default=1, help="how many monthly crawls to read (newest first)")
    ap.add_argument("--max-blocks", type=int, default=0, help="limit index blocks per host (0 = all)")
    ap.add_argument("--crawl", default=None, help="a specific crawl id, e.g. CC-MAIN-2026-43")
    ap.add_argument("--check", type=int, default=200, help="how many new companies to verify live")
    ap.add_argument("--min-eng", type=int, default=1, help="engineering openings needed to count")
    ap.add_argument("--min-us", type=int, default=1, help="of those, how many must be US or remote")
    ap.add_argument("--add", action="store_true", help="append qualifying boards to boards.txt")
    a = ap.parse_args()

    pre = KEY_PREFIX[a.source]
    known = {k.lower() for k in load_slugs(BOARDS.read_text())}
    found: dict[str, str] = {}
    for slug in from_common_crawl(a.indexes, a.max_blocks, a.crawl, a.source):
        found.setdefault(slug.lower(), slug)                # one spelling per board
    fresh = sorted(s for low, s in found.items() if (pre + low) not in known)
    random.Random(0).shuffle(fresh)                         # a fair sample, not just the A's; same order every run
    print(f"{len(fresh)} companies we don't crawl yet; checking {len(fresh[: a.check or None])}", file=sys.stderr)

    rows = []
    for slug in fresh[: a.check or None]:                  # --check 0 = all
        try:
            total, eng, us = check(slug, a.source)
            rows.append((slug, "ok" if eng >= a.min_eng and us >= a.min_us
                         else ("no-us-jobs" if eng >= a.min_eng else "no-eng-jobs"), total, eng, us))
        except Exception:
            rows.append((slug, "dead", 0, 0, 0))
        time.sleep(0.15)                                    # one request at a time
    rows.sort(key=lambda r: (-r[4], -r[3], r[0]))

    with REPORT.open("w", newline="") as f:
        csv.writer(f).writerows([("slug", "status", "open_jobs", "eng_jobs", "eng_us_or_remote"), *rows])
    good = [r for r in rows if r[1] == "ok"]
    print(f"\nchecked {len(rows)}: {len(good)} with engineering openings, "
          f"{sum(r[1] == 'dead' for r in rows)} dead. Full report: {REPORT}")
    for r in good[:25]:
        print(f"  {r[0]:<32} {r[3]:>4} eng jobs ({r[4]} US/remote) of {r[2]}")
    if a.add and good:
        BOARDS.write_text(BOARDS.read_text().rstrip("\n") + "\n" + "\n".join(pre + r[0] for r in good) + "\n")
        print(f"added {len(good)} boards to {BOARDS.name}")


if __name__ == "__main__":
    main()
