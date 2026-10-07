from pathlib import Path

import img2pdf
from PIL import Image, ImageMath, ImageOps

from app import config
from app.errors import ProcessingError
from app.utils.files import JPEG, PNG

# EXIF orientations img2pdf can apply losslessly (via the page's /Rotate); the rest are mirrored.
_LOSSLESS_ORIENTATIONS = {1, 3, 6, 8}
# Orientations that turn the image a quarter, swapping width and height.
_QUARTER_TURNS = {5, 6, 7, 8}
_EXIF_ORIENTATION = 0x0112
# Pillow decoders allowed for each detected kind, so no other image plugin ever parses the upload.
_FORMATS = {JPEG: ["JPEG"], PNG: ["PNG"]}

# Page sizing: honour the image's DPI when it's plausible, otherwise assume 96 dpi.
DEFAULT_DPI = 96
MIN_DPI, MAX_DPI = 50, 1200
# PDF viewers handle pages up to 200 x 200 inches; the spec's minimum page side is 3 pt.
MAX_PAGE_PT, MIN_PAGE_PT = 14400, 3


def _page_layout(width_px: int, height_px: int, dpi: tuple[float, float]) -> tuple[float, float, float, float]:
    """img2pdf layout: one page exactly the size of the image (points)."""
    dpi_x, dpi_y = dpi
    if not (MIN_DPI <= dpi_x <= MAX_DPI and MIN_DPI <= dpi_y <= MAX_DPI):
        dpi_x = dpi_y = DEFAULT_DPI
    width, height = width_px * 72 / dpi_x, height_px * 72 / dpi_y
    scale = min(1.0, MAX_PAGE_PT / max(width, height))
    width, height = max(width * scale, MIN_PAGE_PT), max(height * scale, MIN_PAGE_PT)
    return width, height, width, height


def _has_transparency(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info


def _is_grey(im: Image.Image) -> bool:
    return im.mode in ("1", "L", "LA") or im.mode.startswith("I")


def _flatten(im: Image.Image) -> Image.Image:
    """Return an image img2pdf embeds without a soft mask: transparency is composited onto white.

    Greyscale stays greyscale and CMYK stays CMYK, so an embedded ICC profile still matches.
    """
    if im.mode.startswith("I"):  # 16/32-bit greyscale: scale down rather than clip
        wide = im.convert("I")
        grey = wide.point(lambda v: v / 256).convert("L")
        if "transparency" not in im.info:
            return grey
        key = im.info["transparency"]
        alpha = ImageMath.lambda_eval(lambda a: (a["x"] != key) * 255, x=wide).convert("L")
        background = Image.new("L", im.size, 255)
        background.paste(grey, mask=alpha)
        return background
    if _has_transparency(im):
        mode, alpha_mode = ("L", "LA") if _is_grey(im) else ("RGB", "RGBA")
        with_alpha = im.convert(alpha_mode)
        background = Image.new(mode, im.size, 255 if mode == "L" else (255, 255, 255))
        background.paste(with_alpha.convert(mode), mask=with_alpha.getchannel("A"))
        return background
    if im.mode in ("RGB", "L", "CMYK"):
        return im
    return im.convert("L" if _is_grey(im) else "RGB")


def _embeddable_as_is(im: Image.Image, kind: str, orientation: int) -> bool:
    """Whether img2pdf can embed the original file directly, without re-encoding."""
    if kind == JPEG:
        return orientation in _LOSSLESS_ORIENTATIONS and im.mode in ("L", "RGB", "CMYK")
    return orientation == 1 and im.mode in ("L", "RGB") and not _has_transparency(im)


def prepare_image(path: Path, kind: str, name: str, out_dir: Path) -> Path:
    """Validate an uploaded image and return a file img2pdf can embed as one page.

    Files img2pdf can embed directly are returned as-is (no re-encoding);
    everything else is normalised with Pillow first.
    """
    # One pixel limit for both our check and Pillow's own decompression-bomb guard
    # (otherwise Pillow's ~89 MP default would apply first). Set per call so config is read at request time.
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    try:
        with Image.open(path, formats=_FORMATS[kind]) as im:
            width, height = im.size
            if width * height > config.MAX_IMAGE_PIXELS:
                raise ProcessingError(
                    f'"{name}" is too large ({width} x {height} pixels). '
                    f"The maximum is {config.MAX_IMAGE_PIXELS // 1_000_000} megapixels."
                )
            im.load()  # decode fully so truncated or corrupt files are caught here
            orientation = im.getexif().get(_EXIF_ORIENTATION, 1)
            if _embeddable_as_is(im, kind, orientation):
                return path

            options = {}
            if dpi := im.info.get("dpi"):
                options["dpi"] = (dpi[1], dpi[0]) if orientation in _QUARTER_TURNS else dpi
            if icc := im.info.get("icc_profile"):
                options["icc_profile"] = icc
            page = _flatten(ImageOps.exif_transpose(im))
        out = out_dir / f"{path.stem}-page.{'jpg' if kind == JPEG else 'png'}"
        if kind == JPEG:
            page.save(out, "JPEG", quality=95, **options)
        else:
            page.save(out, "PNG", **options)
        page.close()  # free the decoded pixels before the next image
        return out
    except ProcessingError:
        raise
    except Image.DecompressionBombError as e:
        raise ProcessingError(f'"{name}" is too large to convert.') from e
    except Exception as e:  # Pillow raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e


def images_to_pdf(inputs: list[tuple[Path, str, str]], workdir: Path) -> bytes:
    """Convert (path, kind, display name) images to a PDF with one page per image, in order."""
    pages = [str(prepare_image(path, kind, name, workdir)) for path, kind, name in inputs]
    try:
        return img2pdf.convert(pages, layout_fun=_page_layout)
    except Exception as e:  # img2pdf has its own error types for unsupported variants
        raise ProcessingError("The images could not be converted to a PDF.") from e
