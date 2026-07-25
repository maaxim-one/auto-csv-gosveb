import io
import pytest
from PIL import Image
from app.services.image import convert_image_bytes_to_pdf


def _make_png_bytes(width=100, height=50, mode='RGB'):
    img = Image.new(mode, (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_jpeg_bytes(width=100, height=50):
    img = Image.new('RGB', (width, height), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


def test_convert_png_to_pdf():
    png = _make_png_bytes()
    pdf = convert_image_bytes_to_pdf(png)
    assert pdf is not None
    assert len(pdf) > 100
    assert pdf[:4] == b'%PDF'


def test_convert_jpeg_to_pdf():
    jpg = _make_jpeg_bytes()
    pdf = convert_image_bytes_to_pdf(jpg)
    assert pdf is not None
    assert len(pdf) > 100
    assert pdf[:4] == b'%PDF'


def test_convert_rgba_to_pdf():
    png = _make_png_bytes(mode='RGBA')
    pdf = convert_image_bytes_to_pdf(png)
    assert pdf is not None
    assert len(pdf) > 100
    assert pdf[:4] == b'%PDF'


def test_convert_p_mode_to_pdf():
    img = Image.new('P', (80, 80), color=0)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    pdf = convert_image_bytes_to_pdf(buf.getvalue())
    assert pdf is not None
    assert len(pdf) > 100
    assert pdf[:4] == b'%PDF'
