"""Local development server launcher."""

import uvicorn

from app.config import get_settings


def main() -> None:
    """Validate settings and start the Uvicorn development server."""
    settings = get_settings()
    reload_enabled = settings.ENV == "development"
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=reload_enabled)


if __name__ == "__main__":
    main()

