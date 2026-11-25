"""Reproduce Reader source policy gates using authored SQLite test fixtures.

These tests document the existing policy, not acceptance of the C41 real corpus.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'api'), str(ROOT/'api/tests')]
from catalog_fixture import BOOK_ID, CHAPTER_IDS, create_snapshot, refresh_manifest
from src.config import settings
from src.main import app
from fastapi.testclient import TestClient


@pytest.mark.parametrize('fault', [None, 'missing_reviewer', 'internal_demo_note'])
def test_reader_source_policy_gates_are_independent(tmp_path, monkeypatch, fault):
    fixture = create_snapshot(tmp_path)
    directory = fixture['snapshot_dir']
    if fault:
        with closing(sqlite3.connect(directory/'catalog.sqlite')) as db, db:
            if fault == 'missing_reviewer':
                db.execute("UPDATE sources SET reviewed_by=NULL WHERE book_id=? AND content_type='summary'", (BOOK_ID,))
            else:
                db.execute("UPDATE sources SET rights_note='Chỉ demo nội bộ; chưa có phạm vi Reader' WHERE book_id=? AND content_type='summary'", (BOOK_ID,))
        refresh_manifest(directory)
    monkeypatch.setattr(settings, 'SNAPSHOT_ROOT', str(fixture['snapshot_root']))
    monkeypatch.setattr(settings, 'CONTROL_ROOT', str(fixture['control_root']))
    monkeypatch.setattr(settings, 'SMARTLIBAI_DEMO_SNAPSHOT', None)
    monkeypatch.setattr(settings, 'CLASSROOM_DEMO_SNAPSHOT', None)
    client = TestClient(app)
    response = client.get(f'/api/v1/chapters/{CHAPTER_IDS[0]}', params={'snapshot_id':directory.name})
    assert response.status_code == (503 if fault else 200)
    if fault:
        assert response.json()['code'] == 'service_unavailable'
        assert 'chapter' not in response.json()
    else:
        assert response.json()['chapter']['book_id'] == BOOK_ID
