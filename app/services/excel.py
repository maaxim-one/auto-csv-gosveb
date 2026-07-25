import os
import sys
import io
import json
import shutil
import tempfile
import logging

logger = logging.getLogger(__name__)


def _convert_via_ilovepdf(excel_bytes: bytes, filename: str) -> bytes:
    public_key = os.environ.get('ILOVEPDF_PUBLIC_KEY', '').strip()
    secret_key = os.environ.get('ILOVEPDF_SECRET_KEY', '').strip()
    if not public_key or not secret_key:
        return b''

    _, ext = os.path.splitext(filename)
    if ext.lower() not in ('.xlsx', '.xls'):
        return b''

    tmp_dir = tempfile.mkdtemp(prefix='ilovepdf_')
    try:
        src_path = os.path.join(tmp_dir, f'input{ext}')
        with open(src_path, 'wb') as f:
            f.write(excel_bytes)

        from ilovepdf import OfficePdfTask
        task = OfficePdfTask(public_key=public_key, secret_key=secret_key)
        task.add_file(src_path)
        task.execute()
        task.download(tmp_dir)
        task.delete()

        pdf_files = [f for f in os.listdir(tmp_dir) if f.lower().endswith('.pdf')]
        if pdf_files:
            pdf_path = os.path.join(tmp_dir, pdf_files[0])
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            if pdf_bytes and len(pdf_bytes) > 100:
                logger.info("iLovePDF конвертация: %s -> PDF (%d байт)", filename, len(pdf_bytes))
                return pdf_bytes

        logger.warning("iLovePDF не создал PDF для %s", filename)
        return b''
    except Exception as e:
        logger.warning("iLovePDF ошибка при конвертации %s: %s", filename, e)
        return b''
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _convert_via_msexcel(excel_bytes: bytes, filename: str) -> bytes:
    if sys.platform != 'win32':
        return b''

    try:
        import win32com.client
    except ImportError:
        return b''

    tmp_dir = tempfile.mkdtemp(prefix='msexcel_')
    try:
        _, ext = os.path.splitext(filename)
        ext = ext.lower() or '.xlsx'
        src_path = os.path.join(tmp_dir, f'input{ext}')
        pdf_path = os.path.join(tmp_dir, 'output.pdf')

        with open(src_path, 'wb') as f:
            f.write(excel_bytes)

        excel = None
        wb = None
        try:
            excel = win32com.client.Dispatch('Excel.Application')
            excel.Visible = False
            excel.DisplayAlerts = False

            wb = excel.Workbooks.Open(os.path.abspath(src_path), ReadOnly=True)
            wb.Sheets.Select()
            for ws in wb.Worksheets:
                ps = ws.PageSetup
                ps.Orientation = 1
                ps.PaperSize = 9
            wb.ExportAsFixedFormat(
                Type=0,
                Filename=os.path.abspath(pdf_path),
                Quality=0,
                IncludeDocProperties=True,
                IgnorePrintAreas=False,
                OpenAfterPublish=False,
            )
        finally:
            if wb:
                wb.Close(SaveChanges=False)
            if excel:
                excel.Quit()

        if os.path.isfile(pdf_path):
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            if pdf_bytes and len(pdf_bytes) > 100:
                logger.info("MS Excel конвертация: %s -> PDF (%d байт)", filename, len(pdf_bytes))
                return pdf_bytes

        logger.warning("MS Excel не создал PDF для %s", filename)
        return b''
    except Exception as e:
        logger.warning("MS Excel ошибка при конвертации %s: %s", filename, e)
        return b''
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def detect_engines():
    engines = []
    public_key = os.environ.get('ILOVEPDF_PUBLIC_KEY', '').strip()
    secret_key = os.environ.get('ILOVEPDF_SECRET_KEY', '').strip()
    if public_key and secret_key:
        engines.append('iLovePDF')

    if sys.platform == 'win32':
        try:
            import win32com.client
            engines.append('MS Excel')
        except ImportError:
            pass

    if not engines:
        engines.append('Нет конвертеров Excel → PDF')
    return engines


def convert_excel_bytes_to_pdf(excel_bytes: bytes, filename: str = '') -> bytes:
    lo_pdf = _convert_via_ilovepdf(excel_bytes, filename)
    if lo_pdf:
        return lo_pdf

    lo_pdf = _convert_via_msexcel(excel_bytes, filename)
    if lo_pdf:
        return lo_pdf

    logger.error("Все конвертеры не смогли обработать %s", filename)
    return b''


def file_conversion_entry(filename, status):
    _, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip('.')
    if ext in ('png', 'jpg', 'jpeg'):
        return {'name': os.path.basename(filename), 'from': ext.upper(), 'to': 'PDF', 'status': status}
    elif ext in ('xlsx', 'xls'):
        return {'name': os.path.basename(filename), 'from': ext.upper(), 'to': 'PDF', 'status': status}
    else:
        return {'name': os.path.basename(filename), 'from': ext.upper(), 'to': ext.upper(), 'status': status}


def _do_convert(job_id, session_path, json_path, excel_items, data):
    from app.services.job import job_read, job_update

    if sys.platform == 'win32':
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

    logger.info("Фоновая конвертация %s: %d файлов", job_id, len(excel_items))
    converted_files = []
    try:
        for idx, item in enumerate(excel_items):
            manifest_idx = item.get('manifest_idx')
            try:
                logger.info("Конвертация [%d/%d]: %s", idx + 1, len(excel_items), item['zip_read_path'])

                if manifest_idx is not None:
                    job = job_read(job_id)
                    if job and 'manifest' in job:
                        job['manifest'][manifest_idx]['status'] = 'converting'
                        job_update(job_id, manifest=job['manifest'])

                pdf_content = convert_excel_bytes_to_pdf(item['content'], item['zip_read_path'])
                pdf_path = os.path.splitext(item['file_path'])[0] + '.pdf'
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_content)
                item['row']['ArchivePath'] = os.path.splitext(item['archive_path'])[0] + '.pdf'
                item['row']['File'] = os.path.splitext(item['row']['File'])[0] + '.pdf'
                converted_files.append(os.path.basename(item['zip_read_path']))
                logger.info("Готово [%d/%d]: %s", idx + 1, len(excel_items), item['zip_read_path'])

                if manifest_idx is not None:
                    job = job_read(job_id)
                    if job and 'manifest' in job:
                        job['manifest'][manifest_idx]['status'] = 'done'
                        done_count = sum(1 for e in job['manifest'] if e['status'] == 'done')
                        job_update(job_id, manifest=job['manifest'], progress=done_count)
            except Exception as e:
                logger.error("Ошибка конвертации %s: %s", item['zip_read_path'], e)
                if manifest_idx is not None:
                    job = job_read(job_id)
                    if job and 'manifest' in job:
                        job['manifest'][manifest_idx]['status'] = 'error'
                        done_count = sum(1 for e in job['manifest'] if e['status'] == 'done')
                        job_update(job_id, manifest=job['manifest'], progress=done_count)

        tmp_json = json_path + '.tmp'
        with open(tmp_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_json, json_path)

        job_update(job_id, status='done')
        logger.info("Фоновая конвертация %s завершена", job_id)
    except Exception as e:
        logger.error("Фатальная ошибка фоновой конвертации: %s", e)
        job_update(job_id, status='error', error=str(e))
    finally:
        if sys.platform == 'win32':
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass


def background_convert_excel(job_id, session_path, json_path, excel_items, data, app):
    def _run():
        with app.app_context():
            _do_convert(job_id, session_path, json_path, excel_items, data)

    _run()
