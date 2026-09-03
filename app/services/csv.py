import os
import csv
import io
import re
import logging
from datetime import datetime
from markupsafe import escape
from app.utils import is_image, truncate_filename, is_safe_path, normalize_spaces
from app.services.image import convert_image_bytes_to_pdf

logger = logging.getLogger(__name__)

_PFX_D_PHRASE = 'План финансово-хозяйственной деятельности'


def _expand_abbreviation(name: str) -> str:
    return re.sub(r'пфхд', _PFX_D_PHRASE, name, flags=re.IGNORECASE)


def get_category_from_path(path: str) -> str:
    parts = [p for p in path.replace('\\', '/').split('/') if p]
    return parts[0] if len(parts) > 1 else 'Без категории'


def parse_zip_to_csv_rows(zip_file, export_mode='school'):
    from flask import current_app
    ALLOWED_DOC_EXTS = current_app.config['ALLOWED_DOC_EXTS']

    rows = []
    skipped_files = []
    now_date = datetime.now().strftime('%d-%m-%Y')
    max_filename_bytes = 250 if export_mode == 'school' else 200

    tmp_map = {}

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
        name_no_ext, ext = os.path.splitext(file_name_only)
        if name_no_ext:
            name_no_ext = _expand_abbreviation(name_no_ext)
            name_no_ext = normalize_spaces(name_no_ext)
            name_no_ext = name_no_ext[0].upper() + name_no_ext[1:]
            file_name_only = name_no_ext + ext
        category = get_category_from_path(info.filename)
        zip_read_path = info.filename

        if is_image(file_name_only):
            file_name_only = f"{name_no_ext}.pdf"

        truncated_name = truncate_filename(file_name_only, max_filename_bytes)
        dir_part = os.path.dirname(filename_full)
        truncated_archive_path = os.path.join(dir_part, truncated_name) if dir_part else truncated_name

        key = truncated_name
        if key not in tmp_map:
            tmp_map[key] = {
                'Name': name_no_ext,
                'Number': '',
                'Regulatory': 'Да',
                'File': truncated_name,
                'ArchivePath': truncated_archive_path,
                '_zip_read_path': zip_read_path,
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
        else:
            existing = tmp_map[key]
            if category not in existing['Category'].split('|'):
                existing['Category'] = existing['Category'] + '|' + category

    rows = list(tmp_map.values())

    return rows, skipped_files


def _truncate_for_save(filename: str, max_bytes: int = 200) -> str:
    name, ext = os.path.splitext(filename)
    encoded = filename.encode('utf-8')
    if len(encoded) <= max_bytes:
        return filename
    if len(encoded) <= max_bytes - 8:
        return filename
    truncated = name
    while len((truncated + ext).encode('utf-8')) > max_bytes - 8:
        truncated = truncated[:-1]
    return truncated + ext


def extract_original_files(zip_file, data, target_dir):
    converted_files = []
    manifest = []
    skipped_excel = []
    for row in data:
        zip_read_path = row.get('_zip_read_path', row['ArchivePath'])
        archive_path = row['ArchivePath']
        file_path = os.path.join(target_dir, archive_path)

        if not is_safe_path(target_dir, file_path):
            logger.warning("Path traversal при извлечении: %s", archive_path)
            continue

        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            content = zip_file.read(zip_read_path)
            if is_image(zip_read_path):
                pdf_content = convert_image_bytes_to_pdf(content)
                pdf_path = os.path.splitext(file_path)[0] + '.pdf'
                try:
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_content)
                except OSError as e:
                    if 'File name too long' in str(e) or os.errno.ENAMETOOLONG in (e.errno if e.errno else 0, 36): # type: ignore
                        safe_name = _truncate_for_save(os.path.basename(pdf_path), 120)
                        safe_dir = os.path.dirname(pdf_path)
                        pdf_path = os.path.join(safe_dir, safe_name)
                        os.makedirs(safe_dir, exist_ok=True)
                        with open(pdf_path, 'wb') as f:
                            f.write(pdf_content)
                        row['ArchivePath'] = os.path.basename(pdf_path)
                        row['File'] = os.path.basename(pdf_path)
                        converted_files.append(os.path.basename(row.get('_zip_read_path', archive_path)))
                        logger.info("Ограничение длины имени: %s → %s", archive_path, os.path.basename(pdf_path))
                        continue
                    raise
                row['ArchivePath'] = os.path.splitext(archive_path)[0] + '.pdf'
                row['File'] = os.path.splitext(row['File'])[0] + '.pdf'
                converted_files.append(os.path.basename(zip_read_path))
                logger.info("Конвертировано в PDF: %s → %s", zip_read_path, os.path.basename(pdf_path))
            else:
                try:
                    with open(file_path, 'wb') as f:
                        f.write(content)
                except OSError as e:
                    if 'File name too long' in str(e) or os.errno.ENAMETOOLONG in (e.errno if e.errno else 0, 36): # type: ignore
                        safe_name = _truncate_for_save(os.path.basename(file_path), 120)
                        safe_dir = os.path.dirname(file_path)
                        file_path = os.path.join(safe_dir, safe_name)
                        os.makedirs(safe_dir, exist_ok=True)
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        row['ArchivePath'] = os.path.basename(file_path)
                        row['File'] = os.path.basename(file_path)
                        logger.info("Ограничение длины имени: %s → %s", archive_path, os.path.basename(file_path))
                        manifest.append({'name': os.path.basename(zip_read_path), 'from': '', 'to': '', 'status': 'done'})
                        continue
                    raise
                manifest.append({'name': os.path.basename(zip_read_path), 'from': '', 'to': '', 'status': 'done'})
                logger.info("Сохранён файл: %s → %s", zip_read_path, os.path.basename(file_path))
        except Exception as e:
            logger.error("Ошибка сохранения файла %s: %s", zip_read_path, e)

    for row in data:
        row.pop('_zip_read_path', None)

    return converted_files, manifest, skipped_excel


