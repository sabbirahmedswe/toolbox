import io
import shutil

import pytest
from pypdf import PdfReader

from app import config
from tests.helpers import make_image_pdf, make_pdf

requires_gs = pytest.mark.skipif(shutil.which(config.GS_BINARY) is None, reason="Ghostscript not installed")


def pdf_upload(name: str, data: bytes):
    return {"file": (name, data, "application/pdf")}


@pytest.fixture(autouse=True)
def compression_slots(monkeypatch):
    # The default is the CPU count; an estimate needs two free slots, which a 1-CPU runner lacks.
    monkeypatch.setattr(config, "MAX_CONCURRENT_COMPRESSIONS", 4)


@pytest.fixture(scope="module")
def image_pdf() -> bytes:
    return make_image_pdf(pages=2)


@requires_gs
@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_compress_reduces_size(client, image_pdf, level):
    res = client.post("/api/compress", files=pdf_upload("scan.pdf", image_pdf), data={"level": level})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="scan_compressed.pdf"' in res.headers["content-disposition"]
    assert int(res.headers["x-original-size"]) == len(image_pdf)
    assert int(res.headers["x-compressed-size"]) == len(res.content)
    assert len(res.content) < len(image_pdf)
    assert len(PdfReader(io.BytesIO(res.content)).pages) == 2


@requires_gs
def test_higher_levels_compress_more(client, image_pdf):
    sizes = [
        len(client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf), data={"level": lvl}).content)
        for lvl in ("low", "medium", "high")
    ]
    assert sizes[0] >= sizes[1] >= sizes[2]


@requires_gs
@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_images_downsampled_to_level_dpi_as_jpeg(client, image_pdf, level):
    from app.services.compress import LEVELS

    res = client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf), data={"level": level})
    page = PdfReader(io.BytesIO(res.content)).pages[0]
    (image,) = [x.get_object() for x in page["/Resources"]["/XObject"].values()]
    page_width_in = float(page.mediabox.width) / 72
    # JPEG, not the lossless encoding Ghostscript picks for smooth photos, which can grow the file.
    assert image["/Filter"] == "/DCTDecode"
    assert image["/Width"] / page_width_in == pytest.approx(LEVELS[level].dpi, rel=0.02)


@requires_gs
def test_default_level_is_medium(client, image_pdf):
    default = client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf))
    medium = client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf), data={"level": "medium"})
    assert default.status_code == 200
    assert len(default.content) == len(medium.content)


@requires_gs
def test_never_returns_larger_file(client):
    original = make_pdf([100, 200])  # tiny, already minimal
    res = client.post("/api/compress", files=pdf_upload("a.pdf", original), data={"level": "low"})
    assert res.status_code == 200
    assert len(res.content) <= len(original)
    assert len(PdfReader(io.BytesIO(res.content)).pages) == 2


@requires_gs
def test_non_ascii_filename(client, image_pdf):
    res = client.post("/api/compress", files=pdf_upload("résumé.pdf", image_pdf))
    assert res.status_code == 200
    disposition = res.headers["content-disposition"]
    assert 'filename="r_sum__compressed.pdf"' in disposition
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9_compressed.pdf" in disposition


def test_invalid_level_rejected(client):
    res = client.post("/api/compress", files=pdf_upload("a.pdf", make_pdf([100])), data={"level": "extreme"})
    assert res.status_code == 422


def test_requires_a_file(client):
    res = client.post("/api/compress", data={"level": "medium"})
    assert res.status_code == 422


def test_non_pdf_rejected(client):
    res = client.post("/api/compress", files={"file": ("a.pdf", b"hello world", "application/pdf")})
    assert res.status_code == 400
    assert "not a valid PDF" in res.json()["detail"]


def test_damaged_pdf_rejected(client):
    res = client.post("/api/compress", files=pdf_upload("bad.pdf", b"%PDF-1.4\ngarbage"))
    assert res.status_code == 400
    assert "damaged" in res.json()["detail"]


