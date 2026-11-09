# JobBot

![tests](https://github.com/brb2004/jobbot/actions/workflows/tests.yml/badge.svg)

Crawls Greenhouse job boards, matches every posting against each user's resume, and emails each user their top 20 every week. **Matching is fully deterministic: no AI in the decision path.** Every score traces back to named skills and their weights, and the same input always gives the same output.

## Pipeline

```
42 Greenhouse boards ──crawl every 2 days──▶ jobs (upsert; closed when a board stops listing them)
        │
        ▼
requirements section (selectolax HTML parse) ──▶ skill tags (taxonomy tagger, versioned)
                                                         │
resume (PDF / DOCX) ──text──▶ skill tags ──▶ + implied skills (RAG ⇒ LLM ⇒ AI)
                                                         │
                         per-user preferences (titles, locations, remote regions, years)
                                                         │
                         IDF-weighted match ──▶ top 20 ──▶ dashboard API + weekly email (tiers)
```

## Why deterministic

The first version used local LLMs (Qwen 7B to extract, 14B to judge each requirement). It worked, at 19/20 on its eval set, but it took **about 12 minutes per user**, couldn't explain its scores, and gave different answers on reruns. Hiring is also exactly where automated decisions get scrutinized. v2 replaced the model with plain data structures:

| | v1 (LLM judge) | v2 (deterministic) |
|---|---|---|
| Time per user | ~12 min | ~9 ms |
| Explainable | "the model said so" | every point maps to a skill and its weight |
| Reproducible | no | yes |
| Hardware | GPU | any CPU |

v1 is archived at tag [`v1-llm`](../../tree/v1-llm).

## How matching works

**1. Skill tagging.** `skills.txt` is a curated taxonomy, one skill per line: `PostgreSQL: postgres, psql`. All aliases compile into one regex with whole-word boundaries, and the longest match wins, so "React Native" isn't also "React" and "Java" never matches inside "JavaScript". A leading `=` makes a name case-sensitive, so `=Go` matches "Go, Python" but not "go above and beyond". The taxonomy is versioned by content hash: editing it re-tags every stale job and resume on the next run.

**2. Implications.** `RAG > LLM` means having RAG implies having LLM, applied transitively. Implications expand the *user's* skills only, never a job's requirements. A typo in an implication fails at startup instead of silently matching nothing.

**3. Scoring.** Rare skills matter more than common ones:

```
weight(s) = log((1 + N) / (1 + jobs_with(s))) + 1                 # smoothed IDF
score     = Σ weight(have) / (Σ weight(all) + PRIOR · avg_weight)  # PRIOR = 2
```

The prior adds two imaginary unmet skills of average weight, so a posting that names one skill can't outrank one that names six. Because it's measured in average-skill units, scaling every weight by the same factor leaves every score unchanged. Jobs asking for more than your years of experience + 1 are halved and flagged ("asks for 5+ years"), never hidden.

**4. Retrieval.** One inverted index (`skill → job ids`) is built per run. For each user, the cheap and highly selective preference filter runs first, then only jobs that share a skill *and* pass the filter are scored, and a heap keeps the best 20.

**5. Output.** Tiers instead of percentages ("Strong match / Worth applying / Stretch"), so a 30% doesn't scare anyone off. Soft skills are never scored.

## Performance

Measured with `python -m app.services.bench_matching`: 7.4k real jobs, seeded fake users with realistic skill sets and real preferences.

| Step | ms/user | Finding |
|---|---|---|
| Baseline (per-user pool + index) | 80 | |
| Shared global index | 56 | the index rebuild wasn't the bottleneck |
| Lazy best-first filtering | 56 | the filter keeps ~1% of jobs, so laziness can't stop early |
| **Profile: `has_word` = 84% of time → one cached regex per word list** | **8.6** | **the real bottleneck (9x)** |
| Lazy + cheap filter | 41 | slower: scores thousands of jobs before filtering |
| Filter first, then score | 9 | cheap selective predicate first, like a query planner |

10,000 users take about 90 seconds per run on one core. Users are independent, so it parallelizes trivially.

## Correctness safeguards

- **Closed postings:** jobs missing from a *successfully* fetched board get `closed_at`; failed or 404 fetches close nothing; relisted jobs reopen. The first run cleared 1,143 dead postings.
- **Idempotent crawl:** `INSERT … ON CONFLICT` on `(board, external_id)`; only new jobs get their details fetched.
- **Test isolation:** tests run on a real Postgres `*_test` database inside rolled-back transactions, and refuse to start if pointed at anything else.
- **Uploads:** file type comes from magic bytes, not the extension.
- **Polite crawling:** bounded concurrency and an identifying User-Agent.

## Stack

Python 3.12 · FastAPI · async SQLAlchemy 2 + asyncpg · Postgres 16 · Alembic · selectolax · pytest (TDD) · GitHub Actions · cron + flock

## Run it

```bash
docker compose up -d db                      # Postgres on :55432
cd backend
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                         # DATABASE_URL, JWT_SECRET_KEY, SMTP_*
alembic upgrade head

python -m app.ingest.check_boards            # validate boards.txt slugs
python -m app.ingest.run_ingest              # crawl
python -m app.services.run_matching          # tag + match everyone
uvicorn app.main:app --reload                # API

TEST_DATABASE_URL=postgresql+asyncpg://jobbot:jobbot123@localhost:55432/jobbot_test pytest
```

## Layout

```
backend/
  app/core       config, db, security
  app/db         models
  app/api        routes (auth, resumes, preferences, matches)
  app/ingest     Greenhouse crawler, requirements-section parser
  app/services   tagger, scoring, matching, preferences, digest, benchmarks
  boards.txt     Greenhouse board slugs
  skills.txt     skill taxonomy + implications
  tests/
docs/design.md   decisions and incidents
```

## Roadmap

- Skill discovery: learn new skills from list contexts in postings ("Python, Go, and Prism"), promoted only with evidence across multiple companies
- More job sources beyond Greenhouse
- Frontend
- Recruiter side: let recruiters search for developers, built on the same explainable scoring
