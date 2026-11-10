"""Glue between the database and the pure matcher in scoring_services."""
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume, User
from app.services.preferences_services import Preferences, allowed
from app.services.scoring_services import build_index, idf_weights, needs_clearance, top_matches, years_from_title, years_required
from app.services.skills_services import default_tagger
from app.services.titles_services import role_key


def _stale(model, tagger):
    """Never tagged, or tagged with a different skills.txt."""
    return or_(model.skills_version.is_(None), model.skills_version != tagger.version)


async def tag_jobs(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    jobs = (await s.scalars(select(Job).where(Job.requirements.is_not(None), _stale(Job, tagger)))).all()
    for job in jobs:
        job.skills = sorted(set().union(*(tagger.tag(b) for b in job.requirements)))
        job.skills_version = tagger.version
    await s.commit()
    return len(jobs)


async def tag_resumes(s: AsyncSession, tagger=None) -> int:
    tagger = tagger or default_tagger()
    resumes = (await s.scalars(select(Resume).where(Resume.raw_text.is_not(None), _stale(Resume, tagger)))).all()
    for r in resumes:
        r.skills = sorted(tagger.tag(r.raw_text))
        r.skills_version = tagger.version
    await s.commit()
    return len(resumes)


def _extra(prefs: Preferences) -> set[str]:
    """User-typed skills -> canonical names via the tagger ('k8s' -> 'Kubernetes'); unknown words drop out."""
    tagger = default_tagger()
    return set().union(*(tagger.tag(s) for s in prefs.extra_skills))


async def match_all(s: AsyncSession, k: int = 20, user_id: UUID | None = None) -> int:
    """Recompute every user's top k from scratch. Deterministic and cheap, so no caching needed."""
    tagger = default_tagger()
    # only the columns matching needs: skipping content_html/description is ~100 MB less per run
    cols = select(Job.id, Job.board, Job.title, Job.location, Job.skills, Job.requirements)
    jobs = [j for j in (await s.execute(cols.where(Job.skills.is_not(None), Job.closed_at.is_(None)))).all()
            if j.skills]
    weights = idf_weights([set(j.skills) for j in jobs])                    # weights from ALL jobs
    years, years_src = {}, {}
    for j in jobs:                                                          # stated number first, then the title
        stated = years_required(j.requirements or [])
        years[j.id] = stated if stated is not None else years_from_title(j.title)
        years_src[j.id] = "requirements" if stated is not None else "title"
    by_id = {j.id: j for j in jobs}
    roles = {j.id: (j.board, role_key(j.title)) for j in jobs}  # one per company + title
    all_jobs = {j.id: set(j.skills) for j in jobs}
    index = build_index(all_jobs)                                           # once per run, shared by every user
    users = {u.id: u for u in (await s.scalars(select(User))).all()}        # one query, not one per resume
    saved = 0
    resumes = select(Resume).where(Resume.skills.is_not(None))
    if user_id is not None:
        resumes = resumes.where(Resume.user_id == user_id)                 # just this user
    for resume in (await s.scalars(resumes)).all():
        user = users.get(resume.user_id)
        prefs = Preferences.model_validate((user.preferences if user else None) or {})
        ok = {j.id for j in jobs if allowed(j, prefs)}                      # cheap + selective: filter first
        await s.execute(delete(MatchScore).where(MatchScore.resume_id == resume.id))
        for m in top_matches(tagger.expand(set(resume.skills) | _extra(prefs)), all_jobs, weights, k,
                             index=index, within=ok, dedupe_key=roles, job_years=years, user_years=prefs.years_experience if prefs.years_experience is not None else resume.years_detected):
            s.add(MatchScore(resume_id=resume.id, job_id=m.job_id, score=m.score,
                             detail={"met": m.matched, "partial": [], "missing": m.missing, "soft": [],
                                     "years_asked": m.years_asked,
                                     "years_source": years_src.get(m.job_id), "over_years": m.over_years,
                                     "no_language": m.no_language,
                                     "clearance": needs_clearance(by_id[m.job_id].title,
                                                                  by_id[m.job_id].requirements or [])}))
            saved += 1
    await s.commit()                                                        # one commit for the whole run
    return saved
