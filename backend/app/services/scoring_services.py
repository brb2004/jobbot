from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_db import Job, MatchScore, Resume
from app.services import embedding_services as embeddings
from app.services import extraction_services as extraction
from app.services import matcher_services as matcher
from app.services import prefilter_services as prefilter


async def score_new(s: AsyncSession, extractor, embedder, k: int = 20) -> int:
    # 1. resume skills (cached)
    await extraction.extract_resume_skills(s, extractor)
    resumes = (await s.execute(select(Resume).where(Resume.skills.is_not(None)))).scalars().all()
    jobs = list((await s.execute(select(Job))).scalars().all())
    already = set((await s.execute(select(MatchScore.resume_id, MatchScore.job_id))).all())

    # 2. shortlist per resume (no AI), skipping pairs already scored
    plan = [(r, j) for r in resumes
            for j in prefilter.top_k(r.raw_text or "", jobs, k)
            if (r.id, j.id) not in already]

    # 3. requirements only for shortlisted jobs (cached)  4. vectors for new terms (cached)
    await extraction.extract_job_requirements(s, extractor, job_ids={j.id for _, j in plan})
    await embeddings.embed_new_terms(s, embedder)

    # 5. match (math)
    scored = 0
    for resume, job in plan:
        if not job.requirements:
            continue                                   # extraction failed or empty: retried next run
        vectors = await embeddings.vectors_for(s, [*job.requirements, *resume.skills])
        result = matcher.match(job.requirements, resume.skills, vectors)
        if result is None:
            continue
        s.add(MatchScore(resume_id=resume.id, job_id=job.id, score=result.score,
                         detail={"met": result.met, "missing": result.missing,
                                 "evidence": result.evidence}))
        scored += 1
    await s.commit()
    return scored
