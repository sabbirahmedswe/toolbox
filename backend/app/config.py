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
# Image -> PDF: largest image accepted (width x height), a guard against decompression bombs.
MAX_IMAGE_PIXELS = _int_env("MAX_IMAGE_PIXELS", 100_000_000)
# Each job may hold a few full-size decoded copies of a large image, so keep this small.
MAX_CONCURRENT_IMAGE_JOBS = _int_env("MAX_CONCURRENT_IMAGE_JOBS", min(os.cpu_count() or 2, 4))
# Split: most PDFs one split may produce, and the largest total size of those PDFs. Each part gets its own
# copy of the fonts and images its pages share, so a split can be much larger than the original.
MAX_SPLIT_PARTS = _int_env("MAX_SPLIT_PARTS", 500)
MAX_SPLIT_OUTPUT_MB = _int_env("MAX_SPLIT_OUTPUT_MB", 200)
MAX_CONCURRENT_SPLITS = _int_env("MAX_CONCURRENT_SPLITS", min(os.cpu_count() or 2, 4))
# PDF to JPG: most pages one conversion may render, the largest total size of the images, and jobs at once.
# Each page's image is also limited to MAX_IMAGE_PIXELS, and the whole conversion to GS_TIMEOUT_SECONDS.
MAX_PDF_TO_JPG_PAGES = _int_env("MAX_PDF_TO_JPG_PAGES", 500)
MAX_PDF_TO_JPG_OUTPUT_MB = _int_env("MAX_PDF_TO_JPG_OUTPUT_MB", 200)
MAX_CONCURRENT_PDF_TO_JPG = _int_env("MAX_CONCURRENT_PDF_TO_JPG", min(os.cpu_count() or 2, 4))
