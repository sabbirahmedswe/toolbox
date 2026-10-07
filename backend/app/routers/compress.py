from pathlib import PurePath

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.compress import GhostscriptMissing, Level, compress_pdf
from app.utils.files import PDF, attachment, cleanup, make_workdir, save_upload

router = APIRouter()

# Ghostscript jobs currently running. Only touched from the event loop, so no lock is needed.
_active_jobs = 0


def output_name(upload_name: str) -> str:
    """`report.pdf` -> `report_compressed.pdf`, with a fallback for names like `.pdf`."""
    name = PurePath(upload_name).name
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    return f"{stem or 'document'}_compressed.pdf"


@router.post(
    "/compress",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Compress a PDF with Ghostscript",
)
async def compress(
    file: UploadFile = File(..., description="The PDF to compress"),
    level: Level = Form("medium", description="low = best quality, high = smallest file"),
):
    global _active_jobs
    name = file.filename or "document.pdf"
    workdir = make_workdir()
    try:
        src, _ = await save_upload(file, workdir / "in.pdf", (PDF,))
        if _active_jobs >= config.MAX_CONCURRENT_COMPRESSIONS:
            raise HTTPException(503, "The server is busy compressing other files. Please try again in a moment.")
        _active_jobs += 1
        try:
            result, _ = await run_in_threadpool(compress_pdf, src, workdir / "out.pdf", level, name)
        except GhostscriptMissing:
            raise HTTPException(503, "Compression is unavailable: Ghostscript is not installed on the server.")
        finally:
            _active_jobs -= 1
        original_size = src.stat().st_size
        data = await run_in_threadpool(result.read_bytes)
    finally:
        # Cleaned up here rather than in a response BackgroundTask, which
        # Starlette skips if the response is aborted.
        await run_in_threadpool(cleanup, workdir)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": attachment(output_name(name)),
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(len(data)),
        },
    )
