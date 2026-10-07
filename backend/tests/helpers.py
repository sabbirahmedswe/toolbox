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
