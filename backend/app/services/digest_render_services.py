from app.schemas.matches_schemas import MatchOut
from app.services.requirements_services import years_note
from app.services.scoring_services import tier

SHOW = 3
WIDTH = 80
STILL_OPEN = 5


def _short(items: list[str]) -> str:
    trimmed = [i if len(i) <= WIDTH else i[: WIDTH - 1].rstrip() + "…" for i in items[:SHOW]]
    more = f" (+{len(items) - SHOW} more)" if len(items) > SHOW else ""
    return "; ".join(trimmed) + more


def _head(i: int, m: MatchOut) -> str:
    d = m.detail or {}
    head = f"{i}. {m.title} — {tier(m.score)}"
    if d.get("over_years") and (note := years_note(d)):
        head += f" · {note}"
    if d.get("clearance"):
        head += " · may require clearance or U.S. citizenship"
    total = sum(len(d.get(k) or []) for k in ("met", "partial", "missing"))
    if total:
        head += f" · {len(d.get('met') or [])} of {total} skills"
    return head


def _block(i: int, m: MatchOut) -> str:
    d = m.detail or {}
    lines = [_head(i, m)]
    for key, label in (("met", "You have:"), ("partial", "Partly:  "), ("missing", "Missing: ")):
        if d.get(key):
            lines.append(f"   {label} {_short(d[key])}")
    if m.url:
        lines.append(f"   {m.url}")
    return "\n".join(lines)


def _best_per_job(matches: list[MatchOut]) -> list[MatchOut]:
    best: dict = {}
    for m in matches:
        if m.job_id not in best or m.score > best[m.job_id].score:
            best[m.job_id] = m
    return sorted(best.values(), key=lambda m: m.score, reverse=True)


def groups(matches: list[MatchOut], top_n: int) -> list[tuple[str | None, list[MatchOut]]]:
    ranked = _best_per_job(matches)
    names = list(dict.fromkeys(m.resume for m in ranked))
    per = top_n if len(names) < 2 else max(1, top_n // len(names))
    return [(name, [m for m in ranked if m.resume == name][:per]) for name in names]


def _sections(matches: list[MatchOut], top_n: int) -> str:
    parts = groups(matches, top_n)
    blocks = ["\n\n".join(_block(i, m) for i, m in enumerate(ms, 1)) for _, ms in parts]
    if len(parts) < 2:
        return blocks[0]
    return "\n\n".join(f"== {name or 'Resume'} ==\n\n{b}" for (name, _), b in zip(parts, blocks, strict=True))


def render(matches: list[MatchOut], top_n: int, still_open: list[MatchOut] = ()) -> str:
    if not matches:
        return "No new matches this week."
    text = "New this week:\n\n" + _sections(matches, top_n)
    if still_open:
        older = "\n".join(f"- {m.title} — {m.url or ''}".rstrip(" —") for m in still_open[:STILL_OPEN])
        text += "\n\nStill open from earlier:\n" + older
    return text
