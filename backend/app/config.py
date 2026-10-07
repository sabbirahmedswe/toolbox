import os


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, default))


MAX_FILE_SIZE_MB = _int_env("MAX_FILE_SIZE_MB", 50)
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_FILES = _int_env("MAX_FILES", 20)
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
