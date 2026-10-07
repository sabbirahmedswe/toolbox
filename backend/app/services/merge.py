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
        reader = open_pdf(path, name)
        # open_pdf only checks the page tree; damage deeper in the file can surface while copying.
        try:
            writer.append(reader)
        except Exception as e:  # pypdf raises many exception types on malformed input
            raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e
    buf = io.BytesIO()
    try:
        writer.write(buf)
    except Exception as e:  # objects are read lazily, so damage can also show up here
        raise ProcessingError("The PDFs could not be merged. One of them may be damaged.") from e
    return buf.getvalue()
