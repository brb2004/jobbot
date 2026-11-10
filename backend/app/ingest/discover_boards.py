"""Find Greenhouse job boards we don't crawl yet, from Common Crawl's public URL index, then check each one
live on Greenhouse's public Job Board API. Report first; --add appends the good ones to boards.txt.

  python -m app.ingest.discover_boards                       # report only (default: 1 index, 3 pages per host)
  python -m app.ingest.discover_boards --pages 10 --check 500
  python -m app.ingest.discover_boards --add                 # also append boards with engineering jobs
"""
import argparse
import csv
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.db.models_db import Job
from app.services.places_services import places_in
from app.services.preferences_services import Preferences, allowed

UA = {"User-Agent": "JobMatch board discovery (https://jobmatch.bbenard.dev)"}
HOSTS = ("boards.greenhouse.io", "job-boards.greenhouse.io")
NOT_SLUGS = {"embed", "jobs", "v1", "api", "static", "assets", "favicon.ico", "robots.txt"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,60}$")
BOARDS = Path(__file__).resolve().parents[2] / "boards.txt"
REPORT = Path("/tmp/discovered_boards.csv")


def get(url: str, tries: int = 4) -> str:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i * 2)                          # the index is often busy: back off and retry


def slug_of(url: str) -> str | None:
    u = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    first = u.path.strip("/").split("/")[0].lower()
    if first == "embed":                                   # boards.greenhouse.io/embed/job_board?for=<slug>
        first = (urllib.parse.parse_qs(u.query).get("for") or [""])[0].lower()
    return first if first not in NOT_SLUGS and SLUG.match(first) else None


def from_common_crawl(indexes: int, pages: int) -> set[str]:
    found: set[str] = set()
    for info in json.loads(get("https://index.commoncrawl.org/collinfo.json"))[:indexes]:
        for host in HOSTS:
            base = f"{info['cdx-api']}?url={host}/*&output=json&fl=url"
            total = int(json.loads(get(base + "&showNumPages=true"))["pages"])
            for page in range(min(pages, total)):
                for line in get(f"{info['cdx-api']}?url={host}/*&fl=url&page={page}").splitlines():  # plain text
                    if line.strip() and (s := slug_of(line.strip())):                         # skip cut-off lines
                        found.add(s)
                print(f"  {info['id']} {host}: page {page + 1}/{min(pages, total)} (of {total}), "
                      f"{len(found)} companies so far", file=sys.stderr)
                time.sleep(1)                               # be gentle with a free service
    return found


def check(slug: str) -> tuple[int, int, int]:
    """(open jobs, jobs our matcher would show, of those: US or remote)."""
    jobs = json.loads(get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", tries=2)).get("jobs", [])
    eng = [j for j in jobs if allowed(Job(title=j.get("title")), Preferences())]   # same rules as matching
    us = [j for j in eng if (loc := (j.get("location") or {}).get("name") or "")
          and ("United States" in places_in(loc) or re.search(r"remote", loc, re.I))]
    return len(jobs), len(eng), len(us)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indexes", type=int, default=1, help="how many monthly crawls to read (newest first)")
    ap.add_argument("--pages", type=int, default=3, help="index pages per host per crawl")
    ap.add_argument("--check", type=int, default=200, help="how many new companies to verify live")
    ap.add_argument("--min-eng", type=int, default=1, help="engineering openings needed to count")
    ap.add_argument("--add", action="store_true", help="append qualifying boards to boards.txt")
    a = ap.parse_args()

    known = {l.strip() for l in BOARDS.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")}
    fresh = sorted(from_common_crawl(a.indexes, a.pages) - known)
    random.Random(0).shuffle(fresh)                         # a fair sample, not just the A's; same order every run
    print(f"{len(fresh)} companies we don't crawl yet; checking {min(a.check, len(fresh))}", file=sys.stderr)

    rows = []
    for slug in fresh[: a.check]:
        try:
            total, eng, us = check(slug)
            rows.append((slug, "ok" if eng >= a.min_eng else "no-eng-jobs", total, eng, us))
        except Exception:
            rows.append((slug, "dead", 0, 0, 0))
        time.sleep(0.3)                                     # one request at a time
    rows.sort(key=lambda r: (-r[4], -r[3], r[0]))

    with REPORT.open("w", newline="") as f:
        csv.writer(f).writerows([("slug", "status", "open_jobs", "eng_jobs", "eng_us_or_remote"), *rows])
    good = [r for r in rows if r[1] == "ok"]
    print(f"\nchecked {len(rows)}: {len(good)} with engineering openings, "
          f"{sum(r[1] == 'dead' for r in rows)} dead. Full report: {REPORT}")
    for r in good[:25]:
        print(f"  {r[0]:<32} {r[3]:>4} eng jobs ({r[4]} US/remote) of {r[2]}")
    if a.add and good:
        BOARDS.write_text(BOARDS.read_text().rstrip("\n") + "\n" + "\n".join(r[0] for r in good) + "\n")
        print(f"added {len(good)} boards to {BOARDS.name}")


if __name__ == "__main__":
    main()
