from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app import config

_BODY_METHODS = {"POST", "PUT", "PATCH"}


class RequestSizeLimitMiddleware:
    """Reject oversized uploads before the multipart body is read and spooled to disk.

    Requests with a body must declare Content-Length (browsers always do for
    FormData), so the limit can be enforced up front.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _BODY_METHODS:
            headers = dict(scope["headers"])
            raw = headers.get(b"content-length")
            if raw is None or not raw.isdigit():
                response = JSONResponse({"detail": "Content-Length header is required."}, status_code=411)
                return await response(scope, receive, send)
            if int(raw) > config.MAX_TOTAL_SIZE:
                response = JSONResponse(
                    {"detail": f"Upload is larger than the {config.MAX_TOTAL_SIZE_MB} MB total limit."},
                    status_code=413,
                )
                return await response(scope, receive, send)
        await self.app(scope, receive, send)
