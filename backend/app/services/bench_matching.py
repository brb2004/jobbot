"""Benchmark: per-user pool + index (old) vs one shared index (new).
Run: python -m app.services.bench_matching 100,1000,10000"""

import asyncio
import random
import sys
import time
from collections import Counter

from sqlalchemy import select

from app.core.db_core import SessionLocal, engine
from app.db.models_db import Job, User
from app.services.preferences_services import Preferences, allowed
from app.services.requirements_services import years_required
from app.services.scoring_services import build_index, idf_weights, top_matches

OLD_MAX = 1000  # the old way is slow; above this, extrapolate from its per-user time


async def load():
    async with SessionLocal() as s:
        jobs = [j for j in (await s.scalars(select(Job).where(Job.skills.is_not(None)))).all() if j.skills]
        user = (await s.scalars(select(User).where(User.preferences.is_not(None)))).first()
    await engine.dispose()
    return jobs, Preferences.model_validate(user.preferences if user else {})


def fake_users(jobs, n: int, rng: random.Random) -> list[set[str]]:
    df = Counter(s for j in jobs for s in j.skills)  # sample skills as often as jobs ask for them
    skills, freq = zip(*sorted(df.items()), strict=True)
    return [set(rng.choices(skills, weights=freq, k=rng.randint(10, 25))) for _ in range(n)]


def old_way(users, jobs, prefs, weights, years):
    for u in users:
        pool = {j.id: set(j.skills) for j in jobs if allowed(j, prefs)}  # every job, every user
        top_matches(u, pool, weights, 20, job_years=years, user_years=prefs.years_experience)


def new_way(users, jobs, prefs, weights, years):
    all_jobs = {j.id: set(j.skills) for j in jobs}
    index = build_index(all_jobs)  # once
    for u in users:
        ok = {j.id for j in jobs if allowed(j, prefs)}  # cheap filter first
        top_matches(
            u,
            all_jobs,
            weights,
            20,
            index=index,
            within=ok,
            job_years=years,
            user_years=prefs.years_experience,
        )


def timed(fn, *args) -> float:
    start = time.perf_counter()
    fn(*args)
    return time.perf_counter() - start


async def main(sizes: list[int]) -> None:
    jobs, prefs = await load()
    weights = idf_weights([set(j.skills) for j in jobs])
    years = {j.id: years_required(j.requirements or []) for j in jobs}
    print(f"{len(jobs)} jobs, {len(weights)} distinct skills\n")
    print(
        f"{'users':>7} | {'old total':>10} | {'new total':>10} | {'old ms/user':>11} | {'new ms/user':>11} | speedup"
    )
    old_per_user = None
    for n in sizes:
        users = fake_users(jobs, n, random.Random(42))
        new = timed(new_way, users, jobs, prefs, weights, years)
        if n <= OLD_MAX:
            old = timed(old_way, users, jobs, prefs, weights, years)
            old_per_user = old / n
            old_txt = f"{old:9.2f}s"
        else:
            old = old_per_user * n  # extrapolated
            old_txt = f"~{old:8.0f}s"
        print(
            f"{n:>7} | {old_txt:>10} | {new:9.2f}s | {old / n * 1000:11.1f} | {new / n * 1000:11.1f} | {old / new:5.1f}x"
        )


if __name__ == "__main__":
    asyncio.run(main([int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "100,1000,10000").split(",")]))
