"""Stand-ins for hostile files, run inside the extraction child process (must be importable top-level)."""
import time


def hang(data: bytes) -> str:
    time.sleep(60)
    return "never"


def balloon(data: bytes) -> str:
    return "x" * (2 * 1024 ** 3)              # 2 GB: over the child's memory limit


def nap(data: bytes) -> str:
    time.sleep(0.6)
    return "ok"
