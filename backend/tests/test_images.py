import io

import pytest
from PIL import Image
from pypdf import PdfReader

from app import config
from tests.helpers import make_image, make_pdf


def jpeg(name: str, data: bytes):
    return ("files", (name, data, "image/jpeg"))


def png(name: str, data: bytes):
    return ("files", (name, data, "image/png"))


def pages(data: bytes):
    return PdfReader(io.BytesIO(data)).pages


def page_sizes(data: bytes) -> list[tuple[int, int]]:
    """Displayed page sizes in points, accounting for /Rotate."""
    sizes = []
    for p in pages(data):
        w, h = round(float(p.mediabox.width)), round(float(p.mediabox.height))
        sizes.append((h, w) if p.rotation % 180 else (w, h))
    return sizes


def page_image(data: bytes, index: int = 0) -> Image.Image:
    return pages(data)[index].images[0].image


def test_one_page_per_image_in_order(client):
    res = client.post("/api/images-to-pdf", files=[
        jpeg("a.jpg", make_image(size=(96, 48))),
        png("b.png", make_image("PNG", size=(192, 48))),
        jpeg("c.jpg", make_image(size=(48, 96))),
    ])
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="images.pdf"' in res.headers["content-disposition"]
    # No DPI in the files, so 96 dpi: 1 px = 0.75 pt.
    assert page_sizes(res.content) == [(72, 36), (144, 36), (36, 72)]


def test_jpeg_is_embedded_without_reencoding(client):
    original = make_image(size=(64, 64))
    res = client.post("/api/images-to-pdf", files=[jpeg("a.jpg", original)])
    assert res.status_code == 200
    assert original in res.content


def test_png_transparency_is_flattened_onto_white(client):
    transparent = make_image("PNG", size=(20, 20), mode="RGBA", color=(255, 0, 0, 0))
    res = client.post("/api/images-to-pdf", files=[png("t.png", transparent)])
    assert res.status_code == 200
    assert page_image(res.content).convert("RGB").getpixel((10, 10)) == (255, 255, 255)


@pytest.mark.parametrize(
    ("mode", "color", "extra"),
    [
        ("LA", (0, 128), {}),
        ("P", 0, {"transparency": 0}),
        ("I;16", 65535, {}),
        ("1", 1, {}),
    ],
)
def test_other_png_modes_convert(client, mode, color, extra):
    data = make_image("PNG", size=(16, 16), mode=mode, color=color, **extra)
    res = client.post("/api/images-to-pdf", files=[png("x.png", data)])
    assert res.status_code == 200, res.text
    assert len(pages(res.content)) == 1


def test_sixteen_bit_greyscale_is_scaled_not_clipped(client):
    data = make_image("PNG", size=(8, 8), mode="I;16", color=32768)  # mid grey
    res = client.post("/api/images-to-pdf", files=[png("g.png", data)])
    assert res.status_code == 200
    assert page_image(res.content).convert("L").getpixel((4, 4)) == 128


def test_exif_rotation_applied(client):
    # Orientation 6: stored 96x48, displayed rotated 90° -> 48x96 px.
    # Pillow reports 72 dpi for JPEGs with EXIF (like phone photos), so 1 px = 1 pt.
    res = client.post("/api/images-to-pdf", files=[jpeg("r.jpg", make_image(size=(96, 48), orientation=6))])
    assert res.status_code == 200
    assert page_sizes(res.content) == [(48, 96)]


def test_mirrored_exif_orientation_applied(client):
    # Orientation 5 (transpose) swaps the sides and needs re-encoding.
    res = client.post("/api/images-to-pdf", files=[jpeg("m.jpg", make_image(size=(96, 48), orientation=5))])
    assert res.status_code == 200
    assert page_sizes(res.content) == [(48, 96)]
    assert pages(res.content)[0].rotation == 0  # pixels were transposed, not the page


def test_dpi_sets_page_size(client):
    # A 300 dpi US Letter scan becomes a Letter page.
    res = client.post("/api/images-to-pdf", files=[jpeg("scan.jpg", make_image(size=(2550, 3300), dpi=(300, 300)))])
    assert res.status_code == 200
    assert page_sizes(res.content) == [(612, 792)]


def test_implausible_dpi_ignored(client):
    res = client.post("/api/images-to-pdf", files=[png("d.png", make_image("PNG", size=(96, 48), dpi=(1, 1)))])
    assert res.status_code == 200
    assert page_sizes(res.content) == [(72, 36)]


def test_huge_page_capped(client):
    # 20000 px at 96 dpi would be 208 inches; capped to the 200-inch (14400 pt) maximum.
    res = client.post("/api/images-to-pdf", files=[png("w.png", make_image("PNG", size=(20000, 10), mode="L", color=0))])
    assert res.status_code == 200
    width, _ = page_sizes(res.content)[0]
    assert width == 14400