def test_password_protected_rejected(client):
    res = client.post("/api/compress", files=pdf_upload("locked.pdf", make_pdf([100], password="secret")))
    assert res.status_code == 400
    assert "password" in res.json()["detail"]


def test_missing_ghostscript_returns_503(client, monkeypatch):
    monkeypatch.setattr(config, "GS_BINARY", "definitely-not-ghostscript")
    res = client.post("/api/compress", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 503
    assert "Ghostscript" in res.json()["detail"]


def test_ghostscript_timeout_rejected(client, image_pdf, monkeypatch):
    import subprocess

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(config, "GS_BINARY", "sh")  # any binary that exists
    monkeypatch.setattr("app.services.compress.subprocess.run", fake_run)
    res = client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf))
    assert res.status_code == 400
    assert "too long" in res.json()["detail"]


@requires_gs
def test_temp_files_cleaned_up(client, image_pdf, leftover_workdirs):
    client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf))
    client.post("/api/compress", files=pdf_upload("a.pdf", b"not a pdf"))
    assert leftover_workdirs() == set()


@requires_gs
def test_returns_original_bytes_when_not_smaller(client):
    original = make_pdf([100])
    res = client.post("/api/compress", files=pdf_upload("a.pdf", original), data={"level": "low"})
    assert res.status_code == 200
    assert res.content == original
    assert res.headers["x-compressed-size"] == res.headers["x-original-size"]


@requires_gs
@pytest.mark.parametrize(
    ("upload_name", "expected"),
    [(".pdf", "document_compressed.pdf"), ("Report.PDF", "Report_compressed.pdf"), ("notes", "notes_compressed.pdf")],
)
def test_output_filename(client, upload_name, expected):
    res = client.post("/api/compress", files=pdf_upload(upload_name, make_pdf([100])))
    assert res.status_code == 200
    assert f'filename="{expected}"' in res.headers["content-disposition"]


