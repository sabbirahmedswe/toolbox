import io
import shutil
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from app import config
from tests.helpers import make_image, make_pdf

requires_gs = pytest.mark.skipif(shutil.which(config.GS_BINARY) is None, reason="Ghostscript not installed")

# Page widths 101..103 pt, so each image is identifiable by its width.
THREE_PAGES = [101, 102, 103]


def convert(client, data: bytes, name: str = "report.pdf", **fields):
    return client.post("/api/pdf-to-jpg", files={"file": (name, data, "application/pdf")}, data=fields)


def px(points: int, dpi: int = 150) -> int:
    """Ghostscript's image size for `points` at `dpi`: rounded half up, unlike Python's round()."""
    return int(points * dpi / 72 + 0.5)


def jpeg_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data), formats=["JPEG"]) as im:
        return im.size


@requires_gs
def test_pages_become_jpegs_in_zip(client):
    res = convert(client, make_pdf(THREE_PAGES))
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert 'filename="report_jpg.zip"' in res.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.namelist() == ["report_1.jpg", "report_2.jpg", "report_3.jpg"]
        widths = [jpeg_size(zf.read(n))[0] for n in zf.namelist()]
    assert widths == [px(w) for w in THREE_PAGES]


@requires_gs
def test_single_page_returns_jpeg(client):
    res = convert(client, make_pdf([144], height=72))
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/jpeg"
    assert 'filename="report.jpg"' in res.headers["content-disposition"]
    assert jpeg_size(res.content) == (300, 150)


@requires_gs
def test_high_quality_is_300_dpi(client):
    res = convert(client, make_pdf([144], height=72), quality="high")
    assert res.status_code == 200
    assert jpeg_size(res.content) == (600, 300)


@requires_gs
def test_names_padded_so_they_sort_in_page_order(client):
    res = convert(client, make_pdf(list(range(50, 61))))
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = zf.namelist()
        widths = [jpeg_size(zf.read(n))[0] for n in names]
    assert names == [f"report_{i:02}.jpg" for i in range(1, 12)]
    assert widths == [px(w) for w in range(50, 61)]


@requires_gs
def test_crop_box_is_rendered(client):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf([288], height=288))))
    writer.pages[0].cropbox = RectangleObject((0, 0, 144, 72))
    buf = io.BytesIO()
    writer.write(buf)
    res = convert(client, buf.getvalue())
    assert jpeg_size(res.content) == (300, 150)


@requires_gs
def test_page_rotation_is_applied(client):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf([144], height=72))))
    writer.pages[0].rotate(90)
    buf = io.BytesIO()
    writer.write(buf)
    res = convert(client, buf.getvalue())
    assert jpeg_size(res.content) == (150, 300)


@requires_gs
def test_non_ascii_filename(client):
    res = convert(client, make_pdf([100]), name="résumé.pdf")
    assert res.status_code == 200
    disposition = res.headers["content-disposition"]
    assert 'filename="r_sum_.jpg"' in disposition
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9.jpg" in disposition


@requires_gs
def test_temp_files_cleaned_up(client, leftover_workdirs):
    convert(client, make_pdf(THREE_PAGES))
    convert(client, b"not a pdf")
    assert leftover_workdirs() == set()


def test_invalid_quality_rejected(client):
    res = convert(client, make_pdf([100]), quality="ultra")
    assert res.status_code == 422


def test_non_pdf_rejected(client):
    res = convert(client, b"hello world")
    assert res.status_code == 400
    assert "not a valid PDF" in res.json()["detail"]


def test_damaged_pdf_rejected(client):
    res = convert(client, b"%PDF-1.4\ngarbage")
    assert res.status_code == 400
    assert "damaged" in res.json()["detail"]


def test_password_protected_rejected(client):
    res = convert(client, make_pdf([100], password="secret"))
    assert res.status_code == 400
    assert "password" in res.json()["detail"]


