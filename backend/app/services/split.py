import io
import re
import zipfile
from pathlib import Path
from typing import Literal

from pypdf import PdfReader, PdfWriter

from app import config
from app.errors import ProcessingError
from app.services.output import FileResult, check_output_size
from app.services.pdf import RESOURCE_ERRORS, open_pdf
from app.utils.files import output_stem

Mode = Literal["ranges", "every"]

# A 1-based, inclusive page range.
PageRange = tuple[int, int]

_RANGE = re.compile(r"([0-9]+)(?:\s*-\s*([0-9]+))?")



def parse_ranges(text: str, page_count: int) -> list[PageRange]:
    """Parse `1-3, 5, 8-10` into ranges. Ranges must lie within the document and not overlap."""
    ranges = []
    for item in (part.strip() for part in text.split(",")):
        if not item:
            continue
        match = _RANGE.fullmatch(item)
        first = int(match[1]) if match else 0
        last = int(match[2]) if match and match[2] else first
        if first < 1 or first > last:
            raise ProcessingError(f'"{item}" is not a valid page range. Use page numbers like 1-3, 5, 8-10.')
        if last > page_count:
            raise ProcessingError(f'"{item}" is outside the document, which has {plural(page_count, "page")}.')
        ranges.append((first, last))
    if not ranges:
        raise ProcessingError("Enter at least one page range, like 1-3.")
    # Overlaps would let a request multiply the output past the page count.
    ordered = sorted(ranges)
    for (_, prev_last), (first, _) in zip(ordered, ordered[1:]):
        if first <= prev_last:
            raise ProcessingError(f"Page {first} is in more than one range. Ranges must not overlap.")
    return ranges


def fixed_ranges(every: int, page_count: int) -> list[PageRange]:
    """Consecutive ranges of `every` pages; the last one may be shorter."""
    return [(first, min(first + every - 1, page_count)) for first in range(1, page_count + 1, every)]


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def range_label(r: PageRange) -> str:
    return str(r[0]) if r[0] == r[1] else f"{r[0]}-{r[1]}"


def split_pdf(path: Path, name: str, mode: Mode, ranges: str, every: int, merge: bool) -> FileResult:
    """Split a PDF into one PDF per page range (zipped if more than one), or with `merge`, one PDF of all ranges."""
    reader = open_pdf(path, name)
    page_count = len(reader.pages)
    if page_count == 0:
        raise ProcessingError(f'"{name}" has no pages to split.')
    selected = parse_ranges(ranges, page_count) if mode == "ranges" else fixed_ranges(every, page_count)
    stem = output_stem(name)

    if not merge and len(selected) > config.MAX_SPLIT_PARTS:
        hint = "Use fewer ranges." if mode == "ranges" else "Use more pages per file."
        raise ProcessingError(
            f"This would create {len(selected)} PDFs, more than the limit of {config.MAX_SPLIT_PARTS}. {hint}"
        )

    if merge or len(selected) == 1:
        # Checked once written, but one PDF holds each shared font or image once, so it can't grow much past
        # the original. Only a ZIP, where every part has its own copies, can multiply it.
        data = write_pages(reader, selected, name)
        _check_output_size(len(data))
        filename = f"{stem}_split.pdf" if merge else f"{stem}_{range_label(selected[0])}.pdf"
        return FileResult(data, filename, "application/pdf")

    buf = io.BytesIO()
    total = 0
    # Stored, not deflated: PDF streams are already compressed, so deflating costs CPU for little gain.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for r in selected:
            data = write_pages(reader, [r], name)
            # Checked as each part is written, so memory stays bounded by the limit plus one part.
            total += len(data)
            _check_output_size(total)
            zf.writestr(f"{stem}_{range_label(r)}.pdf", data)
    return FileResult(buf.getbuffer(), f"{stem}_split.zip", "application/zip")


def write_pages(reader: PdfReader, ranges: list[PageRange], name: str) -> memoryview:
    writer = PdfWriter()
    buf = io.BytesIO()
    # Objects are read lazily, so damage can surface while copying or writing.
    try:
        for first, last in ranges:
            for i in range(first - 1, last):
                writer.add_page(reader.pages[i])
        writer.write(buf)
    except RESOURCE_ERRORS:
        raise
    except Exception as e:  # pypdf raises many exception types on malformed input
        raise ProcessingError(f'"{name}" appears to be damaged and could not be split.') from e
    return buf.getbuffer()


def _check_output_size(size: int) -> None:
    check_output_size(size, config.MAX_SPLIT_OUTPUT_MB, "The split PDFs", "Try fewer or larger ranges.")
