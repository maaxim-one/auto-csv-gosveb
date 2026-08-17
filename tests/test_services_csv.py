import io
import os
import zipfile
import pytest
from app.services.csv import (
    generate_csv,
    apply_form_changes,
    render_table_preview,
    parse_zip_to_csv_rows,
    get_category_from_path,
    _expand_abbreviation,
)


def test_expand_abbreviation():
    assert _expand_abbreviation('пфхд') == 'План финансово-хозяйственной деятельности'
    assert _expand_abbreviation('ПФХД') == 'План финансово-хозяйственной деятельности'
    assert _expand_abbreviation('Пфхд 2025') == 'План финансово-хозяйственной деятельности 2025'
    assert _expand_abbreviation('смета пфхд') == 'смета План финансово-хозяйственной деятельности'
    assert _expand_abbreviation('отчёт') == 'отчёт'


def _make_sample_data(export_mode='school'):
    return [
        {
            'Name': 'Doc1',
            'Number': '001',
            'Regulatory': 'Да',
            'File': 'doc1.pdf',
            'ArchivePath': 'cat1/doc1.pdf',
            'Description': '',
            'Category': 'cat1',
            'DateCreated': '25-07-2026',
            'DateUpdated': '',
            'Hypertext': '',
            'Graphic': '',
            'DateEDS': '',
            'FioEDS': '',
            'PositionEDS': '',
            'EDS': '',
        },
        {
            'Name': 'Doc2',
            'Number': '002',
            'Regulatory': 'Нет',
            'File': 'doc2.docx',
            'ArchivePath': 'cat2/doc2.docx',
            'Description': '',
            'Category': 'cat2',
            'DateCreated': '25-07-2026',
            'DateUpdated': '',
            'Hypertext': '',
            'Graphic': '',
            'DateEDS': '',
            'FioEDS': '',
            'PositionEDS': '',
            'EDS': '',
        },
    ]


def test_generate_csv_school():
    data = _make_sample_data()
    csv_bytes = generate_csv(data, export_mode='school')
    assert isinstance(csv_bytes, bytes)
    text = csv_bytes.decode('utf-8-sig')
    assert 'Name;Number;Regulatory' in text
    assert 'Doc1' in text
    assert '001' in text


def test_generate_csv_kindergarten():
    data = _make_sample_data()
    csv_bytes = generate_csv(data, export_mode='kindergarten')
    text = csv_bytes.decode('utf-8-sig')
    assert 'Name;DocumentNumber;Regulatory' in text
    assert 'Doc1' in text


def test_generate_csv_empty():
    csv_bytes = generate_csv([], export_mode='school')
    text = csv_bytes.decode('utf-8-sig')
    assert 'Name' in text


def test_apply_form_changes():
    data = _make_sample_data()
    form = {
        'name_0': 'NewName',
        'regulatory_0': 'Да',
        'category_0': 'newcat',
        'date_created_0': '01-01-2025',
        'number_0': '999',
        'name_1': 'Doc2',
        'category_1': 'cat2',
        'date_created_1': '25-07-2026',
        'number_1': '002',
    }
    updated = apply_form_changes(form, data, export_mode='school')
    assert updated[0]['Name'] == 'NewName'
    assert updated[0]['Category'] == 'newcat'
    assert updated[0]['Number'] == '999'
    assert updated[0]['Regulatory'] == 'Да'


def test_apply_form_changes_checkbox_off():
    data = _make_sample_data()
    form = {
        'name_0': 'Doc1',
        'category_0': 'cat1',
        'date_created_0': '25-07-2026',
        'number_0': '001',
    }
    updated = apply_form_changes(form, data, export_mode='school')
    assert updated[0]['Regulatory'] == 'Нет'


def test_render_table_preview_empty():
    html = render_table_preview([])
    assert 'Загрузите ZIP-архив' in html


def test_render_table_preview_with_data():
    data = _make_sample_data()
    html = render_table_preview(data, export_mode='school', manifest=[
        {'name': 'doc1.pdf', 'from': 'PDF', 'to': 'PDF', 'status': 'done'},
        {'name': 'doc2.pdf', 'from': 'XLSX', 'to': 'PDF', 'status': 'converting'},
    ])
    assert '<table>' in html
    assert 'Doc1' in html
    assert 'Doc2' in html
    assert 'convert-badge-done' in html
    assert 'convert-badge-converting' in html


def test_render_table_preview_with_manifest():
    data = _make_sample_data()
    manifest = [
        {'name': 'doc1.pdf', 'from': 'PDF', 'to': 'PDF', 'status': 'done'},
    ]
    html = render_table_preview(data, manifest=manifest)
    assert 'convert-badge-done' in html


def test_get_category_from_path():
    assert get_category_from_path('cat/sub/file.pdf') == 'cat'
    assert get_category_from_path('file.pdf') == 'Без категории'
    assert get_category_from_path('') == 'Без категории'


def test_parse_zip_to_csv_rows(app):
    zip_data = [
        ('category1/doc1.pdf', b'%PDF-1.4 fake content'),
        ('category1/doc2.docx', b'PK fake docx'),
        ('image.png', b'\x89PNG fake'),
        ('readme.txt', b'not allowed'),
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in zip_data:
            zf.writestr(name, data)
    buf.seek(0)

    with app.app_context():
        with zipfile.ZipFile(buf) as z:
            rows, skipped = parse_zip_to_csv_rows(z)

        filenames = [r['ArchivePath'] for r in rows]
        assert any('Doc1.pdf' in f for f in filenames)
        assert any('Doc2.docx' in f for f in filenames)
        assert any('Image.pdf' in f for f in filenames)
        assert 'readme.txt' in skipped
        assert len(rows) == 3
