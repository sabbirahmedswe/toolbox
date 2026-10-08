from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.compress import GhostscriptMissing, Level, compress_pdf
from app.utils.files import PDF, attachment, output_stem, save_upload, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

GS_MISSING = "Compression is unavailable: Ghostscript is not installed on the server."

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_COMPRESSIONS)


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
            "Content-Disposition": attachment(f"{output_stem(name)}_compressed.pdf"),
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(len(data)),
        },
    )
