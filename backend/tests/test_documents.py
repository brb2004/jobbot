"""Resume parsing can't freeze or crash the API: child process, time limit, memory limit, page cap."""
import asyncio
import io
import time

import pytest
from pypdf import PdfWriter

from app.services import documents_services as docs
from tests import slow_parsers

pytestmark = pytest.mark.asyncio


def pdf(pages: int) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


async def test_plain_text_and_docx_rules_still_work():
    assert await docs.extract_text_safely(b"Python developer") == "Python developer"
    with pytest.raises(docs.UnsupportedType):
        await docs.extract_text_safely(b"\x00\x01binary")


async def test_long_pdfs_are_refused():
    with pytest.raises(docs.Unreadable, match="20 pages"):
        await docs.extract_text_safely(pdf(20))
    assert await docs.extract_text_safely(pdf(2)) == "\n"          # blank pages: empty text, not an error


async def test_a_hanging_parse_is_killed_and_the_loop_keeps_running():
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.05)
            ticks += 1

    t = asyncio.create_task(ticker())
    start = time.monotonic()
    with pytest.raises(docs.Unreadable, match="too long"):
        await docs.extract_text_safely(b"anything", timeout=1, target=slow_parsers.hang)
    elapsed = time.monotonic() - start
    t.cancel()
    assert elapsed < 3                                             # killed at ~1 s, not 60
    assert ticks >= 10                                             # other work kept running meanwhile


async def test_a_memory_bomb_dies_alone():
    with pytest.raises(docs.Unreadable):
        await docs.extract_text_safely(b"anything", target=slow_parsers.balloon)


async def test_a_long_pdf_upload_is_a_clean_422(client, auth_headers):
    r = await client.post("/resumes", headers=auth_headers, files={"file": ("cv.pdf", pdf(20), "application/pdf")})
    assert r.status_code == 422 and "20 pages" in r.text
