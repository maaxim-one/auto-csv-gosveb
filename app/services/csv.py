import os
import csv
import io
import logging
from datetime import datetime
from markupsafe import escape
from app.utils import is_image, is_excel, truncate_filename, is_safe_path
from app.services.image import convert_image_bytes_to_pdf
from app.services.excel import file_conversion_entry

logger = logging.getLogger(__name__)


def get_category_from_path(path: str) -> str:
    parts = [p for p in path.replace('\\', '/').split('/') if p]
    return parts[0] if len(parts) > 1 else 'Без категории'


def parse_zip_to_csv_rows(zip_file):
    from flask import current_app
    ALLOWED_DOC_EXTS = current_app.config['ALLOWED_DOC_EXTS']

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

        if is_image(file_name_only):
            file_name_only = f"{name_no_ext}.pdf"
        elif is_excel(file_name_only):
            file_name_only = f"{name_no_ext}.pdf"

        truncated_name = truncate_filename(file_name_only)
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


def extract_original_files(zip_file, data, target_dir, has_excel_converter=True):
    converted_files = []
    excel_files = []
    manifest = []
    skipped_excel = []
    for row in data:
        zip_read_path = row.get('_zip_read_path', row['ArchivePath'])
        archive_path = row['ArchivePath']
        file_path = os.path.join(target_dir, archive_path)

        if not is_safe_path(target_dir, file_path):
            logger.warning("Path traversal при извлечении: %s", archive_path)
            continue

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            content = zip_file.read(zip_read_path)
            if is_image(zip_read_path):
                manifest.append(file_conversion_entry(zip_read_path, 'converting'))
                pdf_content = convert_image_bytes_to_pdf(content)
                pdf_path = os.path.splitext(file_path)[0] + '.pdf'
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                row['ArchivePath'] = os.path.splitext(archive_path)[0] + '.pdf'
                row['File'] = os.path.splitext(row['File'])[0] + '.pdf'
                converted_files.append(os.path.basename(zip_read_path))
                manifest[-1]['status'] = 'done'
                logger.info("Конвертировано в PDF: %s → %s", zip_read_path, os.path.basename(pdf_path))
            elif is_excel(zip_read_path):
                if not has_excel_converter:
                    row['_skipped_excel'] = True
                    skipped_excel.append(os.path.basename(zip_read_path))
                    logger.info("Excel-файл пропущен (нет конвертера): %s", zip_read_path)
                else:
                    manifest.append(file_conversion_entry(zip_read_path, 'waiting'))
                    excel_files.append({
                        'content': content,
                        'zip_read_path': zip_read_path,
                        'archive_path': archive_path,
                        'file_path': file_path,
                        'row': row,
                        'manifest_idx': len(manifest) - 1,
                    })
            else:
                manifest.append(file_conversion_entry(zip_read_path, 'done'))
                with open(file_path, 'wb') as f:
                    f.write(content)
        except Exception as e:
            logger.error("Ошибка сохранения файла %s: %s", zip_read_path, e)

    for row in data:
        row.pop('_zip_read_path', None)

    return converted_files, excel_files, manifest, skipped_excel


def render_table_preview(data, export_mode='school', manifest=None):
    if not data:
        return "<p style='color: #777; padding: 20px;'>Загрузите ZIP-архив выше, чтобы сформировать CSV.</p>"

    m = manifest or []
    html = ['<div class="table-wrapper"><table>']
    headers = ['№', 'Название', 'Нормативный правовой документ', 'Категория', 'Дата создания', 'Конвертация']

    html.append('<thead><tr>')
    for h in headers:
        html.append(f'<th>{escape(h)}</th>')
    html.append('</tr></thead>')

    html.append('<tbody>')
    for i, row in enumerate(data):
        category = row.get('Category', '')
        entry = m[i] if i < len(m) else None
        skipped_excel = row.get('_skipped_excel', False)
        status_cls = ''
        row_cls = ' class="row-skipped-excel"' if skipped_excel else ''
        status_html = ''
        if skipped_excel:
            status_cls = ' data-convert="skipped"'
            status_html = f'''<td class="convert-col" data-idx="{i}">
              <span class="convert-badge convert-badge-skipped">Пропущено</span>
            </td>'''
        elif entry:
            status_cls = ' data-convert="' + entry['status'] + '"'
            arrow = entry['from'] + ' → ' + entry['to'] if entry['from'] != entry['to'] else entry['from']
            status_html = f'''<td class="convert-col" data-idx="{i}">
              <span class="convert-badge convert-badge-{entry['status']}">{escape(arrow)}</span>
            </td>'''
        else:
            status_html = f'<td class="convert-col" data-idx="{i}"></td>'

        html.append(f'<tr data-category="{escape(category)}" data-idx="{i}"{row_cls}{status_cls}>')
        html.append(f'<td class="num-col">{i + 1}</td>')
        html.append(f'''<td class="name-col">
          <input type="text" name="name_{i}" value="{escape(row["Name"])}" placeholder="Введите название"{' disabled' if skipped_excel else ''}>
        </td>''')
        checked = 'checked' if row['Regulatory'] == 'Да' else ''
        dis = ' disabled' if skipped_excel else ''
        html.append(f'''<td class="reg-col">
          <label class="checkbox-label">
            <input type="checkbox" name="regulatory_{i}" value="Да" {checked} class="reg-checkbox"{dis}> Да
          </label>
        </td>''')
        html.append(f'''<td class="cat-col">
          <input type="text" name="category_{i}" value="{escape(row["Category"])}" placeholder="Категория"{dis}>
        </td>''')
        html.append(f'''<td class="date-col">
          <input type="text" name="date_created_{i}" value="{escape(row["DateCreated"])}" placeholder="ДД-ММ-ГГГГ"{dis}>
        </td>''')
        html.append(status_html)

        number_field = 'documentnumber' if export_mode == 'kindergarten' else 'number'
        for field in ['Description', 'File', 'DateUpdated', 'Hypertext', 'Graphic', 'DateEDS', 'FioEDS', 'PositionEDS', 'EDS', 'ArchivePath']:
            html.append(f'<input type="hidden" name="{field.lower()}_{i}" value="{escape(row.get(field, ""))}">')
        html.append(f'<input type="hidden" name="{number_field}_{i}" value="{escape(row.get("Number", ""))}">')

        html.append('</tr>')
    html.append('</tbody></table></div>')
    return ''.join(html)


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
