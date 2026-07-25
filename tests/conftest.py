import os
import tempfile
import shutil
import zipfile
import io
import json
import pytest
from app import create_app


class TestConfig:
    SECRET_KEY = 'test-secret-key'
    TESTING = True
    STORAGE_DIR = ''  # set per test

    ALLOWED_ARCHIVE_EXT = {'zip'}
    ALLOWED_DOC_EXTS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.xlsx', '.xls'}
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}
    EXCEL_EXTS = {'.xlsx', '.xls'}
    MAX_FILENAME_BYTES = 200
    MAX_ZIP_SIZE = 90 * 1024 * 1024
    APP_VERSION = '1.1.0'
    GITHUB_REPO = 'maaxim-one/auto-csv-gosveb'
    TEMPLATE_FOLDER = os.path.abspath('templates')
    STATIC_FOLDER = os.path.abspath('static')


@pytest.fixture
def tmp_storage(tmp_path):
    d = str(tmp_path / 'storage')
    os.makedirs(d, exist_ok=True)
    return d


@pytest.fixture
def app(tmp_storage):
    cfg = TestConfig()
    cfg.STORAGE_DIR = tmp_storage
    app = create_app(config_class=cfg)
    app.config['TESTING'] = True
    app.config['SERVER_NAME'] = 'localhost'
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_zip(rows_files):
    """Build an in-memory ZIP: rows_files = [(archive_name, bytes), ...]"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in rows_files:
            zf.writestr(name, data)
    buf.seek(0)
    return buf.read()
