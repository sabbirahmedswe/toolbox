import time
from pathlib import PurePath
from typing import get_args

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.errors import ProcessingError
from app.services.compress import GhostscriptMissing, Level, check_compressible, compress_pdf, estimate_size, too_long
from app.utils.files import PDF, attachment, save_upload, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

GS_MISSING = "Compression is unavailable: Ghostscript is not installed on the server."

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_COMPRESSIONS)


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
    name = file.filename or "document.pdf"
    limiter.check()
    async with workdir() as tmp:
        src, _ = await save_upload(file, tmp / "in.pdf", (PDF,))
        async with limiter.slot():
            try:
                result, _ = await run_in_threadpool(compress_pdf, src, tmp / "out.pdf", level, name)
            except GhostscriptMissing:
                raise HTTPException(503, GS_MISSING)
        original_size = src.stat().st_size
        data = await run_in_threadpool(result.read_bytes)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": attachment(output_name(name)),
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(len(data)),
        },
    )


def estimate_reserve() -> int:
    """Slots an estimate must leave free: half of them (rounded up), so optional estimates can't
    crowd out real compressions. With a single slot there are no estimates."""
    return (config.MAX_CONCURRENT_COMPRESSIONS + 1) // 2


@router.post("/compress/estimate", summary="Estimate the compressed size of a PDF at each level")
async def estimate(request: Request, file: UploadFile = File(..., description="The PDF to estimate")):
    name = file.filename or "document.pdf"
    limiter.check(reserve=estimate_reserve())
    async with workdir() as tmp:
        src, _ = await save_upload(file, tmp / "in.pdf", (PDF,))
        async with limiter.slot(reserve=estimate_reserve()):
            try:
                gs = await run_in_threadpool(check_compressible, src, name)
            except GhostscriptMissing:
                raise HTTPException(503, GS_MISSING)
            # One time budget for all levels, so an estimate holds its slot no longer than one compression.
            deadline = time.monotonic() + config.GS_TIMEOUT_SECONDS
            levels = get_args(Level)  # slowest (highest quality) first, so the projection below errs high
            sizes: dict[str, int] = {}
            for i, level in enumerate(levels):
                # Stop between levels once the page has moved on (another file picked, or closed).
                if await request.is_disconnected():
                    return Response(status_code=204)
                started = time.monotonic()
                sizes[level] = await run_in_threadpool(estimate_size, gs, src, tmp, level, name, deadline)
                # Give up now rather than burn the rest of the budget on levels that won't fit.
                now = time.monotonic()
                if (now - started) * (len(levels) - i - 1) > deadline - now:
                    raise ProcessingError(too_long(name))
        return {"original_size": src.stat().st_size, "sizes": sizes}
