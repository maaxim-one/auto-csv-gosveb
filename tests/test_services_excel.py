import pytest
from app.services.excel import (
    file_conversion_entry,
    convert_excel_bytes_to_pdf,
    _convert_via_ilovepdf,
    _convert_via_msexcel,
)


def test_file_conversion_entry_pdf():
    result = file_conversion_entry('doc.pdf', 'done')
    assert result['from'] == 'PDF'
    assert result['to'] == 'PDF'
    assert result['status'] == 'done'
    assert result['name'] == 'doc.pdf'


def test_file_conversion_entry_xlsx():
    result = file_conversion_entry('data.xlsx', 'waiting')
    assert result['from'] == 'XLSX'
    assert result['to'] == 'PDF'
    assert result['status'] == 'waiting'


def test_file_conversion_entry_png():
    result = file_conversion_entry('image.png', 'converting')
    assert result['from'] == 'PNG'
    assert result['to'] == 'PDF'
    assert result['status'] == 'converting'


def test_convert_via_ilovepdf_no_keys(app):
    with app.app_context():
        result = _convert_via_ilovepdf(b'fake data', 'test.xlsx')
        assert result == b''


def test_convert_via_msexcel_non_windows(app):
    with app.app_context():
        import sys
        original = sys.platform
        sys.platform = 'linux'
        result = _convert_via_msexcel(b'fake data', 'test.xlsx')
        sys.platform = original
        assert result == b''


def test_convert_excel_bytes_to_pdf_all_fail(app):
    with app.app_context():
        result = convert_excel_bytes_to_pdf(b'garbage data', 'test.xlsx')
        assert result == b''


def test_convert_excel_bytes_to_pdf_non_excel(app):
    with app.app_context():
        result = convert_excel_bytes_to_pdf(b'data', 'test.pdf')
        assert isinstance(result, bytes)
