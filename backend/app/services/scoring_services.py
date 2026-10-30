from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume
from app.llm.scorer_llm import MAX_CHARS
from app.services import embedding_services as embeddings
from app.services import extraction_services as extraction
from app.services import matcher_services as matcher
from app.services import prefilter_services as prefilter
from app.services.judge_services import CachedJudge


async def score_new(s: AsyncSession, resume_extractor, job_extractor, embedder, judge, k: int = 20) -> int:
    await extraction.extract_resume_skills(s, resume_extractor)                 # chunked
    resumes = (await s.execute(select(Resume).where(Resume.skills.is_not(None)))).scalars().all()
    jobs = list((await s.execute(select(Job))).scalars().all())
    already = set((await s.execute(select(MatchScore.resume_id, MatchScore.job_id))).all())

    plan = [(r, j) for r in resumes
            for j in prefilter.top_k(r.raw_text or "", jobs, k)
            if (r.id, j.id) not in already]

    await extraction.extract_job_requirements(s, job_extractor, job_ids={j.id for _, j in plan},
                                              chunk_size=MAX_CHARS)             # whole posting, one call
    await embeddings.embed_new_terms(s, embedder)
    cached_judge = CachedJudge(s, judge)

    scored = 0
    for resume, job in plan:
        if not job.requirements:
            continue
        vectors = await embeddings.vectors_for(s, [*job.requirements, *resume.skills])
        result = await matcher.match(job.requirements, resume.skills, vectors, cached_judge)
        if result is None:
            continue
        s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=result.score,
                         detail={"met": result.met, "missing": result.missing,
                                 "evidence": result.evidence}))
        scored += 1
    await s.commit()
    return scored
