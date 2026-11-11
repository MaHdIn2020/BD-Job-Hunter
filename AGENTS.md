# AGENTS.md - BD Job Hunter (Antigravity rules)

## Context
- Project: FastAPI web app for Bangladeshi students and fresh graduates. CV upload, editable AI profile, job discovery, Python skill-match score, Groq-written application emails, saved jobs, application tracker.
- Phase plan and scope: `docs/BUILD_PROMPT.md`. Follow it. If this file and the plan conflict, ask the user.
- Current phase: 3 (the user edits this line after each approved phase).
- Stack: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy 2.0, SQLite, Jinja2, vanilla JS, Tailwind CDN, Groq SDK, pypdf, python-docx, bcrypt, itsdangerous, httpx. Dev: pytest, respx, ruff.

## Agent behavior
- Do ONE phase per request. Never start the next phase. Never generate the whole project.
- Before coding a phase, post a short plan: what, why, technologies, files to create or change, expected result. Wait for the user's go-ahead only if the plan changes scope.
- After a phase: run tests and lint, start the app once to confirm it boots, stop it, then report: files changed, tests passed or failed, manual test steps, a Conventional Commit message. Then STOP and wait for `next`.
- Make the smallest change that works. Never rewrite working files. Never delete features without asking.
- Do not re-read the whole repo each turn. Open only files the current phase needs.
- Keep replies short. Explain a concept only when it first appears: 3-5 lines (what, why, how it works here, which file).
- Never say a feature works unless you ran it.
- Explain an error before attempting a large fix.
- Ask before adding any dependency.
- Ask before editing `AGENTS.md`, `docs/BUILD_PROMPT.md`, `.env.example` structure, or CI config.

## Terminal rules
- Work inside the project virtual environment. Activate it before every Python command.
- Run one command at a time. Read the output before the next command.
- Never run: `rm -rf`, `git push --force`, `git reset --hard`, or any command that deletes `data/`, `tests/fixtures/` or `.git`. Ask first.
- Never push to a remote, merge branches, or create releases unless the user asks.
- Run the dev server only for a quick check, then stop it. Never leave a server running in the background.
- Never print, echo or commit values from `.env`.

## Browser rules
- Do not use the browser agent to scrape LinkedIn, Facebook, BDJobs or any job site.
- Do not log in to any account.
- Use the browser only to view the app on localhost for UI checks.

## Code style
- Simple and readable. Small single-purpose functions. Clear names. Type hints.
- Use `logging`, not `print`.
- Read config only through `app/config.py`.
- Keep files under about 200 lines.
- No clever abstractions.
- Use `pathlib` for paths.

## Security rules
- Never hardcode secrets. Never commit `.env`, `data/`, `*.db`, real CVs. Keep `.env.example` current.
- Hash passwords with `bcrypt`. Reject passwords over 72 bytes. Never log or return hashes.
- Sessions: Starlette `SessionMiddleware`, cookie holds only `user_id`, `same_site='lax'`, `https_only` in production.
- CSRF: token in every POST form, verified server-side, 403 on failure.
- Access control: filter every profile, saved job, application and manual job query by the current `user_id`. Return 404 for another user's record. API and demo jobs have `created_by_user_id = NULL`.
- Jinja2 autoescape stays ON. Never use `|safe` on user, job or AI text. Strip HTML from API descriptions.
- Uploads: enforce the size limit while reading. Check extension AND file signature (`%PDF` for PDF, zip for DOCX). Ignore the user's filename. Do not store the file; store only filename and extracted text.
- Prompts: wrap CV and job text in tags and declare them untrusted data. Validate AI output with Pydantic.
- Never let AI invent CV facts. Never let AI change the numeric match score.
- Never send email, auto-apply or auto-submit anything.
- Never scrape any site without an API or permission. Read an API's current docs and terms before writing its adapter.

## Domain rules
- Match score is computed in Python only. Required skill weight 1, preferred weight 0.5. `score = round(100 * matched_weight / total_weight)`. No listed skills means "insufficient data". Normalize skills: lowercase, trim, small synonym map.
- Use `Asia/Dhaka` via `zoneinfo`. Pass `today` as a parameter. Never read the clock inside logic. Tests use `today = 2026-11-11`. Hide expired jobs by default.
- Generated email: 80-200 words, names the company and role, uses only skills in the profile, no placeholders like `[Your Name]`, ends with the user's name. Retry once on invalid output, then show a friendly error.
- Always show: "Review before sending. BD Job Hunter never sends emails for you."
- Demo jobs: `is_demo=True` and a visible DEMO badge. Never present as real vacancies.

## External APIs
- Groq: model name from `GROQ_MODEL` in `.env`. Never invent model names. Handle 429, timeout, missing key with friendly messages. Never call Groq at import time.
- Jobicy `https://jobicy.com/api/v2/remote-jobs`: free, no key. Credit Jobicy. Link to the original listing. Call at most once per hour (cooldown in `source_state`). Decode HTML-encoded titles. Do not redistribute listings to other job platforms.
- RemoteOK `https://remoteok.com/api`: free. Credit RemoteOK. Link back. Send `SOURCE_USER_AGENT`. Skip the first array item (legal notice).
- On API failure show cached jobs and a message. Never crash a page.

## Testing rules
- Every feature ships with tests in the same phase.
- Default tests never use the network or real Groq. Mock Groq. Mock HTTP with `respx`.
- Real-service tests use `@pytest.mark.live` and are skipped by default.
- In-memory SQLite with `StaticPool`. Override `get_db`. No shared state. No `time.sleep`.
- Fixtures live in `tests/fixtures/` (all fake). Read its README.
- Write an access-control test for every user-owned resource.
- Commands: `pytest -q`, `ruff check .`, `ruff format --check .`.

## Git rules
- Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`.
- One branch per phase: `phase/NN-name`.
- Before suggesting a commit: lint, tests, then `git status`. Confirm no `.env`, `data/`, `*.db`, CVs.
- Run the final checks as the LAST step before commit: `ruff format .`, `ruff check .`, `ruff format --check .`, `pytest -q`, `git ls-files --eol`. Never modify files after the checks. Never rewrite file bytes with custom scripts.
- If a secret was committed: stop, tell the user, tell them to rotate the key.
