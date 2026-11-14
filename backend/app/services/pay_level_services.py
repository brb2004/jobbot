import re

JUNIOR = re.compile(
    r"(?<!\w)(?:junior|jr\.?|new grad|university grad|graduate|entry[- ]level|early career|associate|intern"
    r"|apprentice|residency)(?!\w)|(?<!\w)(?:engineer|developer)\s+(?:i|1)(?!\w)",
    re.I,
)
FLOORS = ((180_000, 5), (150_000, 3))


def years_from_pay(title: str | None, salary_min: float | None, currency: str | None) -> int | None:
    if salary_min is None or (currency or "").upper() != "USD" or JUNIOR.search(title or ""):
        return None
    if not 40_000 <= salary_min <= 1_000_000:
        return None
    return next((years for floor, years in FLOORS if salary_min >= floor), None)
