import os


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    return value


MAX_FILE_SIZE_MB = _int_env("MAX_FILE_SIZE_MB", 50)
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
# Cap on a whole request body, checked before the upload is parsed.
MAX_TOTAL_SIZE_MB = _int_env("MAX_TOTAL_SIZE_MB", 200)
MAX_TOTAL_SIZE = MAX_TOTAL_SIZE_MB * 1024 * 1024
MAX_FILES = _int_env("MAX_FILES", 20)
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
# Ghostscript binary and the limits applied to each run on untrusted input.
GS_BINARY = os.getenv("GS_BINARY", "gs")
GS_TIMEOUT_SECONDS = _int_env("GS_TIMEOUT_SECONDS", 120)
GS_MEMORY_LIMIT_MB = _int_env("GS_MEMORY_LIMIT_MB", 2048)
# Ghostscript is single-threaded, so by default allow one job per CPU.
MAX_CONCURRENT_COMPRESSIONS = _int_env("MAX_CONCURRENT_COMPRESSIONS", os.cpu_count() or 2)
