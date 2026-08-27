import json
import logging
import os
import urllib.request
import urllib.error
from packaging.version import Version
from flask import Blueprint, request, jsonify, session
from app.utils import get_session_dir
from app.config import Config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/remove_row', methods=['POST'])
def remove_row():
    """Удаляет строку (файл) из списка."""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'ok': False, 'error': 'Нет активных данных'}), 400

    idx = request.json.get('idx')
    if idx is None:
        return jsonify({'ok': False, 'error': 'Не указан idx'}), 400

    session_path = get_session_dir(session_id)
    json_path = os.path.join(session_path, 'data.json')

    if not os.path.exists(json_path):
        return jsonify({'ok': False, 'error': 'Файл данных не найден'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if idx < 0 or idx >= len(data):
        return jsonify({'ok': False, 'error': 'Неверный idx'}), 400

    row = data[idx]
    archive_path = row.get('ArchivePath', '')
    file_path = os.path.join(session_path, archive_path)
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning("Не удалось удалить файл %s: %s", file_path, e)

    pdf_path = os.path.splitext(file_path)[0] + '.pdf'
    if os.path.isfile(pdf_path):
        try:
            os.remove(pdf_path)
        except OSError as e:
            logger.warning("Не удалось удалить PDF %s: %s", file_path, e)

    data.pop(idx)

    tmp_json = json_path + '.tmp'
    with open(tmp_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_json, json_path)

    return jsonify({'ok': True})


@api_bp.route('/api/remove_rows', methods=['POST'])
def remove_rows():
    """Массовое удаление строк по списку индексов."""
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'ok': False, 'error': 'Нет активных данных'}), 400

    indices = request.json.get('indices', [])
    if not indices:
        return jsonify({'ok': False, 'error': 'Нет индексов'}), 400

    session_path = get_session_dir(session_id)
    json_path = os.path.join(session_path, 'data.json')

    if not os.path.exists(json_path):
        return jsonify({'ok': False, 'error': 'Файл данных не найден'}), 404

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Удаляем в обратном порядке чтобы индексы не сбились
    for idx in sorted(indices, reverse=True):
        if idx < 0 or idx >= len(data):
            continue
        row = data[idx]
        archive_path = row.get('ArchivePath', '')
        file_path = os.path.join(session_path, archive_path)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        pdf_path = os.path.splitext(file_path)[0] + '.pdf'
        if os.path.isfile(pdf_path):
            try:
                os.remove(pdf_path)
            except OSError:
                pass
        data.pop(idx)

    tmp_json = json_path + '.tmp'
    with open(tmp_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_json, json_path)

    return jsonify({'ok': True})


@api_bp.route('/api/version')
def api_version():
    result = {'current': Config.APP_VERSION, 'latest': None, 'url': None, 'update': False}
    try:
        api_url = f'https://api.github.com/repos/{Config.GITHUB_REPO}/releases/latest'
        req = urllib.request.Request(api_url, headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'auto-csv'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get('tag_name', '').lstrip('v')
            result['latest'] = tag
            result['url'] = data.get('html_url', '')
            try:
                result['update'] = Version(tag) > Version(Config.APP_VERSION)
            except Exception:
                result['update'] = tag != Config.APP_VERSION
    except Exception as e:
        logger.debug("Version check failed: %s", e)
    return jsonify(result)


@api_bp.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': Config.APP_VERSION}), 200