def test_too_many_pixels_rejected(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_PIXELS", 1000)
    res = client.post("/api/images-to-pdf", files=[jpeg("big.jpg", make_image(size=(100, 100)))])
    assert res.status_code == 400
    assert "too large" in res.json()["detail"]


def test_non_image_rejected(client):
    res = client.post("/api/images-to-pdf", files=[jpeg("a.jpg", b"definitely not an image")])
    assert res.status_code == 400
    assert "not a valid JPEG or PNG" in res.json()["detail"]


def test_pdf_rejected(client):
    res = client.post("/api/images-to-pdf", files=[("files", ("a.pdf", make_pdf([100]), "application/pdf"))])
    assert res.status_code == 400


def test_truncated_image_rejected(client):
    data = make_image(size=(200, 200))
    res = client.post("/api/images-to-pdf", files=[jpeg("cut.jpg", data[: len(data) // 2])])
    assert res.status_code == 400
    assert "damaged" in res.json()["detail"]


def test_requires_a_file(client):
    assert client.post("/api/images-to-pdf").status_code == 422


def test_too_many_files_rejected(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_FILES", 2)
    res = client.post("/api/images-to-pdf", files=[jpeg(f"{i}.jpg", make_image()) for i in range(3)])
    assert res.status_code == 400
    assert "Too many files" in res.json()["detail"]


def test_busy_server_returns_503(client, monkeypatch):
    monkeypatch.setattr(config, "MAX_CONCURRENT_IMAGE_JOBS", 0)
    res = client.post("/api/images-to-pdf", files=[jpeg("a.jpg", make_image())])
    assert res.status_code == 503


def test_temp_files_cleaned_up(client, leftover_workdirs):
    client.post("/api/images-to-pdf", files=[jpeg("a.jpg", make_image()), png("b.png", make_image("PNG"))])
    client.post("/api/images-to-pdf", files=[jpeg("a.jpg", b"nope")])
    assert leftover_workdirs() == set()


def no_soft_masks(data: bytes) -> bool:
    return all("/SMask" not in img for p in pages(data) for img in [p["/Resources"]["/XObject"][k].get_object() for k in p["/Resources"]["/XObject"]])


def test_quarter_turn_swaps_dpi(client):
    # 100x50 at 300x150 dpi is a 24x24 pt square; after a transpose (orientation 5) it must stay square.
    data = make_image(size=(100, 50), orientation=5, dpi=(300, 150))
    res = client.post("/api/images-to-pdf", files=[jpeg("d.jpg", data)])
    assert res.status_code == 200
    assert page_sizes(res.content) == [(24, 24)]


@pytest.mark.parametrize(
    ("mode", "color", "key"),
    [("RGB", (10, 20, 30), (10, 20, 30)), ("L", 10, 10), ("I;16", 500, 500)],
)
def test_colour_key_transparency_flattened_onto_white(client, mode, color, key):
    data = make_image("PNG", size=(8, 8), mode=mode, color=color, transparency=key)
    res = client.post("/api/images-to-pdf", files=[png("k.png", data)])
    assert res.status_code == 200
    assert no_soft_masks(res.content)
    assert page_image(res.content).convert("L").getpixel((4, 4)) == 255


def test_icc_profile_preserved(client):
    from PIL import ImageCms

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    # RGBA forces the re-encode path.
    data = make_image("PNG", size=(8, 8), mode="RGBA", color=(0, 0, 255, 255), icc_profile=icc)
    res = client.post("/api/images-to-pdf", files=[png("p3.png", data)])
    assert res.status_code == 200
    assert b"/ICCBased" in res.content


def test_mirrored_cmyk_jpeg_stays_cmyk(client):
    data = make_image(size=(16, 8), mode="CMYK", color=(0, 100, 200, 0), orientation=2)
    res = client.post("/api/images-to-pdf", files=[jpeg("c.jpg", data)])
    assert res.status_code == 200
    assert page_image(res.content).mode == "CMYK"


def test_pillow_uses_configured_pixel_limit():
    from app.services import images

    assert images.Image.MAX_IMAGE_PIXELS == config.MAX_IMAGE_PIXELS


@pytest.mark.parametrize(
    ("data", "kind", "as_is"),
    [
        (make_image("PNG", mode="RGB"), "png", True),
        (make_image("PNG", mode="L", color=10), "png", True),
        (make_image("PNG", mode="RGBA", color=(1, 2, 3, 4)), "png", False),
        (make_image("PNG", mode="RGB", transparency=(200, 30, 30)), "png", False),
        (make_image("PNG", mode="P", color=1), "png", False),
        (make_image(orientation=6), "jpeg", True),
        (make_image(orientation=2), "jpeg", False),
    ],
)
def test_only_unembeddable_images_are_reencoded(tmp_path, data, kind, as_is):
    from app.services.images import prepare_image

    src = tmp_path / "0"
    src.write_bytes(data)
    assert (prepare_image(src, kind, "x", tmp_path) == src) is as_is


def test_busy_check_happens_before_upload_is_saved(client, monkeypatch):
    from app.routers import images

    async def fail(*args, **kwargs):
        raise AssertionError("upload should not be saved when the server is busy")

    monkeypatch.setattr(config, "MAX_CONCURRENT_IMAGE_JOBS", 0)
    monkeypatch.setattr(images, "save_upload", fail)
    res = client.post("/api/images-to-pdf", files=[jpeg("a.jpg", make_image())])
    assert res.status_code == 503
