from fastapi import APIRouter, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.services.merge import merge_pdfs
from app.utils.files import PDF, attachment, check_file_count, save_uploads, workdir

router = APIRouter()


@router.post(
    "/merge",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Merge PDFs in upload order",
)
async def merge(files: list[UploadFile] = File(..., description="Two or more PDF files")):
    check_file_count(files, minimum=2)
    async with workdir() as tmp:
        saved = await save_uploads(files, tmp, (PDF,))
        merged = await run_in_threadpool(merge_pdfs, [(path, name) for path, _, name in saved])
    return Response(
        merged,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment("merged.pdf")},
    )
