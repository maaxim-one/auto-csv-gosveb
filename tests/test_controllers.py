import io
import os
import json
import zipfile
import pytest
from conftest import _make_zip
from app.config import Config


def test_index_page(client):
    response = client.get('/')
    assert response.status_code == 200


def test_upload_no_file(client):
    response = client.post('/upload', follow_redirects=True)
    assert response.status_code == 200


def test_upload_empty_file(client):
    data = {'archive': (io.BytesIO(b''), '')}
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200


def test_upload_non_zip(client):
    data = {'archive': (io.BytesIO(b'not a zip'), 'test.txt')}
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200


def test_upload_valid_zip(client):
    zip_data = _make_zip([
        ('category1/doc.pdf', b'%PDF-1.4 fake'),
        ('category1/readme.txt', b'ignored'),
    ])
    data = {'archive': (io.BytesIO(zip_data), 'test.zip')}
    response = client.post('/upload', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert response.status_code == 200


def test_upload_ajax(client):
    zip_data = _make_zip([
        ('cat/doc.pdf', b'%PDF-1.4 fake'),
    ])
    data = {'archive': (io.BytesIO(zip_data), 'test.zip')}
    response = client.post(
        '/upload',
        data=data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert body.get('ok') is True
    assert 'preview_html' in body


def test_clear_session(client):
    response = client.post('/clear', follow_redirects=True)
    assert response.status_code == 200


def test_clear_session_ajax(client):
    response = client.post('/clear', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    body = response.get_json()
    assert body.get('ok') is True


def test_download_zip_no_session(client):
    response = client.post('/download_zip', follow_redirects=True)
    assert response.status_code == 200


def test_download_status_no_params(client):
    response = client.get('/download-status', follow_redirects=True)
    assert response.status_code == 200


def test_serve_download_not_found(client):
    response = client.get('/serve_download/nonexistent.zip')
    assert response.status_code == 404


def test_api_convert_status_not_found(client):
    response = client.get('/api/convert_status/nonexistent')
    assert response.status_code == 404


def test_api_convert_status_valid(client, app):
    with app.app_context():
        from app.services.job import job_update
        job_update('test_api_job', status='processing', total=3, manifest=[
            {'name': 'a.pdf', 'from': 'PDF', 'to': 'PDF', 'status': 'done'},
            {'name': 'b.xlsx', 'from': 'XLSX', 'to': 'PDF', 'status': 'converting'},
            {'name': 'c.docx', 'from': 'DOCX', 'to': 'PDF', 'status': 'waiting'},
        ])

    response = client.get('/api/convert_status/test_api_job')
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'processing'
    assert body['total'] == 3
    assert body['progress'] == 1


def test_api_version(client):
    response = client.get('/api/version')
    assert response.status_code == 200
    body = response.get_json()
    assert 'current' in body
    assert body['current'] == Config.APP_VERSION


def test_upload_then_download(client):
    zip_data = _make_zip([
        ('cat1/doc.pdf', b'%PDF-1.4 fake pdf content here'),
    ])
    data = {'archive': (io.BytesIO(zip_data), 'test.zip'), 'export_mode': 'school'}
    response = client.post('/upload', data=data, content_type='multipart/form-data')
    assert response.status_code in (200, 302)

    response = client.post('/download_zip', data={'export_mode': 'school'}, follow_redirects=True)
    assert response.status_code == 200


def test_upload_then_download_ajax(client):
    zip_data = _make_zip([
        ('cat1/doc.pdf', b'%PDF-1.4 fake pdf content here'),
    ])
    data = {'archive': (io.BytesIO(zip_data), 'test.zip'), 'export_mode': 'school'}
    response = client.post(
        '/upload',
        data=data,
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200

    response = client.post(
        '/download_zip',
        data={'export_mode': 'school'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body.get('ok') is True
    assert 'redirect' in body
