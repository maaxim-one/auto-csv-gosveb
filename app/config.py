import os
import sys


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    MAX_CONTENT_LENGTH = 1000 * 1024 * 1024

    STORAGE_DIR = os.path.join(os.getcwd(), 'storage')

    _frozen = getattr(sys, '_MEIPASS', None)
    if _frozen:
        TEMPLATE_FOLDER = os.path.join(_frozen, 'templates')
        STATIC_FOLDER = os.path.join(_frozen, 'static')
    else:
        TEMPLATE_FOLDER = os.path.abspath('templates')
        STATIC_FOLDER = os.path.abspath('static')

    APP_VERSION = '1.1.0'
    GITHUB_REPO = 'maaxim-one/auto-csv-gosveb'

    ALLOWED_ARCHIVE_EXT = {'zip'}
    ALLOWED_DOC_EXTS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.xlsx', '.xls'}
    IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}
    EXCEL_EXTS = {'.xlsx', '.xls'}
    XLS_EXTS = {'.xls'}

    MAX_FILENAME_BYTES = 200
    MAX_ZIP_SIZE = 90 * 1024 * 1024
