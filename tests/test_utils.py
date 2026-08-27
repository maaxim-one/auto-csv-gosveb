import os
import pytest
from app.utils import (
    sanitize_filename,
    is_safe_path,
    truncate_filename,
)
from app.services.csv import get_category_from_path


def test_sanitize_filename(app):
    with app.app_context():
        assert sanitize_filename('foo.pdf') == 'foo.pdf'
        assert sanitize_filename('../../../etc/passwd') == 'passwd'
        assert sanitize_filename('C:\\Windows\\file.txt') == 'file.txt'
        assert sanitize_filename('just_a_name') == 'just_a_name'
        assert sanitize_filename('path/sub/file.pdf') == 'file.pdf'


def test_is_safe_path():
    base = '/tmp/safe'
    assert is_safe_path(base, '/tmp/safe/file.txt') is True
    assert is_safe_path(base, '/tmp/safe/sub/file.txt') is True
    assert is_safe_path(base, '/tmp/other/file.txt') is False
    assert is_safe_path(base, '/tmp/safe/../../../etc/passwd') is False


def test_truncate_filename_short(app):
    with app.app_context():
        result = truncate_filename('short.pdf')
        assert result == 'short.pdf'


def test_truncate_filename_long(app):
    with app.app_context():
        long_name = 'a' * 300 + '.pdf'
        result = truncate_filename(long_name)
        assert len(result.encode('utf-8')) <= 200
        assert result.endswith('.pdf')


def test_get_category_from_path():
    assert get_category_from_path('category1/sub/file.pdf') == 'category1'
    assert get_category_from_path('file.pdf') == 'Без категории'
    assert get_category_from_path('cat1/cat2/file.pdf') == 'cat1'
    assert get_category_from_path('') == 'Без категории'
