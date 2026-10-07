from pathlib import PurePath

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.compress import GhostscriptMissing, Level, compress_pdf
from app.utils.files import PDF, attachment, save_upload, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

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
                raise HTTPException(503, "Compression is unavailable: Ghostscript is not installed on the server.")
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
