import io
import logging
import math
import subprocess
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PageObject

from app import config
from app.errors import ProcessingError
from app.services.ghostscript import ghostscript_path, stream_limited
from app.services.output import FileResult, check_output_size
from app.services.pdf import RESOURCE_ERRORS, open_pdf
from app.utils.files import output_stem

logger = logging.getLogger(__name__)

Quality = Literal["normal", "high"]


@dataclass(frozen=True)
class QualitySettings:
    dpi: int
    jpeg_quality: int  # 0-100

    def __post_init__(self):
        # Both end up in Ghostscript arguments, so keep them to plain numbers in a sane range.
        if not (isinstance(self.dpi, int) and 36 <= self.dpi <= 600):
            raise ValueError(f"dpi out of range: {self.dpi!r}")
        if not (isinstance(self.jpeg_quality, int) and 1 <= self.jpeg_quality <= 100):
            raise ValueError(f"jpeg_quality out of range: {self.jpeg_quality!r}")


QUALITIES: dict[Quality, QualitySettings] = {
    "normal": QualitySettings(150, 85),
    "high": QualitySettings(300, 92),
}


def pdf_to_jpg(src: Path, name: str, quality: Quality) -> FileResult:
    """Render each page of `src` as a JPEG: one image for a one-page PDF, otherwise a ZIP of them."""
    reader = open_pdf(src, name)
    page_count = len(reader.pages)
    if page_count == 0:
        raise ProcessingError(f'"{name}" has no pages to convert.')
    if page_count > config.MAX_PDF_TO_JPG_PAGES:
        raise ProcessingError(
            f'"{name}" has {page_count} pages, more than the limit of {config.MAX_PDF_TO_JPG_PAGES}. '
            "Split it into smaller PDFs first."
        )
    settings = QUALITIES[quality]
    for number, page in enumerate(reader.pages, start=1):
        _check_page_size(page, number, settings.dpi, name)

    stem = output_stem(name)
    digits = len(str(page_count))
    buf = io.BytesIO()
    single: bytes | None = None
    # Stored, not deflated: JPEGs are already compressed.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for number, image in enumerate(_render(src, page_count, settings, name), start=1):
            if page_count == 1:
                single = image
            else:
                zf.writestr(f"{stem}_{number:0{digits}}.jpg", image)
    if single is not None:
        return FileResult(single, f"{stem}.jpg", "image/jpeg")
    return FileResult(buf.getbuffer(), f"{stem}_jpg.zip", "application/zip")


def _check_page_size(page: PageObject, number: int, dpi: int, name: str) -> None:
    """Reject pages whose image would be over MAX_IMAGE_PIXELS, before Ghostscript allocates it."""
    try:
        scale = float(page.user_unit) * dpi / 72
        # Ghostscript renders the crop box; the media box is counted too in case it falls back to that.
        pixels = max(abs(box.width * box.height) for box in (page.cropbox, page.mediabox)) * scale * scale
    except RESOURCE_ERRORS:
        raise
    except Exception as e:  # pypdf raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e
    # Not finite: a page size like 1e400 in the file. NaN would pass the comparison below.
    if not math.isfinite(pixels) or pixels > config.MAX_IMAGE_PIXELS:
        raise ProcessingError(f'Page {number} of "{name}" is too large to convert to an image.')


def _render(src: Path, page_count: int, settings: QualitySettings, name: str) -> Iterator[bytes]:
    """Each page's JPEG, in order, as Ghostscript renders it.

    Read from a pipe, so nothing is written to disk, and the output limit stops Ghostscript as soon as it's passed.
    """
    gs_cmd = [
        ghostscript_path(),
        "-sDEVICE=jpeg",
        f"-r{settings.dpi}",
        f"-dJPEGQ={settings.jpeg_quality}",
        # Smooth the edges of text and line art, as PDF viewers do.
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        # The visible page, as viewers show it, rather than the whole media box.
        "-dUseCropBox",
        "-dSAFER",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        # Only the pages pypdf counted and checked, in case Ghostscript reads a damaged file as having more.
        "-dFirstPage=1",
        f"-dLastPage={page_count}",
        # The images go to stdout, one after another; messages go to stderr so they can't mix in.
        "-sOutputFile=-",
        "-sstdout=%stderr",
        "-f",
        str(src),
    ]
    count = 0
    try:
        with stream_limited(gs_cmd, config.GS_TIMEOUT_SECONDS) as chunks:
            for image in _split_jpegs(_within_limit(chunks), name):
                count += 1
                if count > page_count:
                    break
                yield image
    except subprocess.TimeoutExpired as e:
        raise ProcessingError(f'"{name}" took too long to convert.') from e
    except subprocess.CalledProcessError as e:
        logger.warning("Ghostscript failed on %r with exit code %s", name, e.returncode)
        raise ProcessingError(f'"{name}" could not be converted. It may be damaged or too complex.') from e
    # Ghostscript can skip pages it can't read, or see a different number of pages than pypdf did.
    if count != page_count:
        logger.warning("Ghostscript rendered %s of %s pages of %r", count, page_count, name)
        raise ProcessingError(f'"{name}" could not be converted. It may be damaged.')


