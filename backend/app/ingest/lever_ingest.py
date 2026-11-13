import html as htmllib
import logging

import httpx

from app.ingest.crawl_ingest import (
    Listing,
    Posting,
    Source,
    _get,
    fingerprint,
    name_from_slug,
    remote_location,
)
from app.ingest.text_ingest import html_to_text

API = "https://api.lever.co/v0/postings"
PAGE = 100
MAX_PAGES = 100
log = logging.getLogger(__name__)


def page_html(job: dict) -> str:
    parts = [job.get("description") or ""]
    for lst in job.get("lists") or []:
        if isinstance(lst, dict) and (lst.get("content") or "").strip():
            parts.append(f"<h3>{htmllib.escape(lst.get('text') or '')}</h3><ul>{lst['content']}</ul>")
    parts.append(job.get("additional") or "")
    return "\n".join(p for p in parts if p)


def salary(job: dict) -> tuple[float | None, float | None, str | None]:
    r = job.get("salaryRange")
    if isinstance(r, dict) and r.get("interval") == "per-year-salary":
        return r.get("min"), r.get("max"), r.get("currency")
    return None, None, None


def posting(job: dict) -> Posting:
    html = page_html(job)
    cats = job.get("categories") or {}
    places = cats.get("allLocations") or [cats.get("location") or ""]
    lo, hi, cur = salary(job)
    return Posting(
        external_id=str(job["id"]),
        title=job["text"],
        url=job.get("hostedUrl") or job.get("applyUrl") or "",
        location=remote_location(
            [p for p in places if isinstance(p, str)], job.get("workplaceType") == "remote"
        ),
        version=fingerprint(html, str(lo), str(hi)),
        content_html=html,
        description=html_to_text(html) if html else "",
        salary_min=lo,
        salary_max=hi,
        salary_currency=cur,
    )


async def fetch_board(client: httpx.AsyncClient, slug: str) -> Listing | None:
    postings, ids, seen = [], [], set()
    for n in range(MAX_PAGES):
        r = await _get(client, f"{API}/{slug}", params={"mode": "json", "skip": n * PAGE, "limit": PAGE})
        if r.status_code == 404 and n == 0:
            return None
        r.raise_for_status()
        page = r.json()
        if not isinstance(page, list):
            raise ValueError(f"lever {slug}: expected a list, got {type(page).__name__}")
        fresh = [j for j in page if isinstance(j, dict) and j.get("id") and str(j["id"]) not in seen]
        for j in fresh:
            seen.add(str(j["id"]))
            ids.append(str(j["id"]))
            try:
                postings.append(posting(j))
            except Exception as e:
                log.warning("lever site %s: skipped a malformed posting: %s", slug, repr(e)[:200])
        if len(page) < PAGE or not fresh:
            return postings, ids
    raise RuntimeError(f"lever {slug}: more than {MAX_PAGES} pages")


async def fetch_name(client: httpx.AsyncClient, slug: str) -> str | None:
    return name_from_slug(slug)


LEVER = Source(name="lever", prefix="lever:", fetch_board=fetch_board, fetch_name=fetch_name)
