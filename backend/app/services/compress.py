import logging
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from app import config
from app.errors import ProcessingError
from app.services.merge import open_pdf

logger = logging.getLogger(__name__)

Level = Literal["low", "medium", "high"]

# low = best quality, high = smallest file.
PRESETS: dict[str, str] = {
    "low": "/printer",
    "medium": "/ebook",
    "high": "/screen",
}

# Applies memory (KiB) and CPU-time (s) limits, then execs Ghostscript with the remaining args.
# Done in the shell rather than via preexec_fn, which isn't safe to use from a worker thread.
_LIMITED_EXEC = 'ulimit -v "$1" && ulimit -t "$2" && shift 2 && exec "$@"'


class GhostscriptMissing(Exception):
    """Raised when the Ghostscript binary can't be found."""


def ghostscript_path() -> str:
    path = shutil.which(config.GS_BINARY)
    if path is None:
        raise GhostscriptMissing(config.GS_BINARY)
    return path


def ghostscript_version() -> str | None:
    try:
        out = subprocess.run([ghostscript_path(), "--version"], capture_output=True, text=True, timeout=10)
    except (GhostscriptMissing, OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def compress_pdf(src: Path, dest: Path, level: Level, name: str) -> tuple[Path, bool]:
    """Compress `src` into `dest` with Ghostscript.

    Returns the path of the smaller of the two files and whether it is the compressed one.
    """
    # Validate with pypdf first so damaged or password-protected files get a clear message.
    open_pdf(src, name)
    gs = ghostscript_path()
    gs_cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={PRESETS[level]}",
        "-dSAFER",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={dest}",
        str(src),
    ]
    limits = [str(config.GS_MEMORY_LIMIT_MB * 1024), str(config.GS_TIMEOUT_SECONDS)]
    cmd = ["sh", "-c", _LIMITED_EXEC, "sh", *limits, *gs_cmd]
    try:
        # Output is discarded: a hostile file could otherwise make gs emit unbounded warnings.
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=config.GS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise ProcessingError(f'"{name}" took too long to compress.') from e
    except subprocess.CalledProcessError as e:
        logger.warning("Ghostscript failed on %r with exit code %s", name, e.returncode)
        raise ProcessingError(f'"{name}" could not be compressed. It may be damaged or too complex.') from e

    if not dest.exists() or dest.stat().st_size == 0:
        raise ProcessingError(f'"{name}" could not be compressed.')
    # Ghostscript can make already-optimised files bigger; never hand back a larger file.
    if dest.stat().st_size < src.stat().st_size:
        return dest, True
    return src, False