def test_too_many_pages_rejected(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_PDF_TO_JPG_PAGES", 2)
    res = convert(client, make_pdf(THREE_PAGES))
    assert res.status_code == 400
    assert "more than the limit of 2" in res.json()["detail"]


def test_oversized_page_rejected_before_rendering(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Ghostscript should not run")

    monkeypatch.setattr("app.services.pdf_to_jpg.stream_limited", fail)
    # 200 x 200 inches at 300 dpi is 3.6 billion pixels.
    res = convert(client, make_pdf([100, 14400], height=14400), quality="high")
    assert res.status_code == 400
    assert "Page 2" in res.json()["detail"] and "too large" in res.json()["detail"]


def test_user_unit_counts_towards_page_size(client, monkeypatch):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import FloatObject, NameObject

    monkeypatch.setattr("app.services.pdf_to_jpg.stream_limited", lambda *a, **k: pytest.fail("Ghostscript ran"))
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf([1000], height=1000))))
    writer.pages[0][NameObject("/UserUnit")] = FloatObject(75000)
    buf = io.BytesIO()
    writer.write(buf)
    res = convert(client, buf.getvalue())
    assert res.status_code == 400
    assert "too large" in res.json()["detail"]


@requires_gs
def test_output_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_PDF_TO_JPG_OUTPUT_MB", 0)
    res = convert(client, make_pdf(THREE_PAGES))
    assert res.status_code == 400
    assert "larger than the 0 MB limit" in res.json()["detail"]


def test_missing_ghostscript_returns_503(client, monkeypatch):
    monkeypatch.setattr(config, "GS_BINARY", "definitely-not-ghostscript")
    res = convert(client, make_pdf([100]))
    assert res.status_code == 503
    assert "Ghostscript" in res.json()["detail"]


def fake_gs(monkeypatch, chunks=(), error: Exception | None = None):
    """Make Ghostscript "write" `chunks` to stdout, then raise `error` (as stream_limited would on exit)."""
    from contextlib import contextmanager

    @contextmanager
    def stream(gs_cmd, timeout):
        def output():
            yield from chunks
            if error:
                raise error

        yield output()

    monkeypatch.setattr(config, "GS_BINARY", "sh")  # any binary that exists
    monkeypatch.setattr("app.services.pdf_to_jpg.stream_limited", stream)


def test_ghostscript_timeout_rejected(client, monkeypatch):
    import subprocess

    fake_gs(monkeypatch, error=subprocess.TimeoutExpired("gs", 1))
    res = convert(client, make_pdf([100]))
    assert res.status_code == 400
    assert "too long" in res.json()["detail"]


@pytest.mark.parametrize("images", [2, 4])
def test_page_count_mismatch_rejected(client, monkeypatch, images):
    fake_gs(monkeypatch, [make_image()] * images)
    res = convert(client, make_pdf(THREE_PAGES))
    assert res.status_code == 400
    assert "could not be converted" in res.json()["detail"]


def test_unexpected_ghostscript_output_rejected(client, monkeypatch):
    fake_gs(monkeypatch, [b"GPL Ghostscript warning\n", make_image()])
    res = convert(client, make_pdf([100]))
    assert res.status_code == 400
    assert "could not be converted" in res.json()["detail"]


def test_output_limit_stops_reading_ghostscript(client, monkeypatch):
    read = []

    def chunks():
        # A JPEG's start, then a scan that never ends.
        yield b"\xff\xd8\xff\xda\x00\x02"
        for i in range(10):
            read.append(i)
            yield bytes(512 * 1024)

    monkeypatch.setattr(config, "MAX_PDF_TO_JPG_OUTPUT_MB", 1)
    fake_gs(monkeypatch, chunks())
    res = convert(client, make_pdf([100]))
    assert res.status_code == 400
    assert "larger than the 1 MB limit" in res.json()["detail"]
    assert read == [0, 1]  # the header plus two chunks pass 1 MB; nothing more is read


def test_stream_limited_yields_output():
    from app.services.ghostscript import stream_limited

    with stream_limited(["sh", "-c", "printf abc; printf def"], 10) as chunks:
        assert b"".join(chunks) == b"abcdef"


