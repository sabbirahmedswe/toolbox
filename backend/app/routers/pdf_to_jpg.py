from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.ghostscript import GhostscriptMissing
from app.services.pdf_to_jpg import Quality, pdf_to_jpg
from app.utils.files import PDF, attachment, save_upload, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

GS_MISSING = "PDF to JPG is unavailable: Ghostscript is not installed on the server."

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_PDF_TO_JPG)


@router.post(
    "/pdf-to-jpg",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}, "application/zip": {}}}},
    summary="Convert each page of a PDF to a JPG image",
)
async def convert(
    file: UploadFile = File(..., description="The PDF to convert"),
    quality: Quality = Form("normal", description="normal = 150 dpi, high = 300 dpi"),
):
    name = file.filename or "document.pdf"
    limiter.check()
    async with workdir() as tmp:
        src, _ = await save_upload(file, tmp / "in.pdf", (PDF,))
        async with limiter.slot():
            try:
                result = await run_in_threadpool(pdf_to_jpg, src, name, quality)
            except GhostscriptMissing:
                raise HTTPException(503, GS_MISSING)
    return Response(
        result.data,
        media_type=result.media_type,
        headers={"Content-Disposition": attachment(result.filename)},
    )
