import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.errors import ProcessingError
from app.middleware import RequestSizeLimitMiddleware
from app.routers import compress, images, merge, pdf_to_jpg, split
from app.services.ghostscript import ghostscript_version

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_: FastAPI):
    version = ghostscript_version()
    if version:
        # Ghostscript has a history of -dSAFER bypasses; keep it patched.
        logger.info("Using Ghostscript %s (%s); keep it up to date.", version, config.GS_BINARY)
    else:
        logger.warning("Ghostscript (%s) not found: PDF compression and PDF to JPG are unavailable.", config.GS_BINARY)
    yield


app = FastAPI(title="Toolbox", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestSizeLimitMiddleware)
# Added last so it's outermost: error responses from the size limit still get CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Original-Size", "X-Compressed-Size"],
)


@app.exception_handler(ProcessingError)
async def processing_error_handler(_: Request, exc: ProcessingError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(merge.router, prefix="/api", tags=["merge"])
app.include_router(compress.router, prefix="/api", tags=["compress"])
app.include_router(images.router, prefix="/api", tags=["images"])
app.include_router(split.router, prefix="/api", tags=["split"])
app.include_router(pdf_to_jpg.router, prefix="/api", tags=["pdf-to-jpg"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
