from fastapi import APIRouter, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.jpg_to_pdf import jpg_to_pdf
from app.utils.files import JPEG, attachment, check_file_count, save_uploads, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_IMAGE_JOBS)


@router.post(
    "/jpg-to-pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Convert JPEG images to a PDF, one page per image in upload order",
)
async def convert(files: list[UploadFile] = File(..., description="One or more JPEG images")):
    check_file_count(files, minimum=1)
    limiter.check()
    async with workdir() as tmp:
        saved = await save_uploads(files, tmp, (JPEG,), label="image")
        inputs = [(path, name) for path, _, name in saved]
        async with limiter.slot():
            pdf = await run_in_threadpool(jpg_to_pdf, inputs, tmp)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment("images.pdf")},
    )
