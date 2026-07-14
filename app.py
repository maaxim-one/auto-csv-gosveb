import os
import sys
import csv
import io
import json
import logging
import zipfile
import shutil
import uuid
import tempfile
from datetime import datetime
from PIL import Image
from markupsafe import escape
from flask import (
    Flask, render_template, request, send_file,
    flash, get_flashed_messages, session, redirect, url_for, abort, jsonify
)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

if hasattr(sys, "_MEIPASS"):
    template_folder = os.path.join(sys._MEIPASS, "templates")  # type: ignore[attr-defined]
else:
    template_folder = os.path.abspath("templates")

if hasattr(sys, "_MEIPASS"):
    static_folder = os.path.join(sys._MEIPASS, "static")  # type: ignore[attr-defined]
else:
    static_folder = os.path.abspath("static")

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32).hex())
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024

ALLOWED_ARCHIVE_EXT = {'zip'}
ALLOWED_DOC_EXTS = {'.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}

TEMP_DIR = os.path.join(os.getcwd(), 'temp_data')
os.makedirs(TEMP_DIR, exist_ok=True)


def _get_session_dir(session_id: str) -> str:
    return os.path.join(TEMP_DIR, session_id)


def _sanitize_filename(filename: str) -> str:
    return os.path.basename(filename)


def _is_safe_path(base: str, target: str) -> bool:
    resolved = os.path.realpath(target)
    return resolved.startswith(os.path.realpath(base))


def allowed_archive(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_ARCHIVE_EXT


MAX_FILENAME_BYTES = 200


def _is_image(filename: str) -> bool:
    _, ext = os.path.splitext(filename)
    return ext.lower() in IMAGE_EXTS


def _truncate_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    if len(filename.encode('utf-8')) <= MAX_FILENAME_BYTES:
        return filename
    truncated = name
    while len((truncated + ext).encode('utf-8')) > MAX_FILENAME_BYTES - 8:
        truncated = truncated[:-1]
    return truncated + ext


def _convert_image_bytes_to_pdf(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format='PDF')
    return pdf_bytes.getvalue()


@app.route('/', methods=['GET'])
def index():
    preview_html = ""
    total_count = 0
    messages = get_flashed_messages(with_categories=True)

    export_mode = session.get('export_mode', 'school')
    categories = []
    session_id = session.get('session_id')
    if session_id:
        session_path = _get_session_dir(session_id)
        if os.path.isdir(session_path):
            json_path = os.path.join(session_path, 'data.json')
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    total_count = len(data)
                    categories = sorted(set(row.get('Category', '') for row in data if row.get('Category')))
                    preview_html = render_table_preview(data, export_mode)
                except Exception as e:
                    logger.error("Ошибка чтения JSON: %s", e)
                    session.pop('session_id', None)
                    flash('Данные сессии повреждены, загрузите архив заново', 'error')

    return render_template('index.html', preview_html=preview_html, total_count=total_count, messages=messages, export_mode=export_mode, categories=categories)


@app.route('/upload', methods=['POST'])
def upload():
    if 'archive' not in request.files:
        flash('Нет файла архива', 'error')
        return redirect(url_for('index'))

    file = request.files['archive']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('index'))

    if not allowed_archive(file.filename): # type: ignore
        flash('Разрешён только ZIP архив', 'error')
        return redirect(url_for('index'))

    export_mode = request.form.get('export_mode', 'school')
    if export_mode not in ('school', 'kindergarten'):
        export_mode = 'school'
    session['export_mode'] = export_mode

    old_session_id = session.get('session_id')
    if old_session_id:
        old_path = _get_session_dir(old_session_id)
        if os.path.isdir(old_path):
            shutil.rmtree(old_path, ignore_errors=True)

    zip_data = file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
            data, skipped_files = parse_zip_to_csv_rows(z)

            session_id = f"sess_{uuid.uuid4().hex[:8]}"
            session_path = _get_session_dir(session_id)
            os.makedirs(session_path, exist_ok=True)

            extract_original_files(z, data, session_path)

        total_count = len(data)
        if skipped_files:
            names = ', '.join(skipped_files)
            flash(f'Пропущены файлы ({len(skipped_files)}): {names}. Поддерживаются только PDF и Word', 'warning')

        json_path = os.path.join(session_path, 'data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        session['session_id'] = session_id
        preview_html = render_table_preview(data, export_mode)
        categories = sorted(set(row.get('Category', '') for row in data if row.get('Category')))
        messages = get_flashed_messages(with_categories=True)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'ok': True,
                'preview_html': preview_html,
                'total_count': total_count,
                'export_mode': export_mode,
                'categories': categories,
                'messages': [{'category': c, 'text': t} for c, t in messages]
            })

        return render_template(
            'index.html',
            preview_html=preview_html,
            total_count=total_count,
            messages=messages,
            export_mode=export_mode,
            categories=categories
        )
    except zipfile.BadZipFile:
        flash('Некорректный ZIP архив', 'error')
        return redirect(url_for('index'))


