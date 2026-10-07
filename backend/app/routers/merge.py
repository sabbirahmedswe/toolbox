from fastapi import APIRouter, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.services.merge import merge_pdfs
from app.utils.files import PDF, attachment, check_file_count, cleanup, make_workdir, save_upload

router = APIRouter()


@router.post(
    "/merge",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Merge PDFs in upload order",
)
async def merge(files: list[UploadFile] = File(..., description="Two or more PDF files")):
    check_file_count(files, minimum=2)
    workdir = make_workdir()
    try:
        inputs = []
        for i, upload in enumerate(files):
            path, _ = await save_upload(upload, workdir / f"{i}.pdf", (PDF,))
            inputs.append((path, upload.filename or f"file {i + 1}"))
        merged = await run_in_threadpool(merge_pdfs, inputs)
    finally:
        # Cleaned up here rather than in a response BackgroundTask, which
        # Starlette skips if the response is aborted.
        await run_in_threadpool(cleanup, workdir)
    return Response(
        merged,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment("merged.pdf")},
    )
