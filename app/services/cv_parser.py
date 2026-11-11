"""In-memory CV upload validation and text extraction for PDF and DOCX files."""

import io
import logging
import re
import zipfile
from pathlib import Path

from docx import Document
from fastapi import Request, UploadFile
from pypdf import PdfReader

from app.config import get_settings

logger = logging.getLogger(__name__)

CHUNK_SIZE_BYTES = 64 * 1024
CONTENT_LENGTH_OVERHEAD_BYTES = 1 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_DOCX_ENTRIES = 200
MAX_PDF_PAGES = 10
MAX_EXTRACTED_TEXT_CHARS = 50_000
MAX_PASTE_TEXT_CHARS = 20_000
MIN_NON_WHITESPACE_CHARS = 20

PDF_SIGNATURE = b"%PDF"
ZIP_SIGNATURE = b"PK\x03\x04"

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
SAFE_FILENAME_RE = re.compile(r"[^\w.\- ()\u0980-\u09FF]")


class CVParseError(Exception):
    """User-friendly error raised when CV upload validation or text extraction fails."""


def sanitize_display_filename(raw_filename: str | None) -> tuple[str, str]:
    """Ignore path components, validate extension (.pdf/.docx), and return (safe_name, ext)."""
    if not raw_filename:
        raise CVParseError("Please select a PDF or DOCX file to upload.")
    base_name = Path(raw_filename.replace("\\", "/")).name.strip()
    ext = Path(base_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise CVParseError("Unsupported file type. Please upload a .pdf or .docx file.")

    stem = Path(base_name).stem
    cleaned_stem = SAFE_FILENAME_RE.sub("_", stem).strip("._ ")
    if not cleaned_stem:
        cleaned_stem = "uploaded_cv"
    safe_name = f"{cleaned_stem[:80]}{ext}"
    return safe_name, ext


def check_request_content_length(request: Request, max_upload_mb: int | None = None) -> None:
    """Reject early if Content-Length header exceeds MAX_UPLOAD_MB + 1 MB multipart overhead.

    Note: Starlette may spool the multipart body to a temp file before the route handler runs,
    so production deployments should also set a reverse-proxy body size limit.
    """
    limit_mb = max_upload_mb if max_upload_mb is not None else get_settings().MAX_UPLOAD_MB
    max_header_bytes = (limit_mb * 1024 * 1024) + CONTENT_LENGTH_OVERHEAD_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            total_bytes = int(content_length)
        except ValueError as exc:
            raise CVParseError("Invalid upload request size.") from exc
        if total_bytes > max_header_bytes:
            raise CVParseError(f"File is too large. Maximum allowed size is {limit_mb} MB.")


def read_upload_bytes_bounded(upload_file: UploadFile, max_upload_mb: int | None = None) -> bytes:
    """Read upload_file.file in chunks, enforcing the exact MAX_UPLOAD_MB byte limit."""
    limit_mb = max_upload_mb if max_upload_mb is not None else get_settings().MAX_UPLOAD_MB
    max_bytes = limit_mb * 1024 * 1024

    buffer = bytearray()
    while True:
        chunk = upload_file.file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise CVParseError(f"File exceeds the {limit_mb} MB size limit.")

    if len(buffer) == 0:
        raise CVParseError(
            "The uploaded file is empty. Please upload a valid CV or paste your CV text below."
        )
    return bytes(buffer)


def _count_non_whitespace(text: str) -> int:
    """Return number of non-whitespace characters in text."""
    return len(re.sub(r"\s+", "", text))


def _normalize_extracted_text(raw_text: str) -> str:
    """Normalize line breaks, cap at MAX_EXTRACTED_TEXT_CHARS, and verify minimum text length."""
    cleaned = raw_text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in cleaned.split("\n")]
    compact = "\n".join(line for line in lines if line)
    capped = compact[:MAX_EXTRACTED_TEXT_CHARS].strip()

    if _count_non_whitespace(capped) < MIN_NON_WHITESPACE_CHARS:
        raise CVParseError(
            "No selectable text was found in this file (it may be a blank page or a scanned "
            "image PDF). Please paste your CV text in the box below."
        )
    return capped


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Verify %PDF magic bytes, reject encrypted PDFs, and extract up to 10 pages."""
    if not data.startswith(PDF_SIGNATURE):
        raise CVParseError("Invalid PDF file signature. Please upload a genuine PDF file.")

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise CVParseError(
                "This PDF is password-protected or encrypted. Please upload an unencrypted "
                "PDF or paste your CV text."
            )
        page_texts: list[str] = []
        for page in reader.pages[:MAX_PDF_PAGES]:
            extracted = page.extract_text() or ""
            if extracted:
                page_texts.append(extracted)
    except CVParseError:
        raise
    except Exception as exc:
        logger.warning("PDF parse error (%s)", type(exc).__name__)
        raise CVParseError(
            "Could not read this PDF file because it appears corrupted. Please paste your "
            "CV text below instead."
        ) from exc

    return _normalize_extracted_text("\n".join(page_texts))


def extract_text_from_docx_bytes(data: bytes) -> str:
    """Verify ZIP signature and zip-bomb bounds, then extract paragraphs and tables from DOCX."""
    if not data.startswith(ZIP_SIGNATURE):
        raise CVParseError(
            "Invalid DOCX file signature. Please upload a genuine Word (.docx) file."
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_DOCX_ENTRIES:
                raise CVParseError(
                    "This DOCX file contains too many internal archive entries and was rejected."
                )
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise CVParseError(
                    "This DOCX file expands beyond the 20 MB safety limit and was rejected."
                )
            names = {info.filename for info in infos}
            if "word/document.xml" not in names:
                raise CVParseError("Invalid DOCX structure (missing word/document.xml).")
    except CVParseError:
        raise
    except Exception as exc:
        logger.warning("DOCX zip validation error (%s)", type(exc).__name__)
        raise CVParseError(
            "Could not read this DOCX file because it appears corrupted. Please paste your "
            "CV text below."
        ) from exc

    try:
        doc = Document(io.BytesIO(data))
        parts: list[str] = []
        for paragraph in doc.paragraphs:
            if paragraph.text and paragraph.text.strip():
                parts.append(paragraph.text.strip())
        for table in doc.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    parts.append(" | ".join(row_cells))
    except Exception as exc:
        logger.warning("DOCX content parse error (%s)", type(exc).__name__)
        raise CVParseError(
            "Could not extract text from this DOCX file. Please paste your CV text below."
        ) from exc

    return _normalize_extracted_text("\n".join(parts))


def parse_uploaded_cv(
    request: Request,
    upload_file: UploadFile,
    max_upload_mb: int | None = None,
) -> tuple[str, str]:
    """Validate and extract text from an uploaded PDF or DOCX CV without saving to disk."""
    check_request_content_length(request, max_upload_mb=max_upload_mb)
    safe_filename, ext = sanitize_display_filename(upload_file.filename)
    raw_bytes = read_upload_bytes_bounded(upload_file, max_upload_mb=max_upload_mb)

    if ext == ".pdf":
        text = extract_text_from_pdf_bytes(raw_bytes)
    else:
        text = extract_text_from_docx_bytes(raw_bytes)

    return safe_filename, text


def validate_pasted_cv_text(raw_text: str) -> str:
    """Validate pasted CV text (20 non-whitespace chars min, 20,000 chars max)."""
    cleaned = raw_text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(cleaned) > MAX_PASTE_TEXT_CHARS:
        raise CVParseError(
            f"Pasted CV text is too long (maximum {MAX_PASTE_TEXT_CHARS:,} characters)."
        )
    if _count_non_whitespace(cleaned) < MIN_NON_WHITESPACE_CHARS:
        raise CVParseError("Please paste at least 20 characters of CV text.")
    return cleaned
