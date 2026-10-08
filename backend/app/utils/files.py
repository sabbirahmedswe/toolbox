import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePath
from typing import BinaryIO
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config

CHUNK_SIZE = 1024 * 1024
# The PDF spec allows the %PDF- header anywhere in the first 1024 bytes.
PDF_HEADER_WINDOW = 1024

PDF = "pdf"
JPEG = "jpeg"
PNG = "png"

_LABELS = {PDF: "PDF", JPEG: "JPEG", PNG: "PNG"}


def attachment(filename: str) -> str:
    """Content-Disposition value with an ASCII fallback plus the UTF-8 name (RFC 6266)."""
    fallback = "".join(c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


# Path separators and characters Windows forbids in file names, so names are also safe as ZIP entries.
_UNSAFE_NAME_CHARS = set('/\\:*?"<>|')
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"{d}{n}" for d in ("COM", "LPT") for n in "123456789¹²³"}


def output_stem(upload_name: str) -> str:
    """`report.pdf` -> `report`, for naming results. Unsafe characters become `_`; `.pdf` -> `document`."""
    name = PurePath(upload_name).name
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    stem = "".join("_" if c in _UNSAFE_NAME_CHARS or not c.isprintable() else c for c in stem)
    stem = stem[:100].strip(" .") or "document"
    # Windows treats CON, CON.pdf and so on as devices, so a result like CON.pdf_1.pdf can't be extracted there.
    if stem.split(".")[0].rstrip(" ").upper() in _RESERVED_NAMES:
        stem = f"_{stem}"
    return stem


def make_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="ilovepdf-"))


def cleanup(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@asynccontextmanager
async def workdir() -> AsyncIterator[Path]:
    """A temp dir for one request, deleted on exit.

    Cleaned up here rather than in a response BackgroundTask, which Starlette skips if the response is aborted.
    """
    path = make_workdir()
    try:
        yield path
    finally:
        await run_in_threadpool(cleanup, path)


def check_file_count(files: list[UploadFile], minimum: int = 1) -> None:
    if len(files) < minimum:
        raise HTTPException(400, f"Please upload at least {minimum} file{'s' if minimum > 1 else ''}.")
    if len(files) > config.MAX_FILES:
        raise HTTPException(400, f"Too many files. The maximum is {config.MAX_FILES}.")


def detect_kind(head: bytes, allowed: tuple[str, ...]) -> str | None:
    if PDF in allowed and b"%PDF-" in head[:PDF_HEADER_WINDOW]:
        return PDF
    if JPEG in allowed and head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if PNG in allowed and head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    return None


def _copy_validated(src: BinaryIO, dest: Path, name: str, allowed: tuple[str, ...]) -> str:
    src.seek(0)
    head = src.read(CHUNK_SIZE)
    if not head:
        raise HTTPException(400, f'"{name}" is empty.')
    kind = detect_kind(head, allowed)
    if kind is None:
        expected = " or ".join(_LABELS[k] for k in allowed)
        raise HTTPException(400, f'"{name}" is not a valid {expected} file.')

    size = 0
    with dest.open("wb") as out:
        chunk = head
        while chunk:
            size += len(chunk)
            if size > config.MAX_FILE_SIZE:
                raise HTTPException(413, f'"{name}" is larger than the {config.MAX_FILE_SIZE_MB} MB limit.')
            out.write(chunk)
            chunk = src.read(CHUNK_SIZE)
    return kind


async def save_upload(upload: UploadFile, dest: Path, allowed: tuple[str, ...]) -> tuple[Path, str]:
    """Copy an upload to `dest`, enforcing the size limit and file type.

    Runs in a worker thread so large files don't block the event loop.
    Returns the saved path and the detected kind.
    """
    name = upload.filename or "file"
    kind = await run_in_threadpool(_copy_validated, upload.file, dest, name, allowed)
    return dest, kind


async def save_uploads(
    uploads: list[UploadFile], dest_dir: Path, allowed: tuple[str, ...], label: str = "file"
) -> list[tuple[Path, str, str]]:
    """Save each upload as `dest_dir/<index>`. Returns (path, kind, display name) in upload order."""
    saved = []
    for i, upload in enumerate(uploads):
        path, kind = await save_upload(upload, dest_dir / str(i), allowed)
        saved.append((path, kind, upload.filename or f"{label} {i + 1}"))
    return saved
