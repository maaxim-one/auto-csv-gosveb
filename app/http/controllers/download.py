import os
import io
import json
import uuid
import zipfile
import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file, abort, jsonify
from app.utils import get_session_dir, sanitize_filename, is_safe_path, is_image, cleanup_session_directory
from app.services.job import job_read
from app.services.csv import generate_csv, apply_form_changes
from app.config import Config

logger = logging.getLogger(__name__)

download_bp = Blueprint('download', __name__)


def _get_resolved_path(row, session_path):
    archive_path_on_disk = row['ArchivePath']
    file_path_on_disk = os.path.join(session_path, archive_path_on_disk)
    if is_image(archive_path_on_disk) and not os.path.isfile(file_path_on_disk):
        pdf_path = os.path.splitext(file_path_on_disk)[0] + '.pdf'
        if os.path.isfile(pdf_path):
            file_path_on_disk = pdf_path
    return file_path_on_disk


def _build_single_zip(rows_chunk, session_path, export_mode, used_names=None):
    if used_names is None:
        used_names = set()

    csv_bytes = generate_csv(rows_chunk, export_mode)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('component_import.csv', csv_bytes)
        for row in rows_chunk:
            file_path_on_disk = _get_resolved_path(row, session_path)
            if not is_safe_path(session_path, file_path_on_disk):
                continue
            if not os.path.isfile(file_path_on_disk):
                continue
            final_arcname = sanitize_filename(row['File'])
            if final_arcname in used_names or final_arcname in zf.namelist():
                base, ext = os.path.splitext(final_arcname)
                final_arcname = f"{base}_dup{len(used_names)}{ext}"
            used_names.add(final_arcname)
            zf.write(file_path_on_disk, arcname=final_arcname)
    buf.seek(0)
    return buf


def _split_rows_by_size(rows, session_path, max_size):
    chunks = []
    current_chunk = []
    current_size = 0

    for row in rows:
        file_path = _get_resolved_path(row, session_path)
        file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0

        if current_chunk and current_size + file_size > max_size:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0

        current_chunk.append(row)
        current_size += file_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


@download_bp.route('/download_zip', methods=['POST'])
def download_zip():
    storage_dir = Config.STORAGE_DIR
    max_zip_size = Config.MAX_ZIP_SIZE

    session_id = session.get('session_id')
    if not session_id:
        flash('Сначала загрузите ZIP архив', 'error')
        return redirect(url_for('page.index'))

    excel_job_id = session.get('excel_job_id')
    if excel_job_id:
        job = job_read(excel_job_id)
        if job and job.get('status') == 'processing':
            flash('Подождите завершения конвертации Excel в PDF', 'warning')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'ok': False, 'error': 'converting'})
            return redirect(url_for('page.index'))

    session_path = get_session_dir(session_id)
    if not os.path.isdir(session_path):
        flash('Сессия устарела, загрузите архив заново', 'error')
        session.pop('session_id', None)
        return redirect(url_for('page.index'))

    json_path = os.path.join(session_path, 'data.json')
    if not os.path.exists(json_path):
        flash('Ошибка: файл данных сессии не найден', 'error')
        session.pop('session_id', None)
        return redirect(url_for('page.index'))

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Ошибка чтения JSON при скачивании: %s", e)
        flash('Ошибка чтения временных данных', 'error')
        return redirect(url_for('page.index'))

    export_mode = request.form.get('export_mode', session.get('export_mode', 'school'))
    updated_data = apply_form_changes(request.form, data, export_mode)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, ensure_ascii=False)

    download_id = uuid.uuid4().hex
    used_names = set()
    saved_files = []

    total_uncompressed = sum(
        os.path.getsize(_get_resolved_path(r, session_path))
        for r in updated_data
        if os.path.isfile(_get_resolved_path(r, session_path))
    )

    if total_uncompressed <= max_zip_size:
        zip_buf = _build_single_zip(updated_data, session_path, export_mode, used_names)
        filename = f"export_{download_id}.zip"
        filepath = os.path.join(storage_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(zip_buf.getvalue())
        saved_files.append({'filename': filename, 'size': os.path.getsize(filepath)})
    else:
        chunks = _split_rows_by_size(updated_data, session_path, max_zip_size)
        logger.info("Файл разбит на %d частей", len(chunks))
        for idx, chunk in enumerate(chunks, 1):
            zip_buf = _build_single_zip(chunk, session_path, export_mode, used_names)
            filename = f"export_{download_id}_part{idx}.zip"
            filepath = os.path.join(storage_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(zip_buf.getvalue())
            saved_files.append({'filename': filename, 'size': os.path.getsize(filepath)})

    cleanup_session_directory(session_path)
    session.pop('session_id', None)

    if len(saved_files) == 1:
        redirect_url = url_for('download.download_status', filename=saved_files[0]['filename'])
    else:
        manifest_name = f"manifest_{download_id}.json"
        manifest_path = os.path.join(storage_dir, manifest_name)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(saved_files, f, ensure_ascii=False)
        redirect_url = url_for('download.download_status', manifest=manifest_name)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'redirect': redirect_url})

    return redirect(redirect_url)


@download_bp.route('/download-status')
def download_status():
    storage_dir = Config.STORAGE_DIR

    manifest_name = request.args.get('manifest')
    filename = request.args.get('filename')

    if manifest_name:
        manifest_name = sanitize_filename(manifest_name)
        manifest_path = os.path.join(storage_dir, manifest_name)
        if not os.path.isfile(manifest_path):
            flash('Манифест скачивания не найден', 'error')
            return redirect(url_for('page.index'))
        with open(manifest_path, 'r', encoding='utf-8') as f:
            files = json.load(f)
        for item in files:
            item['size_mb'] = round(item['size'] / (1024 * 1024), 2)
        return render_template('download_status.html', files=files, manifest=manifest_name)

    if filename:
        filename = sanitize_filename(filename)
        download_path = os.path.join(storage_dir, filename)
        if not os.path.isfile(download_path):
            flash('Файл для скачивания не найден', 'error')
            return redirect(url_for('page.index'))
        size_mb = round(os.path.getsize(download_path) / (1024 * 1024), 2)
        return render_template('download_status.html', files=[{'filename': filename, 'size_mb': size_mb}], manifest=None)

    flash('Сессия скачивания истекла или неверна', 'error')
    return redirect(url_for('page.index'))


@download_bp.route('/serve_download/<filename>')
def serve_download(filename):
    storage_dir = Config.STORAGE_DIR

    filename = sanitize_filename(filename)
    download_path = os.path.join(storage_dir, filename)
    if not os.path.isfile(download_path):
        abort(404)

    try:
        return send_file(
            download_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    finally:
        try:
            os.remove(download_path)
            logger.info("Удалён временный ZIP: %s", download_path)
        except OSError as e:
            logger.warning("Не удалось удалить временный ZIP %s: %s", download_path, e)
