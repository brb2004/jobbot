import asyncio
import io
import multiprocessing
import resource
import threading
import zipfile

MAX_PAGES = 15  # a resume is 1-3 pages; anything far past that isn't one
MAX_UNZIPPED = 10 * 1024 * 1024  # a .docx is a zip: cap what it expands to (zip bombs)
MAX_ZIP_ENTRIES = 1000
TIMEOUT_S = 10
PARSE_SLOTS = 2  # children at once: each may use up to 512 MB, the API pod has 1 GiB
QUEUE_WAIT_S = 30  # an upload waits this long for a slot, then is told to retry
_slots = threading.BoundedSemaphore(PARSE_SLOTS)
MEMORY_LIMIT = 512 * 1024 * 1024  # address space for the child: a decompression bomb dies alone


class TooLarge(Exception):
    pass


class UnsupportedType(Exception):
    pass


class Unreadable(Exception):
    pass


def sniff(data: bytes) -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    if b"\x00" in data:
        raise UnsupportedType  # binary pretending to be text
    return "txt"


def _check_zip(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries = z.infolist()
    except zipfile.BadZipFile:
        raise Unreadable("Couldn't read this .docx. Try saving it again, or upload a PDF.") from None
    if len(entries) > MAX_ZIP_ENTRIES or sum(e.file_size for e in entries) > MAX_UNZIPPED:
        raise Unreadable("This .docx is too large once unpacked.")


def extract_text(data: bytes) -> str:
    kind = sniff(data)
    try:
        if kind == "pdf":
            from pypdf import PdfReader

            pages = PdfReader(io.BytesIO(data)).pages
            if len(pages) > MAX_PAGES:
                raise Unreadable(
                    f"This PDF has {len(pages)} pages. Upload a resume of {MAX_PAGES} pages or fewer."
                )
            return "\n".join(p.extract_text() or "" for p in pages)
        if kind == "docx":
            _check_zip(data)
            from docx import Document

            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    except Unreadable:
        raise
    except Exception:
        # never a 500, and never echo parser internals (which can contain resume text)
        raise Unreadable("Couldn't read this file. Try saving it again as a PDF or .docx.") from None
    return data.decode("utf-8", errors="ignore")


def _child(conn, data: bytes, target) -> None:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
        conn.send(("ok", target(data)))
    except UnsupportedType:
        conn.send(("unsupported", ""))
    except Unreadable as e:
        conn.send(("unreadable", str(e)))
    except BaseException:  # MemoryError included: no details, see extract_text
        conn.send(("unreadable", "Couldn't read this file. Try saving it again as a PDF or .docx."))
    finally:
        conn.close()


_ctx = multiprocessing.get_context("forkserver")
_ctx.set_forkserver_preload(["app.services.documents_services", "pypdf", "docx"])


def _run(data: bytes, timeout: float, target) -> tuple[str, str] | None:
    if not _slots.acquire(timeout=QUEUE_WAIT_S):
        return ("busy", "Lots of uploads right now. Try again in a minute.")
    try:
        return _run_child(data, timeout, target)
    finally:
        _slots.release()


def _run_child(data: bytes, timeout: float, target) -> tuple[str, str] | None:
    parent, child = _ctx.Pipe(duplex=False)
    p = _ctx.Process(target=_child, args=(child, data, target), daemon=True)
    p.start()
    child.close()
    try:
        return parent.recv() if parent.poll(timeout) else None
    except EOFError:  # killed by the memory limit before it could answer
        return ("unreadable", "Couldn't read this file. Try saving it again as a PDF or .docx.")
    finally:
        parent.close()
        p.join(0.5)
        if p.is_alive():
            p.kill()  # over time: it never gets to finish
            p.join()


async def extract_text_safely(data: bytes, timeout: float | None = None, target=extract_text) -> str:
    result = await asyncio.to_thread(_run, data, TIMEOUT_S if timeout is None else timeout, target)
    if result is None:
        raise Unreadable("This file took too long to read. Try saving it again as a simple PDF or .docx.")
    status, value = result
    if status == "unsupported":
        raise UnsupportedType
    if status in ("unreadable", "busy"):
        raise Unreadable(value)
    return value
