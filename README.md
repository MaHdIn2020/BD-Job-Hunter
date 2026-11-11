# BD Job Hunter

A FastAPI web application for Bangladeshi students and fresh graduates to upload their CV, maintain an editable AI-extracted profile, discover remote and local jobs, compute transparent Python skill-match scores, draft application emails and cover notes with Groq, save jobs, and track applications.

> **Safety Rule:** Review before sending. BD Job Hunter never sends emails or auto-applies for you.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`
- **Database:** SQLite, SQLAlchemy 2.0
- **Frontend:** Jinja2 templates, Tailwind CSS (CDN), Vanilla JS
- **AI & Parsing:** Groq SDK, `pypdf`, `python-docx`
- **Security:** `bcrypt`, `itsdangerous` (Starlette `SessionMiddleware` + CSRF)
- **Testing & Quality:** `pytest`, `respx`, `ruff`

## Quickstart (Windows PowerShell)

1. **Create and activate the virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   Copy `.env.example` to `.env` and set a non-empty `SECRET_KEY` (and optional `GROQ_API_KEY` / `GROQ_MODEL`).
   ```powershell
   Copy-Item .env.example .env
   ```

4. **Run the development server:**
   ```powershell
   python run.py
   ```
   Open `http://127.0.0.1:8000/health` to verify the server is running.

5. **Run tests:**
   ```powershell
   pytest -q
   ```

6. **Run linter and formatter check:**
   ```powershell
   ruff check .
   ruff format --check .
   ```

