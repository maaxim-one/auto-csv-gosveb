import os
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)


def _find_dejavu_path() -> str:
    from flask import current_app
    static_folder = current_app.config['STATIC_FOLDER']
    candidates = [
        os.path.join(static_folder, 'DejaVuSans.ttf'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'static', 'DejaVuSans.ttf'),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ''


def convert_image_bytes_to_pdf(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format='PDF')
    return pdf_bytes.getvalue()
