import io
import logging
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, IndirectObject, NameObject, NumberObject, StreamObject

from app import config
from app.errors import ProcessingError
from app.services.ghostscript import ghostscript_path, run_limited
from app.services.pdf import RESOURCE_ERRORS, open_pdf

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

def compress_pdf(src: Path, dest: Path, level: Level, name: str) -> tuple[Path, bool]:
    """Compress `src` into `dest` with Ghostscript.

    Returns the path of the smaller of the two files and whether it is the compressed one.
    """
    # Validate with pypdf first so damaged or password-protected files get a clear message.
    original = open_pdf(src, name)
    _run_ghostscript(ghostscript_path(), src, dest, level, name)
    try:
        _restore_original_jpegs(original, dest)
    except RESOURCE_ERRORS:
        raise
    except Exception:  # an optional saving: on any failure keep Ghostscript's output as it is
        logger.warning("Could not restore original JPEGs in %r", name, exc_info=True)
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


def _run_ghostscript(gs: str, src: Path, dest: Path, level: Level, name: str) -> None:
    settings = LEVELS[level]
    # Fixed-point: Python's repr (e.g. 1e-05) isn't always valid PostScript.
    jpeg = f"<< /QFactor {settings.qfactor:.2f} /Blend 1 /HSamples [2 1 1 2] /VSamples [2 1 1 2] >>"
    gs_cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={settings.preset}",
        # /ebook and /screen convert every colour to sRGB. On files with ICC-based colours that rewrites every
        # page's content (tripling it on one report) and is about 3x slower, so the result is often bigger.
        "-sColorConversionStrategy=LeaveColorUnchanged",
        # /screen turns pages whose text mostly runs sideways, which put half of a two-page spread on its side.
        "-dAutoRotatePages=/None",
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
    try:
        run_limited(gs_cmd, config.GS_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        raise ProcessingError(f'"{name}" took too long to compress.') from e
    except subprocess.CalledProcessError as e:
        logger.warning("Ghostscript failed on %r with exit code %s", name, e.returncode)
        raise ProcessingError(f'"{name}" could not be compressed. It may be damaged or too complex.') from e

    if not dest.exists() or dest.stat().st_size == 0:
        raise ProcessingError(f'"{name}" could not be compressed.')


# Ghostscript re-encodes every JPEG it resamples, and some it doesn't, notably any with a soft mask
# (transparency). When the original was saved at a lower quality than the level's, the copy can be bigger even
# at a lower resolution, so the original is put back: smaller and sharper.
# Most JPEGs decoded per file (each at reduced scale) to find those copies, which bounds the time this pass takes.
_MAX_JPEG_DECODES = 400
# Every copy is checked against every original, so files with more JPEGs than this skip the pass.
_MAX_JPEGS = 2000
# Two images count as the same when, compared at about 1/8 of the copy's size, their mean difference is at most
# _MAX_MEAN_DIFF (0-255) and at most _MAX_CHANGED_SHARE of pixels differ by more than _CHANGED_PIXEL_DIFF.
# On a real report, copies (even resampled ones) scored at most 4.1 and 0.7%, different images at least 27 and 20%.
# The share test also catches different pages of text, which can be close on average.
_MAX_MEAN_DIFF = 8.0
_CHANGED_PIXEL_DIFF = 40
_MAX_CHANGED_SHARE = 0.02
_MIN_COMPARE_SIZE = 16


@dataclass(frozen=True)
class _Jpeg:
    data: bytes  # the raw, still-encoded stream
    width: int
    height: int


def _images(pages) -> Iterator[StreamObject]:
    """Each image XObject on `pages` once, including those inside form XObjects."""
    seen: set[int] = set()

    def walk(resources) -> Iterator[StreamObject]:
        resources = resources.get_object() if resources is not None else None
        xobjects = resources.get("/XObject") if isinstance(resources, DictionaryObject) else None
        xobjects = xobjects.get_object() if xobjects is not None else None
        if not isinstance(xobjects, DictionaryObject):
            return
        for ref in xobjects.values():
            obj = ref.get_object()
            # Keyed on the object rather than the reference, which direct objects don't have.
            if id(obj) in seen or not isinstance(obj, StreamObject):
                continue
            seen.add(id(obj))
            if obj.get("/Subtype") == "/Image":
                yield obj
            elif obj.get("/Subtype") == "/Form":
                yield from walk(obj.get("/Resources"))

    for page in pages:
        yield from walk(page.get("/Resources"))


def _plain_jpeg(image: StreamObject) -> _Jpeg | None:
    """An 8-bit image stored as nothing but a JPEG, or None for anything else."""
    if image.get("/Filter") != "/DCTDecode" or image.get("/BitsPerComponent") != 8:
        return None
    if "/Decode" in image or "/DecodeParms" in image or image.get("/ImageMask"):
        return None
    width, height = image.get("/Width"), image.get("/Height")
    if not (isinstance(width, int) and isinstance(height, int) and 0 < width * height <= config.MAX_IMAGE_PIXELS):
        return None
    return _Jpeg(image._data, width, height)


def _same_shape(copy: _Jpeg, original: _Jpeg) -> bool:
    """`original` has the copy's aspect ratio (to within a pixel or so) and at least its resolution."""
    if original.width < copy.width or original.height < copy.height:
        return False
    return abs(copy.width * original.height - copy.height * original.width) <= original.width + original.height


def _decode_small(jpeg: _Jpeg, size: tuple[int, int]) -> tuple[str, Image.Image] | None:
    """`jpeg`'s mode, and the image decoded at reduced scale (cheap for JPEG) and resized to `size` as RGB."""
    try:
        with Image.open(io.BytesIO(jpeg.data), formats=["JPEG"]) as im:
            # The stream's own size must match the PDF's, and no CMYK: Adobe's inverted CMYK JPEGs need the
            # PDF's /Decode to display right, so leave them alone.
            if im.size != (jpeg.width, jpeg.height) or im.mode not in ("L", "RGB"):
                return None
            mode = im.mode
            im.draft(mode, size)
            return mode, im.convert("RGB").resize(size, Image.Resampling.BOX)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def _restore_original_jpegs(original: PdfReader, dest: Path) -> None:
    """Put back original JPEGs that are smaller than Ghostscript's re-encoded copies of them in `dest`."""
    originals = {j.data: j for image in _images(original.pages) if (j := _plain_jpeg(image)) is not None}
    if not 0 < len(originals) <= _MAX_JPEGS:
        return
    writer = PdfWriter(clone_from=dest)
    copies = [(image, j) for image in _images(writer.pages) if (j := _plain_jpeg(image)) is not None]
    if len(copies) > _MAX_JPEGS:
        return

    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    decoded: dict[tuple[bytes, tuple[int, int]], tuple[str, Image.Image] | None] = {}

    def small(jpeg: _Jpeg, size: tuple[int, int]) -> tuple[str, Image.Image] | None:
        key = (jpeg.data, size)
        if key not in decoded:
            decoded[key] = _decode_small(jpeg, size) if len(decoded) < _MAX_JPEG_DECODES else None
        return decoded[key]

    def same_image(a: tuple[str, Image.Image], b: tuple[str, Image.Image]) -> bool:
        # Same mode too: grey JPEG data under the copy's RGB colour space (or the reverse) wouldn't display.
        (a_mode, a), (b_mode, b) = a, b
        if a_mode != b_mode:
            return False
        diff = ImageChops.difference(a, b).convert("L")
        hist = diff.histogram()
        pixels = a.width * a.height
        changed = sum(hist[_CHANGED_PIXEL_DIFF + 1 :])
        return ImageStat.Stat(diff).mean[0] <= _MAX_MEAN_DIFF and changed <= pixels * _MAX_CHANGED_SHARE

    restored = 0
    for image, copy in copies:
        # A soft mask with /Matte must match its image's size, so those copies can only take a same-size original.
        smask = image.get("/SMask")
        fixed_size = isinstance(smask, StreamObject | IndirectObject) and "/Matte" in smask.get_object()
        candidates = [
            o
            for o in originals.values()
            if len(o.data) < len(copy.data)
            and _same_shape(copy, o)
            and not (fixed_size and (o.width, o.height) != (copy.width, copy.height))
        ]
        if not candidates:
            continue
        size = (max(copy.width // 8, _MIN_COMPARE_SIZE), max(copy.height // 8, _MIN_COMPARE_SIZE))
        if (copy_small := small(copy, size)) is None:
            continue
        matches = [o for o in candidates if (s := small(o, size)) is not None and same_image(copy_small, s)]
        if matches:
            best = min(matches, key=lambda o: len(o.data))
            image._data = best.data  # pypdf writes /Length from the data
            # Otherwise a soft mask may differ in size from its image, so it can stay at the copy's resolution.
            image[NameObject("/Width")] = NumberObject(best.width)
            image[NameObject("/Height")] = NumberObject(best.height)
            restored += 1

    if restored:
        out = dest.with_name(f"{dest.stem}.restored.pdf")
        with out.open("wb") as f:
            writer.write(f)
        # Rewriting with pypdf can cost more than a few small images save.
        if out.stat().st_size < dest.stat().st_size:
            out.replace(dest)
        else:
            out.unlink()
