import io

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
    # 600 dpi, above every preset's target (/printer is 300 dpi), so all levels downsample.
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=600, quality=95)
    return buf.getvalue()