MAX_ZIP_SIZE = 90 * 1024 * 1024


def _get_resolved_path(row, session_path):
    archive_path_on_disk = row['ArchivePath']
    file_path_on_disk = os.path.join(session_path, archive_path_on_disk)
    if _is_image(archive_path_on_disk) and not os.path.isfile(file_path_on_disk):
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
            if not _is_safe_path(session_path, file_path_on_disk):
                continue
            if not os.path.isfile(file_path_on_disk):
                continue
            final_arcname = _sanitize_filename(row['File'])
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


@app.route('/download_zip', methods=['POST'])
def download_zip():
    session_id = session.get('session_id')
    if not session_id:
        flash('Сначала загрузите ZIP архив', 'error')
        return redirect(url_for('index'))

    session_path = _get_session_dir(session_id)
    if not os.path.isdir(session_path):
        flash('Сессия устарела, загрузите архив заново', 'error')
        session.pop('session_id', None)
        return redirect(url_for('index'))

    json_path = os.path.join(session_path, 'data.json')
    if not os.path.exists(json_path):
        flash('Ошибка: файл данных сессии не найден', 'error')
        session.pop('session_id', None)
        return redirect(url_for('index'))

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Ошибка чтения JSON при скачивании: %s", e)
        flash('Ошибка чтения временных данных', 'error')
        return redirect(url_for('index'))

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

    if total_uncompressed <= MAX_ZIP_SIZE:
        zip_buf = _build_single_zip(updated_data, session_path, export_mode, used_names)
        filename = f"export_{download_id}.zip"
        filepath = os.path.join(TEMP_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(zip_buf.getvalue())
        saved_files.append({'filename': filename, 'size': os.path.getsize(filepath)})
    else:
        chunks = _split_rows_by_size(updated_data, session_path, MAX_ZIP_SIZE)
        logger.info("Файл разбит на %d частей", len(chunks))
        for idx, chunk in enumerate(chunks, 1):
            zip_buf = _build_single_zip(chunk, session_path, export_mode, used_names)
            filename = f"export_{download_id}_part{idx}.zip"
            filepath = os.path.join(TEMP_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(zip_buf.getvalue())
            saved_files.append({'filename': filename, 'size': os.path.getsize(filepath)})

    cleanup_session_directory(session_path)
    session.pop('session_id', None)

    if len(saved_files) == 1:
        redirect_url = url_for('download_status', filename=saved_files[0]['filename'])
    else:
        manifest_name = f"manifest_{download_id}.json"
        manifest_path = os.path.join(TEMP_DIR, manifest_name)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(saved_files, f, ensure_ascii=False)
        redirect_url = url_for('download_status', manifest=manifest_name)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True, 'redirect': redirect_url})

    return redirect(redirect_url)


@app.route('/download-status')
def download_status():
    manifest_name = request.args.get('manifest')
    filename = request.args.get('filename')

    if manifest_name:
        manifest_name = _sanitize_filename(manifest_name)
        manifest_path = os.path.join(TEMP_DIR, manifest_name)
        if not os.path.isfile(manifest_path):
            flash('Манифест скачивания не найден', 'error')
            return redirect(url_for('index'))
        with open(manifest_path, 'r', encoding='utf-8') as f:
            files = json.load(f)
        for item in files:
            item['size_mb'] = round(item['size'] / (1024 * 1024), 2)
        return render_template('download_status.html', files=files, manifest=manifest_name)

    if filename:
        filename = _sanitize_filename(filename)
        download_path = os.path.join(TEMP_DIR, filename)
        if not os.path.isfile(download_path):
            flash('Файл для скачивания не найден', 'error')
            return redirect(url_for('index'))
        size_mb = round(os.path.getsize(download_path) / (1024 * 1024), 2)
        return render_template('download_status.html', files=[{'filename': filename, 'size_mb': size_mb}], manifest=None)

    flash('Сессия скачивания истекла или неверна', 'error')
    return redirect(url_for('index'))


