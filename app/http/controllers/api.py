import json
import logging
import urllib.request
import urllib.error
from packaging.version import Version
from flask import Blueprint, request, jsonify
from app.services.job import job_read
from app.config import Config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/convert_status/<job_id>', methods=['GET'])
def convert_status(job_id):
    job = job_read(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    manifest = job.get('manifest', [])
    done_count = sum(1 for e in manifest if e['status'] == 'done')
    return jsonify({
        'status': job.get('status', 'processing'),
        'total': job.get('total', 0),
        'progress': done_count,
        'manifest': manifest,
        'error': job.get('error'),
    })


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
