from dataclasses import dataclass

from app.errors import ProcessingError

MB = 1024 * 1024


@dataclass
class FileResult:
    """A file for the router to send back as a download."""

    # May be a view of the output buffer rather than a copy, so a large result is held in memory only once.
    data: bytes | memoryview
    filename: str
    media_type: str


def check_output_size(size: int, limit_mb: int, what: str, hint: str) -> None:
    """Fail once `size` bytes of output passes `limit_mb`. `what` is the output's name, e.g. "The split PDFs"."""
    if size > limit_mb * MB:
        raise ProcessingError(f"{what} would be larger than the {limit_mb} MB limit. {hint}")