@app.route('/serve_download/<filename>')
def serve_download(filename):
    filename = _sanitize_filename(filename)
    download_path = os.path.join(TEMP_DIR, filename)
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


def cleanup_session_directory(session_path: str):
    if os.path.isdir(session_path):
        try:
            shutil.rmtree(session_path)
            logger.info("Полностью удалена папка сессии: %s", session_path)
        except OSError as e:
            logger.warning("Не удалось удалить папку сессии %s: %s", session_path, e)


def cleanup_stale_temp_files(max_age_hours: int = 24):
    now = datetime.now().timestamp()
    for filename in os.listdir(TEMP_DIR):
        filepath = os.path.join(TEMP_DIR, filename)
        if os.path.isfile(filepath):
            try:
                age_hours = (now - os.path.getmtime(filepath)) / 3600
                if age_hours > max_age_hours:
                    os.remove(filepath)
                    logger.info("Удалён устаревший temp-файл: %s", filepath)
            except OSError:
                pass


def parse_zip_to_csv_rows(zip_file: zipfile.ZipFile):
    rows = []
    skipped_files = []
    now_date = datetime.now().strftime('%d-%m-%Y')

    for info in zip_file.infolist():
        if info.is_dir() or info.filename.startswith('__MACOSX/'):
            continue

        filename_full = info.filename
        _, ext = os.path.splitext(filename_full)
        ext_lower = ext.lower()
        if ext_lower not in ALLOWED_DOC_EXTS:
            skipped_files.append(os.path.basename(filename_full))
            continue

        file_name_only = os.path.basename(filename_full)
        name_no_ext = os.path.splitext(file_name_only)[0]
        if name_no_ext:
            name_no_ext = name_no_ext[0].upper() + name_no_ext[1:]
        category = get_category_from_path(info.filename)

        if _is_image(file_name_only):
            file_name_only = f"{name_no_ext}.pdf"

        truncated_name = _truncate_filename(file_name_only)
        dir_part = os.path.dirname(filename_full)
        truncated_archive_path = os.path.join(dir_part, truncated_name) if dir_part else truncated_name

        row = {
            'Name': name_no_ext,
            'Number': '',
            'Regulatory': 'Да',
            'File': truncated_name,
            'ArchivePath': truncated_archive_path,
            '_zip_read_path': filename_full,
            'Description': '',
            'Category': category,
            'DateCreated': now_date,
            'DateUpdated': '',
            'Hypertext': '',
            'Graphic': '',
            'DateEDS': '',
            'FioEDS': '',
            'PositionEDS': '',
            'EDS': ''
        }
        rows.append(row)

    return rows, skipped_files


def extract_original_files(zip_file: zipfile.ZipFile, data, target_dir: str):
    for row in data:
        zip_read_path = row.get('_zip_read_path', row['ArchivePath'])
        archive_path = row['ArchivePath']
        file_path = os.path.join(target_dir, archive_path)

        if not _is_safe_path(target_dir, file_path):
            logger.warning("Path traversal при извлечении: %s", archive_path)
            continue

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            content = zip_file.read(zip_read_path)
            if _is_image(zip_read_path):
                pdf_content = _convert_image_bytes_to_pdf(content)
                pdf_path = os.path.splitext(file_path)[0] + '.pdf'
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                row['ArchivePath'] = os.path.splitext(archive_path)[0] + '.pdf'
                row['File'] = os.path.splitext(row['File'])[0] + '.pdf'
                logger.info("Конвертировано в PDF: %s → %s", zip_read_path, os.path.basename(pdf_path))
            else:
                with open(file_path, 'wb') as f:
                    f.write(content)
        except Exception as e:
            logger.error("Ошибка сохранения файла %s: %s", zip_read_path, e)

    for row in data:
        row.pop('_zip_read_path', None)


