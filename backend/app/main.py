from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config

app = FastAPI(title="iLovePDF Tool", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Original-Size", "X-Compressed-Size"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
