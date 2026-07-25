import os
import pytest
from app.services.job import job_update, job_read, job_dir, job_status_path


def test_job_update_and_read(app, tmp_storage):
    with app.app_context():
        job_update('testjob', status='processing', total=5, manifest=[{'name': 'a.pdf', 'from': 'PDF', 'to': 'PDF', 'status': 'done'}])
        result = job_read('testjob')
        assert result is not None
        assert result['status'] == 'processing'
        assert result['total'] == 5
        assert len(result['manifest']) == 1


def test_job_read_nonexistent(app):
    with app.app_context():
        result = job_read('nonexistent_job_id')
        assert result is None


def test_job_update_incremental(app):
    with app.app_context():
        job_update('incjob', status='processing', progress=0)
        job_update('incjob', progress=3)
        result = job_read('incjob')
        assert result['status'] == 'processing'
        assert result['progress'] == 3


def test_job_update_atomic_write(app):
    with app.app_context():
        for i in range(5):
            job_update('atomicjob', progress=i)
        result = job_read('atomicjob')
        assert result['progress'] == 4


def test_job_dir_and_path(app):
    with app.app_context():
        d = job_dir('xyz')
        assert 'job_xyz' in d
        p = job_status_path('xyz')
        assert p.endswith('status.json')
