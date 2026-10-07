import logging
import math
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app import config
from app.errors import ProcessingError
from app.services.merge import open_pdf

logger = logging.getLogger(__name__)

Level = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class LevelSettings:
    preset: str  # Ghostscript -dPDFSETTINGS base
    dpi: int  # colour and grey images above this are downsampled to it
    qfactor: float  # JPEG quantisation: lower = better quality, bigger file (0.15 ~ q90, 0.76 ~ q50)

    def __post_init__(self):
        # Both end up in Ghostscript arguments, so keep them to plain numbers in a sane range.
        if not (isinstance(self.dpi, int) and 36 <= self.dpi <= 600):
            raise ValueError(f"dpi out of range: {self.dpi!r}")
        if not (isinstance(self.qfactor, (int, float)) and 0.05 <= self.qfactor <= 2.0):
            raise ValueError(f"qfactor out of range: {self.qfactor!r}")


# low = best quality, high = smallest file. Tuned on photos and 300 dpi scans: the stock presets alone
# went too far at /screen (72 dpi: small print unreadable) and too little at /printer.
LEVELS: dict[Level, LevelSettings] = {
    "low": LevelSettings("/printer", 200, 0.25),
    "medium": LevelSettings("/ebook", 150, 0.40),
    "high": LevelSettings("/screen", 120, 0.60),
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
    gs = check_compressible(src, name)
    _run_ghostscript(gs, src, dest, level, name, config.GS_TIMEOUT_SECONDS)
    return _smaller(src, dest)


def check_compressible(src: Path, name: str) -> str:
    """Checks made before any Ghostscript run; returns the Ghostscript path."""
    # Validate with pypdf first so damaged or password-protected files get a clear message.
    open_pdf(src, name)
    return ghostscript_path()


def estimate_size(gs: str, src: Path, tmp: Path, level: Level, name: str, deadline: float) -> int:
    """Return the size `compress_pdf` would hand back for `level`.

    `deadline` (a `time.monotonic()` value) is shared by every level of one estimate, so a whole
    estimate is held to GS_TIMEOUT_SECONDS, like one compression.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProcessingError(too_long(name))
    dest = tmp / f"estimate-{level}.pdf"
    try:
        _run_ghostscript(gs, src, dest, level, name, remaining)
        return _smaller(src, dest)[0].stat().st_size
    finally:
        dest.unlink(missing_ok=True)


def too_long(name: str) -> str:
    return f'"{name}" took too long to compress.'


def _smaller(src: Path, dest: Path) -> tuple[Path, bool]:
    # Ghostscript can make already-optimised files bigger; never hand back a larger file.
    if dest.stat().st_size < src.stat().st_size:
        return dest, True
    return src, False


def _image_args(settings: LevelSettings) -> list[str]:
    args = []
    for kind in ("Color", "Gray"):
        args += [
            f"-dDownsample{kind}Images=true",
            f"-d{kind}ImageResolution={settings.dpi}",
            # Bicubic, not the presets' averaging, which leaves photos blocky and text jagged.
            f"-d{kind}ImageDownsampleType=/Bicubic",
            # Only images over 1.2x the target: resampling one just above it costs quality for little gain.
            # Not the presets' 1.5, which skips common 200 dpi scans at the 150 dpi level.
            f"-d{kind}ImageDownsampleThreshold=1.2",
        ]
    # Colour images always as JPEG: left to choose, Ghostscript stores smooth photos losslessly, which
    # can make them bigger than the original. Grey is left to choose, because pdfwrite also writes
    # transparency masks as grey images, and JPEG would leave halos around transparent edges.
    args += ["-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode"]
    return args


def _run_ghostscript(gs: str, src: Path, dest: Path, level: Level, name: str, timeout: float) -> None:
    settings = LEVELS[level]
    # Fixed-point: Python's repr (e.g. 1e-05) isn't always valid PostScript.
    jpeg = f"<< /QFactor {settings.qfactor:.2f} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >>"
    gs_cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={settings.preset}",
        "-dSAFER",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        *_image_args(settings),
        f"-sOutputFile={dest}",
        # JPEG quality can only be set from PostScript. Fixed text (no user input), run after -dSAFER.
        "-c",
        f"<< /ColorImageDict {jpeg} /GrayImageDict {jpeg} /GrayACSImageDict {jpeg} >> setdistillerparams",
        "-f",
        str(src),
    ]
    limits = [str(config.GS_MEMORY_LIMIT_MB * 1024), str(math.ceil(timeout))]
    cmd = ["sh", "-c", _LIMITED_EXEC, "sh", *limits, *gs_cmd]
    try:
        # Output is discarded: a hostile file could otherwise make gs emit unbounded warnings.
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise ProcessingError(too_long(name)) from e
    except subprocess.CalledProcessError as e:
        logger.warning("Ghostscript failed on %r with exit code %s", name, e.returncode)
        raise ProcessingError(f'"{name}" could not be compressed. It may be damaged or too complex.') from e

    if not dest.exists() or dest.stat().st_size == 0:
        raise ProcessingError(f'"{name}" could not be compressed.')