def test_busy_server_returns_503(client, monkeypatch, leftover_workdirs):
    monkeypatch.setattr(config, "MAX_CONCURRENT_COMPRESSIONS", 0)
    res = client.post("/api/compress", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 503
    assert "busy" in res.json()["detail"]
    assert leftover_workdirs() == set()


@requires_gs
def test_ghostscript_memory_limit_enforced(client, image_pdf, monkeypatch):
    monkeypatch.setattr(config, "GS_MEMORY_LIMIT_MB", 1)  # far too little for gs to run
    res = client.post("/api/compress", files=pdf_upload("a.pdf", image_pdf))
    assert res.status_code == 400
    assert "could not be compressed" in res.json()["detail"]


def test_busy_check_happens_before_upload_is_saved(client, monkeypatch):
    from app.routers import compress

    async def fail(*args, **kwargs):
        raise AssertionError("upload should not be saved when the server is busy")

    monkeypatch.setattr(config, "MAX_CONCURRENT_COMPRESSIONS", 0)
    monkeypatch.setattr(compress, "save_upload", fail)
    res = client.post("/api/compress", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 503


@requires_gs
def test_estimate_matches_actual_sizes(client, image_pdf):
    res = client.post("/api/compress/estimate", files=pdf_upload("scan.pdf", image_pdf))
    assert res.status_code == 200
    body = res.json()
    assert body["original_size"] == len(image_pdf)
    assert set(body["sizes"]) == {"low", "medium", "high"}
    for level, size in body["sizes"].items():
        actual = client.post("/api/compress", files=pdf_upload("scan.pdf", image_pdf), data={"level": level})
        assert size == len(actual.content)


@requires_gs
def test_estimate_never_exceeds_original(client):
    original = make_pdf([100])
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", original))
    assert res.status_code == 200
    assert all(size <= len(original) for size in res.json()["sizes"].values())


def test_estimate_non_pdf_rejected(client):
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", b"not a pdf"))
    assert res.status_code == 400


def test_estimate_missing_ghostscript_returns_503(client, monkeypatch):
    monkeypatch.setattr(config, "GS_BINARY", "definitely-not-ghostscript")
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 503
    assert "Ghostscript" in res.json()["detail"]


def test_estimate_timeout_rejected(client, image_pdf, monkeypatch):
    import subprocess

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(config, "GS_BINARY", "sh")
    monkeypatch.setattr("app.services.compress.subprocess.run", fake_run)
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", image_pdf))
    assert res.status_code == 400
    assert "too long" in res.json()["detail"]


def test_estimate_busy_server_returns_503_before_upload(client, monkeypatch, leftover_workdirs):
    from app.routers import compress

    async def fail(*args, **kwargs):
        raise AssertionError("upload should not be saved when the server is busy")

    monkeypatch.setattr(config, "MAX_CONCURRENT_COMPRESSIONS", 0)
    monkeypatch.setattr(compress, "save_upload", fail)
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 503
    assert leftover_workdirs() == set()


@requires_gs
def test_estimate_temp_files_cleaned_up(client, image_pdf, leftover_workdirs):
    client.post("/api/compress/estimate", files=pdf_upload("a.pdf", image_pdf))
    client.post("/api/compress/estimate", files=pdf_upload("a.pdf", b"not a pdf"))
    assert leftover_workdirs() == set()


def _fake_gs(monkeypatch, seconds_per_run: float) -> list[float]:
    """Replace Ghostscript with a stub that copies the input and advances a fake clock; returns the timeouts used."""
    clock = [1000.0]
    timeouts: list[float] = []

    def fake_run(cmd, **kwargs):
        timeouts.append(kwargs["timeout"])
        clock[0] += seconds_per_run
        out = next(arg.removeprefix("-sOutputFile=") for arg in cmd if arg.startswith("-sOutputFile="))
        shutil.copyfile(cmd[-1], out)

    monkeypatch.setattr(config, "GS_BINARY", "sh")  # any binary that exists
    monkeypatch.setattr(config, "GS_TIMEOUT_SECONDS", 120)
    monkeypatch.setattr("app.services.compress.subprocess.run", fake_run)
    monkeypatch.setattr("app.services.compress.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.routers.compress.time.monotonic", lambda: clock[0])
    return timeouts


def test_estimate_levels_share_one_time_budget(client, monkeypatch):
    timeouts = _fake_gs(monkeypatch, seconds_per_run=30)
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 200
    assert timeouts == [120, 90, 60]


def test_estimate_stops_early_when_levels_wont_fit(client, monkeypatch, leftover_workdirs):
    # 50 s for the first level projects 100 s for the other two, but only 70 s are left.
    timeouts = _fake_gs(monkeypatch, seconds_per_run=50)
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == 400
    assert "too long" in res.json()["detail"]
    assert timeouts == [120]
    assert leftover_workdirs() == set()


@pytest.mark.parametrize(("slots", "busy", "allowed"), [(1, 0, False), (2, 0, True), (4, 1, True), (4, 2, False)])
def test_estimate_leaves_half_the_slots_for_compression(client, monkeypatch, slots, busy, allowed):
    from app.routers import compress

    monkeypatch.setattr(config, "MAX_CONCURRENT_COMPRESSIONS", slots)
    monkeypatch.setattr(compress.limiter, "active", busy)
    if not allowed:

        async def fail(*args, **kwargs):
            raise AssertionError("upload should not be saved when the estimate is refused")

        monkeypatch.setattr(compress, "save_upload", fail)
    _fake_gs(monkeypatch, seconds_per_run=1)
    res = client.post("/api/compress/estimate", files=pdf_upload("a.pdf", make_pdf([100])))
    assert res.status_code == (200 if allowed else 503)


@pytest.mark.parametrize(("dpi", "qfactor"), [(0, 0.4), (150, 0.0), (150, 1e-05), (150, 3.0), (150.0, 0.4), (150, "0.4")])
def test_level_settings_reject_out_of_range_values(dpi, qfactor):
    from app.services.compress import LevelSettings

    with pytest.raises(ValueError):
        LevelSettings("/ebook", dpi, qfactor)
