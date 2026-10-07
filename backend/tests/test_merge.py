import io

from pypdf import PdfReader

from app import config
from tests.helpers import make_pdf


def pdf_upload(name: str, data: bytes):
    return ("files", (name, data, "application/pdf"))


def page_widths(data: bytes) -> list[int]:
    return [int(p.mediabox.width) for p in PdfReader(io.BytesIO(data)).pages]


def test_merge_two_files_in_order(client):
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100, 110])),
        pdf_upload("b.pdf", make_pdf([200])),
    ])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="merged.pdf"' in res.headers["content-disposition"]
    assert page_widths(res.content) == [100, 110, 200]


def test_merge_respects_upload_order(client):
    res = client.post("/api/merge", files=[
        pdf_upload("c.pdf", make_pdf([300])),
        pdf_upload("a.pdf", make_pdf([100])),
        pdf_upload("b.pdf", make_pdf([200])),
    ])
    assert res.status_code == 200
    assert page_widths(res.content) == [300, 100, 200]


def test_merge_requires_two_files(client):
    res = client.post("/api/merge", files=[pdf_upload("a.pdf", make_pdf([100]))])
    assert res.status_code == 400
    assert "at least 2" in res.json()["detail"]


def test_merge_rejects_non_pdf(client):
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100])),
        ("files", ("notes.txt", b"hello world", "text/plain")),
    ])
    assert res.status_code == 400
    assert "notes.txt" in res.json()["detail"]


def test_merge_rejects_damaged_pdf(client):
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100])),
        pdf_upload("broken.pdf", b"%PDF-1.7\nthis is not really a pdf"),
    ])
    assert res.status_code == 400
    assert "broken.pdf" in res.json()["detail"]


def test_merge_rejects_password_protected_pdf(client):
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100])),
        pdf_upload("locked.pdf", make_pdf([200], password="secret")),
    ])
    assert res.status_code == 400
    assert "password" in res.json()["detail"]


def test_merge_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_FILE_SIZE", 100)
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100])),
        pdf_upload("b.pdf", make_pdf([200])),
    ])
    assert res.status_code == 413


def test_merge_rejects_too_many_files(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_FILES", 2)
    res = client.post("/api/merge", files=[pdf_upload(f"{i}.pdf", make_pdf([100])) for i in range(3)])
    assert res.status_code == 400
    assert "Too many" in res.json()["detail"]


def test_merge_rejects_oversized_request_before_parsing(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_TOTAL_SIZE", 100)
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", make_pdf([100])),
        pdf_upload("b.pdf", make_pdf([200])),
    ])
    assert res.status_code == 413
    assert "total limit" in res.json()["detail"]


def test_merge_requires_content_length(client):
    def chunked():
        yield b"--x\r\n"

    res = client.post("/api/merge", content=chunked(), headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert res.status_code == 411


def test_merge_accepts_pdf_header_after_leading_bytes(client):
    res = client.post("/api/merge", files=[
        pdf_upload("a.pdf", b"\xef\xbb\xbf\n" + make_pdf([100])),
        pdf_upload("b.pdf", make_pdf([200])),
    ])
    assert res.status_code == 200
    assert page_widths(res.content) == [100, 200]


def test_merge_cleans_up_temp_files(client, leftover_workdirs):
    client.post("/api/merge", files=[pdf_upload("a.pdf", make_pdf([100])), pdf_upload("b.pdf", make_pdf([200]))])
    client.post("/api/merge", files=[pdf_upload("a.pdf", make_pdf([100])), pdf_upload("x.pdf", b"%PDF-1.7 junk")])
    client.post("/api/merge", files=[pdf_upload("a.pdf", make_pdf([100])), ("files", ("x.txt", b"hi", "text/plain"))])
    assert leftover_workdirs() == set()