def test_stream_limited_reports_failure():
    import subprocess

    from app.services.ghostscript import stream_limited

    with stream_limited(["sh", "-c", "printf abc; exit 3"], 10) as chunks:
        with pytest.raises(subprocess.CalledProcessError) as exc:
            list(chunks)
    assert exc.value.returncode == 3


def test_stream_limited_times_out():
    import subprocess
    import time

    from app.services.ghostscript import stream_limited

    start = time.monotonic()
    with stream_limited(["sh", "-c", "sleep 30"], 1) as chunks:
        with pytest.raises(subprocess.TimeoutExpired):
            list(chunks)
    assert time.monotonic() - start < 5


def test_stream_limited_kills_ghostscript_when_left_early(tmp_path):
    import os

    from app.services.ghostscript import stream_limited

    pid_file = tmp_path / "pid"
    # Endless output, like a huge render; the pid is the process's, as the wrapper execs it.
    with stream_limited(["sh", "-c", f'echo $$ > {pid_file}; exec yes'], 10) as chunks:
        next(chunks)
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@requires_gs
def test_ghostscript_memory_limit_enforced(client, monkeypatch):
    monkeypatch.setattr(config, "GS_MEMORY_LIMIT_MB", 1)  # far too little for gs to run
    res = convert(client, make_pdf([100]))
    assert res.status_code == 400
    assert "could not be converted" in res.json()["detail"]


def test_busy_check_happens_before_upload_is_saved(client, monkeypatch, leftover_workdirs):
    from app.routers import pdf_to_jpg

    async def fail(*args, **kwargs):
        raise AssertionError("upload should not be saved when the server is busy")

    monkeypatch.setattr(config, "MAX_CONCURRENT_PDF_TO_JPG", 0)
    monkeypatch.setattr(pdf_to_jpg, "save_upload", fail)
    res = convert(client, make_pdf([100]))
    assert res.status_code == 503
    assert "busy" in res.json()["detail"]
    assert leftover_workdirs() == set()


@pytest.mark.parametrize(("dpi", "jpeg_quality"), [(0, 85), (10_000, 85), (150, 0), (150, 101), ("150", 85)])
def test_quality_settings_reject_out_of_range_values(dpi, jpeg_quality):
    from app.services.pdf_to_jpg import QualitySettings

    with pytest.raises(ValueError):
        QualitySettings(dpi, jpeg_quality)


def split_jpegs(data: bytes, chunk_size: int) -> list[bytes]:
    from app.services.pdf_to_jpg import _JpegSplitter

    splitter = _JpegSplitter()
    images = []
    for i in range(0, len(data), chunk_size):
        images += splitter.feed(data[i : i + chunk_size])
    splitter.finish()
    return images


@pytest.fixture(scope="module")
def varied_jpegs() -> list[bytes]:
    """JPEGs whose scans contain stuffed 0xFF bytes, restart markers and (progressive) several scans."""
    noise = Image.effect_noise((64, 48), 100).convert("RGB")
    jpegs = []
    for options in ({}, {"progressive": True}, {"restart_marker_blocks": 1}, {"quality": 100}):
        buf = io.BytesIO()
        noise.save(buf, "JPEG", **options)
        jpegs.append(buf.getvalue())
    jpegs.append(make_image(mode="L", color=128))
    return jpegs


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 7, 1000, 1_000_000])
def test_jpeg_splitter_finds_each_image(varied_jpegs, chunk_size):
    assert any(b"\xff\x00" in j for j in varied_jpegs)
    assert any(b"\xff\xd0" in j for j in varied_jpegs)
    assert split_jpegs(b"".join(varied_jpegs), chunk_size) == varied_jpegs


@pytest.mark.parametrize(
    "data",
    [b"not a jpeg", make_image()[:-1], make_image() + b"\n", make_image()[:20] + b"\x00" + make_image()[20:]],
    ids=["garbage", "truncated", "trailing-data", "no-marker"],
)
def test_jpeg_splitter_rejects_bad_streams(data):
    with pytest.raises(ValueError):
        split_jpegs(data, 1000)
