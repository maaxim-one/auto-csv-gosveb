import os
import sys



class Config:
    _raw_secret = os.environ.get('SECRET_KEY')
    if _raw_secret:
        SECRET_KEY = _raw_secret
    else:
        _secret_file = os.path.join(os.getcwd(), '.flask_secret')
        if os.path.isfile(_secret_file):
            try:
                with open(_secret_file, 'r') as f:
                    SECRET_KEY = f.read().strip()
            except Exception:
                SECRET_KEY = __import__('secrets').token_hex(32)
        else:
            SECRET_KEY = __import__('secrets').token_hex(32)
            with open(_secret_file, 'w') as f:
                f.write(SECRET_KEY)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    STORAGE_DIR = os.path.join(os.getcwd(), 'storage')

    _frozen = getattr(sys, '_MEIPASS', None)
    if _frozen:
        TEMPLATE_FOLDER = os.path.join(_frozen, 'templates')
        STATIC_FOLDER = os.path.join(_frozen, 'static')
    else:
        TEMPLATE_FOLDER = os.path.abspath('templates')
        STATIC_FOLDER = os.path.abspath('static')

    APP_VERSION = '1.1.2'
    GITHUB_REPO = 'maaxim-one/auto-csv-gosveb'

    ALLOWED_ARCHIVE_EXT = {'zip'}
    ALLOWED_DOC_EXTS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.xlsx', '.xls'}
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}
    EXCEL_EXTS = {'.xlsx', '.xls'}
    XLS_EXTS = {'.xls'}

    MAX_FILENAME_BYTES = 200
    MAX_FILENAME_BYTES_NO_TRUNC = 250
    MAX_ZIP_SIZE = 90 * 1024 * 1024
    MAX_EXCEL_CONVERT = 10 * 1024 * 1024
