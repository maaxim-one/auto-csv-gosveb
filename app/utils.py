import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_storage_dir():
    from flask import current_app
    return current_app.config['STORAGE_DIR']


def get_session_dir(session_id: str) -> str:
    return os.path.join(get_storage_dir(), session_id)


def sanitize_filename(filename: str) -> str:
    return os.path.basename(filename)


def is_safe_path(base: str, target: str) -> bool:
    resolved = os.path.realpath(target)
    return resolved.startswith(os.path.realpath(base))


def allowed_archive(filename: str) -> bool:
    from flask import current_app
    exts = current_app.config['ALLOWED_ARCHIVE_EXT']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in exts


def is_image(filename: str) -> bool:
    from flask import current_app
    exts = current_app.config['IMAGE_EXTS']
    _, ext = os.path.splitext(filename)
    return ext.lower() in exts


def is_excel(filename: str) -> bool:
    from flask import current_app
    exts = current_app.config['EXCEL_EXTS']
    _, ext = os.path.splitext(filename)
    return ext.lower() in exts


def truncate_filename(filename: str) -> str:
    from flask import current_app
    max_bytes = current_app.config['MAX_FILENAME_BYTES']
    name, ext = os.path.splitext(filename)
    if len(filename.encode('utf-8')) <= max_bytes:
        return filename
    truncated = name
    while len((truncated + ext).encode('utf-8')) > max_bytes - 8:
        truncated = truncated[:-1]
    return truncated + ext


def cleanup_session_directory(session_path: str):
    if os.path.isdir(session_path):
        try:
            shutil.rmtree(session_path)
            logger.info("Полностью удалена папка сессии: %s", session_path)
        except OSError as e:
            logger.warning("Не удалось удалить папку сессии %s: %s", session_path, e)


def cleanup_stale_temp_files(max_age_hours: int = 24):
    from flask import current_app
    storage = current_app.config['STORAGE_DIR']
    if not os.path.isdir(storage):
        return
    now = datetime.now().timestamp()
    for filename in os.listdir(storage):
        filepath = os.path.join(storage, filename)
        try:
            age_hours = (now - os.path.getmtime(filepath)) / 3600
            if age_hours > max_age_hours:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    logger.info("Удалён устаревший temp-файл: %s", filepath)
                elif os.path.isdir(filepath):
                    shutil.rmtree(filepath, ignore_errors=True)
                    logger.info("Удалена устаревшая папка: %s", filepath)
        except OSError:
            pass
