import io
import zipfile

import pytest
from pypdf import PdfReader

from app import config
from app.utils.files import output_stem
from tests.helpers import make_image_pdf, make_pdf

# Page widths 101..110, so each page is identifiable by its mediabox width.
TEN_PAGES = list(range(101, 111))


def split(client, data: bytes, name: str = "report.pdf", **fields):
    return client.post("/api/split", files={"file": (name, data, "application/pdf")}, data=fields)


def page_widths(data: bytes) -> list[int]:
    return [int(p.mediabox.width) for p in PdfReader(io.BytesIO(data)).pages]


def zip_parts(data: bytes) -> dict[str, list[int]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {n: page_widths(zf.read(n)) for n in zf.namelist()}


def test_split_ranges_into_zip(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="1-3, 5,8 - 10")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert 'filename="report_split.zip"' in res.headers["content-disposition"]
    assert zip_parts(res.content) == {
        "report_1-3.pdf": [101, 102, 103],
        "report_5.pdf": [105],
        "report_8-10.pdf": [108, 109, 110],
    }


def test_split_keeps_range_order(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="9-10,1")
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.namelist() == ["report_9-10.pdf", "report_1.pdf"]


def test_split_single_range_returns_pdf(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="2-4")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="report_2-4.pdf"' in res.headers["content-disposition"]
    assert page_widths(res.content) == [102, 103, 104]


def test_split_merge_puts_ranges_in_one_pdf(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="7, 1-2", merge="true")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="report_split.pdf"' in res.headers["content-disposition"]
    assert page_widths(res.content) == [107, 101, 102]


def test_split_every_n_pages(client):
    res = split(client, make_pdf(TEN_PAGES), mode="every", every="4")
    assert res.status_code == 200
    assert zip_parts(res.content) == {
        "report_1-4.pdf": [101, 102, 103, 104],
        "report_5-8.pdf": [105, 106, 107, 108],
        "report_9-10.pdf": [109, 110],
    }


def test_split_every_page(client):
    res = split(client, make_pdf([100, 200, 300]), mode="every", every="1")
    assert zip_parts(res.content) == {"report_1.pdf": [100], "report_2.pdf": [200], "report_3.pdf": [300]}


def test_split_every_with_one_chunk_returns_pdf(client):
    res = split(client, make_pdf([100, 200]), mode="every", every="5")
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="report_1-2.pdf"' in res.headers["content-disposition"]


@pytest.mark.parametrize("ranges, message", [
    ("", "at least one"),
    (" , ", "at least one"),
    ("abc", "not a valid page range"),
    ("1-2-3", "not a valid page range"),
    ("0", "not a valid page range"),
    ("5-3", "not a valid page range"),
    ("-3", "not a valid page range"),
    ("١", "not a valid page range"),  # Arabic-Indic digit one
    ("9-11", "has 10 pages"),
    ("1-3, 3-5", "Page 3 is in more than one range"),
    ("4, 1-5", "Page 4 is in more than one range"),
])
def test_split_rejects_bad_ranges(client, ranges, message):
    res = split(client, make_pdf(TEN_PAGES), ranges=ranges)
    assert res.status_code == 400
    assert message in res.json()["detail"]


def test_split_rejects_overlong_ranges_field(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="1," * 600)
    assert res.status_code == 422


@pytest.mark.parametrize("every", ["0", "-1", "x"])
def test_split_rejects_bad_every(client, every):
    assert split(client, make_pdf(TEN_PAGES), mode="every", every=every).status_code == 422


def test_split_rejects_merge_with_every(client):
    res = split(client, make_pdf(TEN_PAGES), mode="every", every="2", merge="true")
    assert res.status_code == 400


def test_split_rejects_too_many_parts(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_SPLIT_PARTS", 3)
    res = split(client, make_pdf(TEN_PAGES), mode="every", every="3")
    assert res.status_code == 400
    assert "4 PDFs" in res.json()["detail"]
    assert split(client, make_pdf(TEN_PAGES), mode="every", every="4").status_code == 200


def test_split_part_limit_does_not_apply_to_merge(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_SPLIT_PARTS", 1)
    assert split(client, make_pdf(TEN_PAGES), ranges="1,3,5", merge="true").status_code == 200


@pytest.fixture(scope="module")
def big_pdf() -> bytes:
    data = make_image_pdf(pages=2)  # about 2.4 MB per page
    assert 4 * 1024 * 1024 < len(data) < 6 * 1024 * 1024
    return data


@pytest.mark.parametrize("fields", [
    {"mode": "every", "every": "1"},  # each page fits; the running total doesn't
    {"ranges": "1-2"},
    {"ranges": "1-2", "merge": "true"},
])
def test_split_rejects_oversized_output(client, monkeypatch, big_pdf, fields):
    monkeypatch.setattr(config, "MAX_SPLIT_OUTPUT_MB", 3)
    res = split(client, big_pdf, **fields)
    assert res.status_code == 400
    assert "3 MB limit" in res.json()["detail"]


def test_split_zip_entries_are_stored(client):
    res = split(client, make_pdf(TEN_PAGES), ranges="1,2")
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert {i.compress_type for i in zf.infolist()} == {zipfile.ZIP_STORED}


@pytest.mark.parametrize("fields", [{"mode": "every", "every": "1"}, {"ranges": "1"}])
def test_split_rejects_pdf_without_pages(client, fields):
    res = split(client, make_pdf([]), name="empty.pdf", **fields)
    assert res.status_code == 400
    assert '"empty.pdf" has no pages' in res.json()["detail"]


def test_split_rejects_non_pdf(client):
    res = split(client, b"hello", name="notes.txt")
    assert res.status_code == 400
    assert "notes.txt" in res.json()["detail"]


def test_split_rejects_damaged_pdf(client):
    res = split(client, b"%PDF-1.7\nnot really a pdf", name="broken.pdf", ranges="1")
    assert res.status_code == 400
    assert "broken.pdf" in res.json()["detail"]


def test_split_rejects_password_protected_pdf(client):
    res = split(client, make_pdf([100], password="secret"), ranges="1")
    assert res.status_code == 400
    assert "password" in res.json()["detail"]


def test_split_reports_damage_found_while_writing(client, monkeypatch):
    def broken_write(self, *args, **kwargs):
        raise KeyError("/Length")

    data = make_pdf(TEN_PAGES)  # built before patching
    monkeypatch.setattr("app.services.split.PdfWriter.write", broken_write)
    res = split(client, data, ranges="1")
    assert res.status_code == 400
    assert "damaged" in res.json()["detail"]


def test_split_does_not_report_running_out_of_memory_as_damage(client, monkeypatch):
    def exhausted(self, *args, **kwargs):
        raise MemoryError

    data = make_pdf(TEN_PAGES)  # built before patching
    monkeypatch.setattr("app.services.split.PdfWriter.write", exhausted)
    with pytest.raises(MemoryError):
        split(client, data, ranges="1")


def test_split_reports_recursion_error_as_damage(client, monkeypatch):
    # pypdf hits this on deeply nested objects in the upload: a bad file, not a server problem.
    def too_deep(self, *args, **kwargs):
        raise RecursionError

    data = make_pdf(TEN_PAGES)  # built before patching
    monkeypatch.setattr("app.services.split.PdfWriter.write", too_deep)
    res = split(client, data, ranges="1")
    assert res.status_code == 400
    assert "damaged" in res.json()["detail"]


def test_split_returns_503_when_busy(client, monkeypatch):
    from app.routers.split import limiter

    monkeypatch.setattr(config, "MAX_CONCURRENT_SPLITS", 1)
    monkeypatch.setattr(limiter, "active", 1)
    assert split(client, make_pdf(TEN_PAGES), ranges="1").status_code == 503


def test_split_zip_entry_names_have_no_directories(client):
    res = split(client, make_pdf([100, 200, 300]), name="../../etc/x.pdf", ranges="1-2,3")
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.namelist() == ["x_1-2.pdf", "x_3.pdf"]


@pytest.mark.parametrize("name, expected", [
    ("../../etc/x.pdf", "x"),
    ('a\\b:c*?"<>|.pdf', "a_b_c______"),
    ("tab\there\r\n.PDF", "tab_here__"),
    (".pdf", "document"),
    (" .. ", "document"),
    ("CON.pdf", "_CON"),
    ("con.pdf.pdf", "_con.pdf"),
    ("Lpt1 .x.pdf", "_Lpt1 .x"),
    ("COM\u00b9.pdf", "_COM\u00b9"),
    ("CONSOLE.pdf", "CONSOLE"),
    ("x" * 300 + ".pdf", "x" * 100),
])
def test_output_stem_is_safe(name, expected):
    assert output_stem(name) == expected


def test_split_cleans_up_temp_files(client, leftover_workdirs):
    split(client, make_pdf(TEN_PAGES), ranges="1-2,3")
    split(client, make_pdf(TEN_PAGES), ranges="99")
    split(client, b"%PDF-1.7 junk", ranges="1")
    assert leftover_workdirs() == set()
