"""Ashby adapter: one public, unauthenticated call returns a board's whole published set, descriptions included.

  GET https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true

The API names no company, so the display name comes from the slug.
"""
import logging

import httpx

from app.ingest.crawl_ingest import Listing, Posting, Source, _get, fingerprint, name_from_slug, remote_location
from app.ingest.text_ingest import html_to_text

API = "https://api.ashbyhq.com/posting-api/job-board"
log = logging.getLogger(__name__)


def salary(job: dict) -> tuple[float | None, float | None, str | None]:
    """Yearly salary band from compensation.summaryComponents; anything else (hourly, equity) is skipped."""
    for c in ((job.get("compensation") or {}).get("summaryComponents") or []):
        if isinstance(c, dict) and c.get("compensationType") == "Salary" and c.get("interval") == "1 YEAR":
            return c.get("minValue"), c.get("maxValue"), c.get("currencyCode")
    return None, None, None


def posting(job: dict) -> Posting:
    html = job.get("descriptionHtml") or ""
    places = [job.get("location") or ""] + [(s or {}).get("location") or "" for s in job.get("secondaryLocations") or []]
    remote = bool(job.get("isRemote")) or (job.get("workplaceType") or "").lower() == "remote"
    lo, hi, cur = salary(job)
    return Posting(
        external_id=str(job["id"]),
        title=job["title"],
        url=job.get("jobUrl") or job.get("applyUrl") or "",
        location=remote_location(places, remote),
        version=fingerprint(html, str(lo), str(hi)),
        content_html=html,
        description=html_to_text(html) if html else (job.get("descriptionPlain") or ""),
        salary_min=lo, salary_max=hi, salary_currency=cur,
    )


async def fetch_board(client: httpx.AsyncClient, slug: str) -> Listing | None:
    """(postings that parsed, ids of everything listed) or None for 404. Unlisted postings (isListed false)
    don't count as listed, so they close."""
    r = await _get(client, f"{API}/{slug}", params={"includeCompensation": "true"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    raw = r.json()["jobs"]                                  # not JSON / no "jobs": the whole board fails
    postings, ids = [], []
    for j in raw:
        if not isinstance(j, dict) or j.get("isListed") is False:
            continue
        if j.get("id"):
            ids.append(str(j["id"]))
        try:
            postings.append(posting(j))
        except Exception as e:                              # skipped, not closed: its id still counts
            log.warning("ashby board %s: skipped a malformed job: %s", slug, repr(e)[:200])
    return postings, ids


async def fetch_name(client: httpx.AsyncClient, slug: str) -> str | None:
    return name_from_slug(slug)


ASHBY = Source(name="ashby", prefix="ashby:", fetch_board=fetch_board, fetch_name=fetch_name)