def get_category_from_path(path: str) -> str:
    parts = [p for p in path.replace('\\', '/').split('/') if p]
    return parts[0] if len(parts) > 1 else 'Без категории'


def render_table_preview(data, export_mode='school'):
    if not data:
        return "<p style='color: #777; padding: 20px;'>Загрузите ZIP архив, чтобы увидеть предпросмотр данных.</p>"

    html = ['<div class="table-wrapper"><table>']
    headers = ['№', 'Название', 'Нормативный правовой документ', 'Категория', 'Дата создания']

    html.append('<thead><tr>')
    for h in headers:
        html.append(f'<th>{escape(h)}</th>')
    html.append('</tr></thead>')

    html.append('<tbody>')
    for i, row in enumerate(data):
        category = row.get('Category', '')
        html.append(f'<tr data-category="{escape(category)}">')
        html.append(f'<td class="num-col">{i + 1}</td>')
        html.append(f'''<td class="name-col">
          <input type="text" name="name_{i}" value="{escape(row["Name"])}" placeholder="Введите название">
        </td>''')
        checked = 'checked' if row['Regulatory'] == 'Да' else ''
        html.append(f'''<td class="reg-col">
          <label class="checkbox-label">
            <input type="checkbox" name="regulatory_{i}" value="Да" {checked} class="reg-checkbox"> Да
          </label>
        </td>''')
        html.append(f'''<td class="cat-col">
          <input type="text" name="category_{i}" value="{escape(row["Category"])}" placeholder="Категория">
        </td>''')
        html.append(f'''<td class="date-col">
          <input type="text" name="date_created_{i}" value="{escape(row["DateCreated"])}" placeholder="ДД-ММ-ГГГГ">
        </td>''')

        number_field = 'documentnumber' if export_mode == 'kindergarten' else 'number'
        for field in ['Description', 'File', 'DateUpdated', 'Hypertext', 'Graphic', 'DateEDS', 'FioEDS', 'PositionEDS', 'EDS', 'ArchivePath']:
            html.append(f'<input type="hidden" name="{field.lower()}_{i}" value="{escape(row.get(field, ""))}">')
        html.append(f'<input type="hidden" name="{number_field}_{i}" value="{escape(row.get("Number", ""))}">')

        html.append('</tr>')
    html.append('</tbody></table></div>')
    return ''.join(html)


def apply_form_changes(form, original_data, export_mode='school'):
    number_field = f'documentnumber' if export_mode == 'kindergarten' else 'number'
    updated = []
    for i, row in enumerate(original_data):
        new_name = form.get(f'name_{i}', row['Name'])
        if new_name:
            new_name = new_name[0].upper() + new_name[1:]
        reg_key = f'regulatory_{i}'
        new_reg = 'Да' if reg_key in form else 'Нет'
        new_category = form.get(f'category_{i}', row['Category'])
        new_date_created = form.get(f'date_created_{i}', row['DateCreated'])
        new_number = form.get(f'{number_field}_{i}', row['Number'])

        row['Name'] = new_name
        row['Regulatory'] = new_reg
        row['Category'] = new_category
        row['DateCreated'] = new_date_created
        row['Number'] = new_number
        updated.append(row)
    return updated


def generate_csv(data, export_mode='school'):
    output = io.StringIO(newline='')
    number_col = 'DocumentNumber' if export_mode == 'kindergarten' else 'Number'
    fieldnames = [
        'Name', number_col, 'Regulatory', 'File', 'Description', 'Category',
        'DateCreated', 'DateUpdated', 'Hypertext', 'Graphic', 'DateEDS',
        'FioEDS', 'PositionEDS', 'EDS'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for row in data:
        filtered_row = {k: row.get('Number', '') if k == number_col else row.get(k, '') for k in fieldnames}
        writer.writerow(filtered_row)

    return output.getvalue().encode('utf-8-sig')


if __name__ == '__main__':
    cleanup_stale_temp_files()
    app.run(host='0.0.0.0', port=5000, debug=True)