def render_table_preview(data, export_mode='school', manifest=None):
    if not data:
        return "<p style='color: #777; padding: 20px;'>Загрузите ZIP-архив выше, чтобы сформировать CSV.</p>"

    m = manifest or []
    html = ['<div class="table-wrapper"><table>']
    headers = ['№', 'Название', 'Файл', 'Нормативный правовой документ', 'Категория', 'Дата создания', 'Удалить']

    html.append('<thead><tr>')
    for h in headers:
        html.append(f'<th>{escape(h)}</th>')
    html.append('</tr></thead>')

    html.append('<tbody>')
    for i, row in enumerate(data):
        category = row.get('Category', '')
        skipped_excel = row.get('_skipped_excel', False)

        dis = ' disabled' if skipped_excel else ''

        html.append(f'<tr data-category="{escape(category)}" data-idx="{i}">')
        html.append(f'<td class="num-col">{i + 1}</td>')
        html.append(f'''<td class="name-col">
          <input type="text" name="name_{i}" value="{escape(row["Name"])}" placeholder="Введите название"{dis}>
        </td>''')
        checked = 'checked' if row['Regulatory'] == 'Да' else ''
        
        # File column
        file_value = row.get('File', '')
        html.append(f'''<td class="file-col">
          <input type="text" name="file_{i}" value="{escape(file_value)}" placeholder="Имя файла"{dis}>
        </td>''')
        
        html.append(f'''<td class="reg-col">
          <label class="checkbox-label">
            <input type="checkbox" name="regulatory_{i}" value="Да" {checked} class="reg-checkbox"{dis}> Да
          </label>
        </td>''')
        html.append(f'''<td class="cat-col">
          <input type="hidden" name="category_{i}" value="{escape(row["Category"])}">
          <input type="text" name="category_{i}_display" value="{escape(row["Category"])}" placeholder="Категория"{dis} readonly>
        </td>''')
        html.append(f'''<td class="date-col">
          <input type="text" name="date_created_{i}" value="{escape(row["DateCreated"])}" placeholder="ДД-ММ-ГГГГ"{dis}>
        </td>''')
        html.append(f'''<td class="delete-col" data-delete-idx="{i}">
          <button type="button" class="btn btn-delete-row" data-row-idx="{i}" title="Удалить"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
        </td>''')

        html.append('</tr>')
    html.append('</tbody></table></div>')
    return ''.join(html)


def rebuild_manifest(session_dir, data):
    import zipfile
    from app.utils import is_image, is_safe_path
    manifest = []
    missing = []

    def _simple_entry(filename):
        _, ext = os.path.splitext(filename)
        ext = ext.lstrip('.').upper()
        return {'name': os.path.basename(filename), 'from': ext, 'to': ext, 'status': 'done'}

    session_path = session_dir
    try:
        zip_path = os.path.join(session_path, 'upload.zip')
        zip_file = zipfile.ZipFile(zip_path, 'r')
    except Exception:
        zip_file = None

    for idx, row in enumerate(data):
        zip_read_path = row.get('_zip_read_path', row['ArchivePath'])
        archive_path = row['ArchivePath']
        file_path = os.path.join(session_path, archive_path)

        if not is_safe_path(session_path, file_path):
            continue

        if is_image(zip_read_path):
            pdf_path = os.path.splitext(file_path)[0] + '.pdf'
            if os.path.isfile(pdf_path):
                row['ArchivePath'] = os.path.splitext(archive_path)[0] + '.pdf'
                row['File'] = os.path.splitext(row['File'])[0] + '.pdf'
                row['_converted'] = True
                entry = _simple_entry(zip_read_path)
            else:
                entry = _simple_entry(zip_read_path)
        else:
            if not os.path.isfile(file_path):
                missing.append(archive_path)
            entry = _simple_entry(zip_read_path)

        manifest.append(entry)

    if zip_file:
        zip_file.close()

    return manifest, missing


def apply_form_changes(form, original_data, export_mode='school'):
    number_field = 'documentnumber' if export_mode == 'kindergarten' else 'number'
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
