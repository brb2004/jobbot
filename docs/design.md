# JobBot Design

## Flow

crawl (bi-daily) Greenhouse Job Board API -> jobs (upsert on board+external_id)
job details per-job API -> decoded HTML (content_html) + plain text + salary
requirements selectolax: requirements section -> bullet list (no AI, 96% coverage)
resume upload pypdf / python-docx -> text (file type by magic bytes, not extension)
resume skills 7B: whole-text pass + 800-char chunks, union (AI, once per resume)
prefilter word overlap, jobs WITH requirements only -> top 20 per resume (no AI)
fit judge 14B: each requirement bullet vs skills -> yes / partial / no / soft
score (yes + 0.5 * partial) / (yes + partial + no); soft shown, not scored
dashboard GET /dashboard: my matches, best first
weekly email send_weekly: top N per user, skip users with no new matches


## Rules
- Crawling and parsing are plain code. AI only reads resumes and judges fit.
- Never twice: each expensive step only touches rows whose output is NULL. Failures stay NULL and retry next run.
- Prompts for judgment, code for rules. If the model won't follow an instruction, enforce it in code.
- Every behavior starts as a failing test. Every model change is measured with an eval.

## Structure
`app/{core,db,schemas,api/routes,services,llm,ingest}`, files named `<name>_<folder>.py`.
Route (HTTP only) -> service (logic + SQL) -> database.
Tests use a real Postgres (jobbot_test), each test inside a rolled-back transaction.
LLM, judge, extractor, email sender and HTTP are injected and faked in tests. CI runs them on every push.

## Decisions (with evidence)

**Python, not Rust, for the crawler.** Interview value is in explaining the code.

**7B extracts, 14B judges.**
- One-shot 7B scorer (judge + quote + format in one prompt): unmet items listed as met, items in both
  lists, scores clustered at 0.65. Rejected.
- 14B one-shot scorer: ~90 s/job, no more honest. Rejected.
- 14B as judge: term eval 17/20 (7B) -> 19/20 (14B), ~1.4 s/verdict.
- Fit judge on 14B: ~4.6 s/bullet, ~12 min/user/run at top 20. Fine for a bi-daily batch.

**Job requirements from HTML, not LLM extraction.**
- LLM extraction pulled in responsibilities, benefits (401k, equity), cities, soft skills.
- Headings are <strong>, h1-h6, or short plain <p> ending in ':'. <strong> counts only if it's
  its parent's whole text (bold inside a sentence or bullet isn't a heading).
- Coverage on 4,335 real jobs: 64 -> 81 -> 84 -> 88 -> 91 -> 94 -> 96%, one fixture and red test
  per company pattern (tests/fixtures/, app/ingest/coverage_sections.py).

**Judge each bullet against the whole skills list.** Comparing compound bullets to single skills
scored almost everything 0.0. yes/partial/no matches how real requirements are written.

**Soft skills shown, not scored.** A resume can't prove "fast-paced environment"; counting it as
missing discouraged users.
- Fit eval (16 labeled bullets, app/llm/eval_fit.py): 13/16; soft detection 3/3.
- Judge called "5+ years in security" soft. Prompt rule "years are NEVER soft" made it worse (11/16),
  reverted. Enforced in code: a soft verdict on years/degree requirements becomes "no".

**Resume skills: union of whole-text and chunked passes.** Single pass dropped Linux/Docker/CI;
chunks alone dropped the Languages line.

**Shortlist only jobs with requirements.** Fractional overlap gave title-only jobs (failed detail
fetches) 100% and crowded out real postings.

**Upload type by magic bytes.** A .docx named .txt put null bytes into Postgres (500). Found with a
real resume, reproduced as a test.

## Tried and dropped (in git history)
- Evidence-quote verification: caught invented quotes, not stretched ones.
- Embeddings + cached term-pair judge: right for keywords, wrong for compound bullets.
- Static alias table: not dynamic.

## Open issues
- Fit judge too strict on obvious matches (Linux -> partial). Next prompt experiment, measured by eval_fit.
- "built without Scrapy" still extracts Scrapy (negation).
- ~4% of jobs have no detectable requirements section.
- No real email sender; no cron jobs yet.
- Rotate the LiteLLM key from an earlier version of the repo.

## Incidents
- **Tests wiped the dev database.** direnv exported DATABASE_URL=jobbot_dev; conftest used setdefault, so
  the suite ran drop_all against dev. Fix: tests read TEST_DATABASE_URL only and refuse any database not
  named *_test. Data rebuilt from sources (crawl + re-upload) in ~20 min.
- **A revert removed more than intended.** One commit held smoothing + digest links; reverting it dropped
  both. Restored with `git checkout <commit> -- <files>`. Rule: one change per commit.

## Preferences
User-level title filters run before the shortlist (no AI spent on excluded jobs): include_titles (must
contain one) + exclude_titles (must contain none), whole-word matching that also handles "Sr.".
