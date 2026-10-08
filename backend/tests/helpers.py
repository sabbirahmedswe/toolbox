import io
import os

from pypdf import PdfWriter


def make_pdf(widths: list[int], height: int = 100, password: str | None = None) -> bytes:
    """Build a PDF with one blank page per width, so page order is checkable via mediabox width."""
    writer = PdfWriter()
    for w in widths:
        writer.add_blank_page(width=w, height=height)
    if password:
        writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_image_pdf(pages: int = 1, size: int = 1600) -> bytes:
    """Build a PDF of high-resolution noisy photos: large, and shrinkable by Ghostscript."""
    from PIL import Image

    images = [Image.effect_noise((size, size), 64).convert("RGB") for _ in range(pages)]
    buf = io.BytesIO()
    # 600 dpi: well over every level's target (200 dpi at most), so all levels downsample.
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=600, quality=95)
    return buf.getvalue()


def make_image(
    fmt: str = "JPEG",
    size: tuple[int, int] = (96, 48),
    mode: str = "RGB",
    color=(200, 30, 30),
    orientation: int | None = None,
    dpi: tuple[int, int] | None = None,
    **save_options,
) -> bytes:
    """Build a solid-colour JPEG or PNG, optionally with an EXIF orientation and DPI."""
    from PIL import Image

    im = Image.new(mode, size, color)
    options = dict(save_options)
    if orientation is not None:
        exif = Image.Exif()
        exif[0x0112] = orientation
        options["exif"] = exif
    if dpi is not None:
        options["dpi"] = dpi
    buf = io.BytesIO()
    im.save(buf, fmt, **options)
    return buf.getvalue()


def make_jpeg_pdf(jpegs: list[bytes], soft_mask: bool = False, padding: int = 0) -> bytes:
    """Build a PDF with one page per JPEG, embedded as is (optionally with a soft mask) at 72 dpi.

    `padding` adds an unused stream of that many bytes, which Ghostscript drops, so the file compresses.
    """
    from PIL import Image
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    for i, data in enumerate(jpegs):
        width, height = Image.open(io.BytesIO(data)).size
        page = writer.add_blank_page(width=width, height=height)
        image = DecodedStreamObject()
        image.set_data(data)
        image.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(width),
                NameObject("/Height"): NumberObject(height),
                NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                NameObject("/BitsPerComponent"): NumberObject(8),
                NameObject("/Filter"): NameObject("/DCTDecode"),
            }
        )
        if soft_mask:
            # Mostly opaque with a transparent corner, so Ghostscript keeps the mask.
            alpha = Image.new("L", (width, height), 255)
            alpha.paste(0, (0, 0, width // 4, height // 4))
            mask = DecodedStreamObject()
            mask.set_data(alpha.tobytes())
            mask.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(width),
                    NameObject("/Height"): NumberObject(height),
                    NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            mask = mask.flate_encode()
            image[NameObject("/SMask")] = writer._add_object(mask)
        name = f"/Im{i}"
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/XObject"): DictionaryObject({NameObject(name): writer._add_object(image)})}
        )
        content = DecodedStreamObject()
        content.set_data(f"q {width} 0 0 {height} 0 0 cm {name} Do Q".encode())
        page[NameObject("/Contents")] = writer._add_object(content)
    if padding:
        unused = DecodedStreamObject()
        unused.set_data(os.urandom(padding))
        writer._add_object(unused)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_text_image(seed: int, size: tuple[int, int] = (1240, 1754)):
    """A white page of random black 'text' lines: different seeds give pages that look alike from afar."""
    import random

    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    im = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(im)
    for y in range(120, size[1] - 120, 36):
        x = 100
        while x < size[0] - 160:
            word = rng.randint(30, 120)
            draw.rectangle((x, y, x + word, y + 14), fill="black")
            x += word + rng.randint(12, 24)
    return im
