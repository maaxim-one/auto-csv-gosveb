import os
import io
import json
import uuid
import shutil
import zipfile
import logging
import threading
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, get_flashed_messages, jsonify, current_app
from app.utils import get_session_dir, allowed_archive
from app.services.job import job_update, job_read
from app.services.csv import parse_zip_to_csv_rows, extract_original_files, render_table_preview
from app.services.excel import background_convert_excel, detect_engines
from app.config import Config

logger = logging.getLogger(__name__)

page_bp = Blueprint('page', __name__)


@page_bp.route('/', methods=['GET'])
def index():
    preview_html = ""
    total_count = 0
    messages = get_flashed_messages(with_categories=True)

    export_mode = session.get('export_mode', 'school')
    categories = []

    excel_job_id = session.get('excel_job_id')
    converting = False
    manifest = []
    if excel_job_id:
        job = job_read(excel_job_id)
        if job and job.get('status') == 'processing':
            converting = True
            manifest = job.get('manifest', [])
        elif job and job.get('status') == 'done':
            manifest = job.get('manifest', [])
            session.pop('excel_job_id', None)

    session_id = session.get('session_id')
    if session_id:
        session_path = get_session_dir(session_id)
        if os.path.isdir(session_path):
            json_path = os.path.join(session_path, 'data.json')
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    total_count = len(data)
                    categories = sorted(set(row.get('Category', '') for row in data if row.get('Category')))
                    preview_html = render_table_preview(data, export_mode, manifest)
                except Exception as e:
                    logger.error("Ошибка чтения JSON: %s", e)
                    session.pop('session_id', None)
                    flash('Данные сессии повреждены, загрузите архив заново', 'error')

    app_version = Config.APP_VERSION
    engines = detect_engines()
    github_repo = Config.GITHUB_REPO

    return render_template('index.html', preview_html=preview_html, total_count=total_count, messages=messages, export_mode=export_mode, categories=categories, converting=converting, excel_job_id=excel_job_id if converting else None, app_version=app_version, engines=engines, github_repo=github_repo)


@page_bp.route('/upload', methods=['POST'])
def upload():
    if 'archive' not in request.files:
        flash('Нет файла архива', 'error')
        return redirect(url_for('page.index'))

    file = request.files['archive']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('page.index'))

    if not allowed_archive(file.filename):
        flash('Разрешён только ZIP архив', 'error')
        return redirect(url_for('page.index'))

    export_mode = request.form.get('export_mode', 'school')
    if export_mode not in ('school', 'kindergarten'):
        export_mode = 'school'
    session['export_mode'] = export_mode

    old_session_id = session.get('session_id')
    if old_session_id:
        old_path = get_session_dir(old_session_id)
        if os.path.isdir(old_path):
            shutil.rmtree(old_path, ignore_errors=True)

    zip_data = file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            data, skipped_files = parse_zip_to_csv_rows(z)

            session_id = f"sess_{uuid.uuid4().hex[:8]}"
            session_path = get_session_dir(session_id)
            os.makedirs(session_path, exist_ok=True)

            engines = detect_engines()
            has_excel_converter = engines[0] != 'Нет конвертеров Excel → PDF'
            converted_files, excel_items, manifest, skipped_excel = extract_original_files(z, data, session_path, has_excel_converter=has_excel_converter)

        total_count = len(data)
        if skipped_files:
            names = ', '.join(skipped_files)
            flash(f'Пропущены файлы ({len(skipped_files)}): {names}. Поддерживаются только PDF, Word, Excel и изображения', 'warning')

        if skipped_excel:
            names = ', '.join(skipped_excel)
            flash(f'Excel-файлы пропущены ({len(skipped_excel)}): {names}. Нет доступного конвертера Excel → PDF', 'warning')

        if converted_files:
            count = len(converted_files)
            if count <= 3:
                names = ', '.join(converted_files)
                flash(f'Конвертированы в PDF ({count}): {names}', 'success')
            else:
                flash(f'Конвертированы в PDF ({count} файлов)', 'success')

        json_path = os.path.join(session_path, 'data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        session['session_id'] = session_id

        need_conversion = any(e['status'] in ('waiting', 'converting') for e in manifest)
        excel_job_id = None
        if need_conversion:
            excel_job_id = uuid.uuid4().hex
            job_update(excel_job_id,
                status='processing',
                total=len(manifest),
                progress=sum(1 for e in manifest if e['status'] == 'done'),
                manifest=manifest,
                error=None,
            )
            session['excel_job_id'] = excel_job_id
            if excel_items:
                t = threading.Thread(
                    target=background_convert_excel,
                    args=(excel_job_id, session_path, json_path, excel_items, data, current_app._get_current_object()),
                    daemon=True,
                )
                t.start()
            else:
                job_update(excel_job_id, status='done')

        preview_html = render_table_preview(data, export_mode, manifest)
        categories = sorted(set(row.get('Category', '') for row in data if row.get('Category')))
        messages = get_flashed_messages(with_categories=True)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'ok': True,
                'preview_html': preview_html,
                'total_count': total_count,
                'export_mode': export_mode,
                'categories': categories,
                'messages': [{'category': c, 'text': t} for c, t in messages],
                'excel_job_id': excel_job_id,
                'manifest': manifest,
            })

        return render_template(
            'index.html',
            preview_html=preview_html,
            total_count=total_count,
            messages=messages,
            export_mode=export_mode,
            categories=categories,
            app_version=Config.APP_VERSION,
            engines=detect_engines(),
            github_repo=Config.GITHUB_REPO,
        )
    except zipfile.BadZipFile:
        flash('Некорректный ZIP архив', 'error')
        return redirect(url_for('page.index'))


@page_bp.route('/clear', methods=['POST'])
def clear_session():
    session_id = session.get('session_id')
    if session_id:
        session_path = get_session_dir(session_id)
        if os.path.isdir(session_path):
            shutil.rmtree(session_path, ignore_errors=True)
            logger.info("Очищена папка сессии: %s", session_path)
    session.pop('session_id', None)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})

    return redirect(url_for('page.index'))
