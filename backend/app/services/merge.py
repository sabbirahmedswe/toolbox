import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.errors import ProcessingError


def open_pdf(path: Path, name: str) -> PdfReader:
    """Open a PDF, unlocking it if it only has an owner password."""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ProcessingError(f'"{name}" is password protected. Remove the password and try again.')
        # Touch the page tree so structural damage surfaces here, not mid-merge.
        len(reader.pages)
    except ProcessingError:
        raise
    except Exception as e:  # pypdf raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e
    return reader


def merge_pdfs(inputs: list[tuple[Path, str]]) -> bytes:
    """Merge PDFs in the given order. `inputs` is a list of (path, display name)."""
    writer = PdfWriter()
    for path, name in inputs:
        writer.append(open_pdf(path, name))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
