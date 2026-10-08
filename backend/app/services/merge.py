import io
from pathlib import Path

from pypdf import PdfWriter

from app.errors import ProcessingError
from app.services.pdf import RESOURCE_ERRORS, open_pdf


def merge_pdfs(inputs: list[tuple[Path, str]]) -> bytes:
    """Merge PDFs in the given order. `inputs` is a list of (path, display name)."""
    writer = PdfWriter()
    for path, name in inputs:
        reader = open_pdf(path, name)
        # open_pdf only checks the page tree; damage deeper in the file can surface while copying.
        try:
            writer.append(reader)
        except RESOURCE_ERRORS:
            raise
        except Exception as e:  # pypdf raises many exception types on malformed input
            raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e
    buf = io.BytesIO()
    try:
        writer.write(buf)
    except RESOURCE_ERRORS:
        raise
    except Exception as e:  # objects are read lazily, so damage can also show up here
        raise ProcessingError("The PDFs could not be merged. One of them may be damaged.") from e
    return buf.getvalue()
