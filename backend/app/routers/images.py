from fastapi import APIRouter, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.images import images_to_pdf
from app.utils.files import JPEG, PNG, attachment, check_file_count, cleanup, make_workdir, save_upload
from app.utils.limits import JobLimiter

router = APIRouter()

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_IMAGE_JOBS)


@router.post(
    "/images-to-pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Convert JPEG/PNG images to a PDF, one page per image in upload order",
)
async def images_to_pdf_route(files: list[UploadFile] = File(..., description="One or more JPEG or PNG images")):
    check_file_count(files, minimum=1)
    limiter.check()
    workdir = make_workdir()
    try:
        inputs = []
        for i, upload in enumerate(files):
            path, kind = await save_upload(upload, workdir / f"{i}", (JPEG, PNG))
            inputs.append((path, kind, upload.filename or f"image {i + 1}"))
        async with limiter.slot():
            pdf = await run_in_threadpool(images_to_pdf, inputs, workdir)
    finally:
        # Cleaned up here rather than in a response BackgroundTask, which
        # Starlette skips if the response is aborted.
        await run_in_threadpool(cleanup, workdir)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment("images.pdf")},
    )
