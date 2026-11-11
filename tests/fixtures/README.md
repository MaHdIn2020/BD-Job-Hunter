# Test fixtures (all fake)

All people, companies and emails are fictional (`example.com` / `.example` domains).
Tests must pass `today = 2026-11-11` into date logic. Do not use the real clock.

| File | Used for |
|---|---|
| cvs/sample_cv.pdf, sample_cv.docx | Normal CV: text extraction, profile extraction (mocked Groq) |
| cvs/sample_cv_bangla.pdf, .docx | Bangla text survives extraction and storage |
| cvs/sample_cv.txt | Paste-CV-text fallback |
| cvs/empty.pdf | Blank page: friendly "no text found" error |
| cvs/scanned.pdf | Image-only PDF: no text layer, friendly error |
| cvs/corrupt.pdf | Broken PDF: parser error handled, no crash |
| cvs/spoofed_exe.pdf | Executable bytes named .pdf: rejected by signature check |
| jobs/demo_jobs.json | 10 demo jobs (one expired, one with no skills) |
| jobs/manual_job_posts.json | 3 Facebook-style posts with expected extraction (one expired, one obfuscated email) |
| api_samples/ | Real Jobicy and RemoteOK responses you save yourself (see HOW_TO_SAVE.md) |

The sample CV skills are Python, JavaScript, React, MongoDB, Django, Git (no PostgreSQL, no REST API).
Match test: candidate vs required Python, Django, PostgreSQL, REST API gives 50 percent.
