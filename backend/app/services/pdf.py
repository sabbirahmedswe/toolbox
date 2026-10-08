from pathlib import Path

from pypdf import PdfReader

from app.errors import ProcessingError

# The server running out of memory, not a damaged file: let it propagate (500) rather than report it as a
# 400 "damaged" error, which would hide the problem. RecursionError isn't here: pypdf hits it on deeply nested
# objects in the upload, so it is a damaged file.
RESOURCE_ERRORS = (MemoryError,)


def open_pdf(path: Path, name: str) -> PdfReader:
    """Open a PDF, unlocking it if it only has an owner password."""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ProcessingError(f'"{name}" is password protected. Remove the password and try again.')
        # Touch the page tree so structural damage surfaces here, not mid-processing.
        len(reader.pages)
    except (ProcessingError, *RESOURCE_ERRORS):
        raise
    except Exception as e:  # pypdf raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be read.') from e
    return reader