def _within_limit(chunks: Iterable[bytes]) -> Iterator[bytes]:
    """Pass `chunks` on, failing as soon as they add up to more than the output limit."""
    total = 0
    for chunk in chunks:
        total += len(chunk)
        check_output_size(
            total,
            config.MAX_PDF_TO_JPG_OUTPUT_MB,
            "The images",
            "Try normal quality, or split the PDF into smaller files first.",
        )
        yield chunk


def _split_jpegs(chunks: Iterable[bytes], name: str) -> Iterator[bytes]:
    """Split a stream of JPEGs written one after another into the separate images."""
    splitter = _JpegSplitter()
    try:
        for chunk in chunks:
            yield from splitter.feed(chunk)
        splitter.finish()
    except ValueError as e:
        logger.warning("Unexpected Ghostscript output for %r: %s", name, e)
        raise ProcessingError(f'"{name}" could not be converted.') from e


class _JpegSplitter:
    """Finds where each JPEG ends by walking its marker segments, so images can be passed on as they complete.

    Holds at most one image (plus one chunk) in memory.
    """

    def __init__(self):
        self._buf = bytearray()
        self._pos = 0  # where parsing resumes in _buf; 0 = at the start of an image
        self._in_scan = False  # in entropy-coded data, where the next marker can only be found by scanning

    def feed(self, data: bytes) -> list[bytes]:
        """Add data; returns the images it completed."""
        self._buf += data
        images = []
        while (end := self._image_end()) is not None:
            images.append(bytes(self._buf[:end]))
            del self._buf[:end]
            self._pos, self._in_scan = 0, False
        return images

    def finish(self) -> None:
        if self._buf:
            raise ValueError(f"{len(self._buf)} bytes left after the last complete image")

    def _image_end(self) -> int | None:
        """The end of the first image in the buffer, or None until it has all arrived."""
        buf = self._buf
        if self._pos == 0:
            if len(buf) < 2:
                return None
            if buf[:2] != b"\xff\xd8":
                raise ValueError("data does not start with a JPEG start-of-image marker")
            self._pos = 2
        while True:
            if self._in_scan:
                # The scan ends at the first 0xFF that isn't a stuffed 0xFF00 or a restart marker (0xFFD0-D7).
                i = buf.find(b"\xff", self._pos)
                while i != -1 and i + 1 < len(buf) and (buf[i + 1] == 0 or 0xD0 <= buf[i + 1] <= 0xD7):
                    i = buf.find(b"\xff", i + 2)
                if i == -1 or i + 1 == len(buf):
                    # Resume at the unmatched 0xFF, if any, once its next byte arrives.
                    self._pos = len(buf) if i == -1 else i
                    return None
                self._pos, self._in_scan = i, False
            if len(buf) < self._pos + 2:
                return None
            if buf[self._pos] != 0xFF:
                raise ValueError(f"expected a marker at byte {self._pos}")
            marker = buf[self._pos + 1]
            if marker == 0xFF:  # fill byte before a marker
                self._pos += 1
            elif marker == 0xD9:  # end of image
                return self._pos + 2
            elif marker == 0x01 or 0xD0 <= marker <= 0xD7:  # markers without a length
                self._pos += 2
            else:
                if len(buf) < self._pos + 4:
                    return None
                length = int.from_bytes(buf[self._pos + 2 : self._pos + 4], "big")
                if length < 2:
                    raise ValueError(f"invalid segment length at byte {self._pos}")
                if len(buf) < self._pos + 2 + length:
                    return None
                self._pos += 2 + length
                self._in_scan = marker == 0xDA  # start of scan: entropy-coded data follows its header
