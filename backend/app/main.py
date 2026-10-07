from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.errors import ProcessingError
from app.middleware import RequestSizeLimitMiddleware
from app.routers import merge

app = FastAPI(title="iLovePDF Tool", version="0.1.0")

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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
