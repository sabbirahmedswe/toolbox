from pathlib import Path

import img2pdf
from PIL import Image, ImageOps

from app import config
from app.errors import ProcessingError

# EXIF orientations img2pdf can apply losslessly (via the page's /Rotate); the rest are mirrored.
_LOSSLESS_ORIENTATIONS = {1, 3, 6, 8}
# Orientations that turn the image a quarter, swapping width and height.
_QUARTER_TURNS = {5, 6, 7, 8}
_EXIF_ORIENTATION = 0x0112

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


def _embeddable_as_is(im: Image.Image, orientation: int) -> bool:
    """Whether img2pdf can embed the original file directly, without re-encoding."""
    return orientation in _LOSSLESS_ORIENTATIONS and im.mode in ("L", "RGB", "CMYK")


def prepare_image(path: Path, name: str, out_dir: Path) -> Path:
    """Validate an uploaded JPEG and return a file img2pdf can embed as one page.

    Files img2pdf can embed directly are returned as-is (no re-encoding);
    everything else is normalised with Pillow first.
    """
    # One pixel limit for both our check and Pillow's own decompression-bomb guard
    # (otherwise Pillow's ~89 MP default would apply first). Set per call so config is read at request time.
    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS
    try:
        # Only the JPEG decoder, so no other image plugin ever parses the upload.
        with Image.open(path, formats=["JPEG"]) as im:
            width, height = im.size
            if width * height > config.MAX_IMAGE_PIXELS:
                raise ProcessingError(
                    f'"{name}" is too large ({width} x {height} pixels). '
                    f"The maximum is {config.MAX_IMAGE_PIXELS // 1_000_000} megapixels."
                )
            im.load()  # decode fully so truncated or corrupt files are caught here
            orientation = im.getexif().get(_EXIF_ORIENTATION, 1)
            if _embeddable_as_is(im, orientation):
                return path

            options = {}
            if dpi := im.info.get("dpi"):
                options["dpi"] = (dpi[1], dpi[0]) if orientation in _QUARTER_TURNS else dpi
            if icc := im.info.get("icc_profile"):
                options["icc_profile"] = icc
            page = ImageOps.exif_transpose(im)
            # Greyscale and CMYK stay as they are, so an embedded ICC profile still matches. Pillow's JPEG decoder
            # gives no other modes today; this only guards against one it might add, which img2pdf can't embed.
            if page.mode not in ("L", "RGB", "CMYK"):
                page = page.convert("RGB")
        out = out_dir / f"{path.stem}-page.jpg"
        page.save(out, "JPEG", quality=95, **options)
        page.close()  # free the decoded pixels before the next image
        return out
    except ProcessingError:
        raise
    except Image.DecompressionBombError as e:
        raise ProcessingError(f'"{name}" is too large to convert.') from e
    except Exception as e:  # Pillow raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e


def jpg_to_pdf(inputs: list[tuple[Path, str]], workdir: Path) -> bytes:
    """Convert (path, display name) JPEGs to a PDF with one page per image, in order."""
    pages = [str(prepare_image(path, name, workdir)) for path, name in inputs]
    try:
        return img2pdf.convert(pages, layout_fun=_page_layout)
    except Exception as e:  # img2pdf has its own error types for unsupported variants
        raise ProcessingError("The images could not be converted to a PDF.") from e
