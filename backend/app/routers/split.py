from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app import config
from app.services.split import Mode, split_pdf
from app.utils.files import PDF, attachment, save_upload, workdir
from app.utils.limits import JobLimiter

router = APIRouter()

limiter = JobLimiter(lambda: config.MAX_CONCURRENT_SPLITS)


@router.post(
    "/split",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}, "application/zip": {}}}},
    summary="Split a PDF by page ranges or into fixed-size chunks",
)
async def split(
    file: UploadFile = File(..., description="The PDF to split"),
    mode: Mode = Form("ranges", description="ranges = the pages in `ranges`; every = chunks of `every` pages"),
    ranges: str = Form("", max_length=1000, description="Page ranges for mode=ranges, e.g. `1-3, 5, 8-10`"),
    every: int = Form(1, ge=1, description="Pages per PDF for mode=every"),
    merge: bool = Form(False, description="mode=ranges only: put all ranges in one PDF instead of one PDF each"),
):
    if merge and mode != "ranges":
        raise HTTPException(400, "merge can only be used with mode=ranges.")
    name = file.filename or "document.pdf"
    limiter.check()
    async with workdir() as tmp:
        src, _ = await save_upload(file, tmp / "in.pdf", (PDF,))
        async with limiter.slot():
            result = await run_in_threadpool(split_pdf, src, name, mode, ranges, every, merge)
    return Response(
        result.data,
        media_type=result.media_type,
        headers={"Content-Disposition": attachment(result.filename)},
    )
