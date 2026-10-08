import io
import shutil

import pytest
from pypdf import PdfReader

from app import config
from tests.helpers import make_image_pdf, make_jpeg_pdf, make_pdf, make_text_image

requires_gs = pytest.mark.skipif(shutil.which(config.GS_BINARY) is None, reason="Ghostscript not installed")


def pdf_upload(name: str, data: bytes):
    return {"file": (name, data, "application/pdf")}


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


@pytest.mark.parametrize(("dpi", "qfactor"), [(0, 0.4), (150, 0.0), (150, 1e-05), (150, 3.0), (150.0, 0.4), (150, "0.4")])
def test_level_settings_reject_out_of_range_values(dpi, qfactor):
    from app.services.compress import LevelSettings

    with pytest.raises(ValueError):
        LevelSettings("/ebook", dpi, qfactor)


def jpeg(im, quality: int) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def page_jpegs(pdf: bytes) -> list[tuple[bytes, int, int]]:
    from app.services.compress import _images

    reader = PdfReader(io.BytesIO(pdf))
    return [(i._data, i["/Width"], i["/Height"]) for i in _images(reader.pages) if i["/Filter"] == "/DCTDecode"]


@pytest.fixture(scope="module")
def low_quality_photo() -> bytes:
    from PIL import Image, ImageFilter

    # Smooth, like a photo, and saved at a lower quality than any level re-encodes at.
    im = Image.effect_noise((60, 40), 80).convert("RGB").filter(ImageFilter.GaussianBlur(3)).resize((600, 400))
    return jpeg(im, 30)


@requires_gs
@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_smaller_original_jpeg_with_soft_mask_restored(client, low_quality_photo, level):
    # Ghostscript re-encodes JPEGs with a soft mask, which made low-quality originals bigger.
    original = make_jpeg_pdf([low_quality_photo], soft_mask=True, padding=100_000)
    res = client.post("/api/compress", files=pdf_upload("a.pdf", original), data={"level": level})
    assert res.status_code == 200
    ((data, width, height),) = page_jpegs(res.content)
    assert (data, width, height) == (low_quality_photo, 600, 400)
    assert len(res.content) < len(original)


@requires_gs
def test_restored_jpegs_are_not_swapped_between_similar_pages(tmp_path):
    # Pages of text look alike when scaled down; each must keep its own image.
    from app.services.compress import _restore_original_jpegs

    pages = [make_text_image(seed) for seed in range(3)]
    original = make_jpeg_pdf([jpeg(p, 30) for p in pages])
    # Stand-in for Ghostscript's output: bigger copies of the same pages, in a different order.
    dest = tmp_path / "out.pdf"
    dest.write_bytes(make_jpeg_pdf([jpeg(p, 90) for p in reversed(pages)]))
    _restore_original_jpegs(PdfReader(io.BytesIO(original)), dest)

    restored = [data for data, _, _ in page_jpegs(dest.read_bytes())]
    assert restored == [jpeg(p, 30) for p in reversed(pages)]


def test_restore_skips_images_that_differ(tmp_path):
    from app.services.compress import _restore_original_jpegs

    first, second = make_text_image(1), make_text_image(2)
    original = make_jpeg_pdf([jpeg(first, 30)])
    dest = tmp_path / "out.pdf"
    copy = make_jpeg_pdf([jpeg(second, 90)])
    dest.write_bytes(copy)
    _restore_original_jpegs(PdfReader(io.BytesIO(original)), dest)
    assert dest.read_bytes() == copy


def test_restore_skipped_for_files_with_too_many_jpegs(tmp_path, monkeypatch):
    from app.services import compress

    page = make_text_image(1)
    original = make_jpeg_pdf([jpeg(page, 30)] * 2)
    dest = tmp_path / "out.pdf"
    copy = make_jpeg_pdf([jpeg(page, 90)] * 2)
    dest.write_bytes(copy)
    monkeypatch.setattr(compress, "_MAX_JPEGS", 0)
    compress._restore_original_jpegs(PdfReader(io.BytesIO(original)), dest)
    assert dest.read_bytes() == copy


def test_restore_keeps_colour_and_grey_jpegs_apart(tmp_path):
    from app.services.compress import _restore_original_jpegs

    page = make_text_image(1)  # black and white, so it looks the same in grey and colour
    original = make_jpeg_pdf([jpeg(page.convert("L"), 30)])
    dest = tmp_path / "out.pdf"
    copy = make_jpeg_pdf([jpeg(page, 90)])
    dest.write_bytes(copy)
    _restore_original_jpegs(PdfReader(io.BytesIO(original)), dest)
    assert dest.read_bytes() == copy



def sideways_text_pdf() -> bytes:
    """A landscape page whose text all runs bottom to top, which Ghostscript's /screen preset rotates."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=842, height=595)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    text = " ".join(f"BT /F1 12 Tf 0 1 -1 0 {100 + 20 * i} 50 Tm (Sideways line of text {i}) Tj ET" for i in range(30))
    content.set_data(text.encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@requires_gs
@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_pages_not_auto_rotated(tmp_path, level):
    from app.services.compress import _run_ghostscript, ghostscript_path

    src, dest = tmp_path / "in.pdf", tmp_path / "out.pdf"
    src.write_bytes(sideways_text_pdf())
    _run_ghostscript(ghostscript_path(), src, dest, level, "a.pdf")
    page = PdfReader(dest).pages[0]
    assert page.get("/Rotate", 0) == 0
    assert (float(page.mediabox.width), float(page.mediabox.height)) == (842, 595)
