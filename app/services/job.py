import os
import json
import logging

logger = logging.getLogger(__name__)


def get_storage_dir():
    from flask import current_app
    return current_app.config['STORAGE_DIR']


def job_dir(job_id: str) -> str:
    return os.path.join(get_storage_dir(), f'job_{job_id}')


def job_status_path(job_id: str) -> str:
    return os.path.join(job_dir(job_id), 'status.json')


def job_update(job_id: str, **kwargs):
    d = job_dir(job_id)
    os.makedirs(d, exist_ok=True)
    path = job_status_path(job_id)
    tmp_path = path + '.tmp'
    data = {}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
    data.update(kwargs)
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def job_read(job_id: str):
    path = job_status_path(job_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None
