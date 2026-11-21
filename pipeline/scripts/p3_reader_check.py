"""Validate staging Reader data and exercise all chapters on a temporary C25 snapshot."""

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(Path(__file__).resolve().parent)] + [str(REPO / path) for path in ('pipeline', 'api', 'api/tests')]

from fastapi.testclient import TestClient

from ai_library.catalog_sqlite import import_catalog_to_sqlite
from ai_library.importer import validate_and_load_batch
from ai_library.text_utils import compute_sha256
from catalog_fixture import create_snapshot, refresh_manifest
from src.config import settings
from src.main import app

from in_memory_http import enable_for_restricted_windows
from p3_artifacts import verify_reader_data, verify_package


SNAPSHOT = 'smartlibai-reader-contract-test'


def verify(root=REPO):
    root = Path(root).resolve(strict=True)
    BATCH = root / 'data/raw/p3_reader'
    data_result = verify_reader_data(root)
    enable_for_restricted_windows()
    taxonomy = BATCH / 'taxonomy.json'
    report, data = validate_and_load_batch(BATCH, taxonomy_path=taxonomy)
    assert not report.errors and report.valid == {'books': 2, 'chapters': 28}
    assert all(not book.fulltext_approved for book in data['books'].values())
    assert all(source.rights_status == 'pending' for book in data['books'].values()
               for source in book.sources if source.content_type == 'fulltext')
    provenance = json.loads((BATCH / 'source_manifest.json').read_bytes())
    ids = json.loads((BATCH / 'id_registry.json').read_bytes())
    metadata_only = {}
    checked = Counter()

    with TemporaryDirectory(prefix='smartlib-reader-verify-') as temp:
        fixture_root = Path(temp)
        fixture_info = create_snapshot(fixture_root, SNAPSHOT)
        snapshot_path = fixture_info['snapshot_dir']
        db_path = snapshot_path / 'catalog.sqlite'
        # Replace authored sample data, keeping the existing C25 fixture manifest structure.
        with closing(sqlite3.connect(db_path)) as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            with db:
                for table in tables:
                    db.execute(f'DELETE FROM {table}')
        imported = import_catalog_to_sqlite(BATCH, db_path, snapshot_id=SNAPSHOT, taxonomy_path=taxonomy)
        assert not imported.errors and imported.valid == {'books': 2, 'chapters': 0}
        with closing(sqlite3.connect(db_path)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            assert db.execute('SELECT count(*) FROM books WHERE has_fulltext=1').fetchone() == (0,)
            assert db.execute('SELECT count(*) FROM chapters').fetchone() == (0,)
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            metadata_only.update({'loaded_books': 2, 'loaded_chapters': 0, 'approved_fulltext': 0,
                                  'sqlite_integrity': 'ok', 'foreign_key_violations': 0})
            # Approval columns below are technical fixture values and exist only in this temporary DB.
            db.execute('''UPDATE sources SET rights_status='approved', rights_note=?, reviewed_at=?, reviewed_by=?''',
                       ('Fixture-only source approval for API contract verification.', '2026-11-21T00:00:00Z', 'reader-contract-fixture'))
            for book in data['books'].values():
                source = next(source for source in book.sources if source.content_type == 'fulltext')
                db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?)', (
                    SNAPSHOT, source.source_id, book.book_id, 'fulltext', source.source_url, source.source_note,
                    'approved', 'Fixture-only source approval for API contract verification.',
                    '2026-11-21T00:00:00Z', 'reader-contract-fixture'))
                db.execute('UPDATE books SET has_fulltext=1 WHERE snapshot_id=? AND book_id=?', (SNAPSHOT, book.book_id))
                for chapter in data['chapters'][book.book_id]:
                    text = '\n\n'.join(chapter.paragraphs)
                    db.execute('INSERT INTO chapters VALUES (?,?,?,?,?,?,?)', (
                        SNAPSHOT, chapter.chapter_id, book.book_id, chapter.order_no, chapter.title, text,
                        compute_sha256(text)))
                    offset = 0
                    counts = Counter()
                    for order, paragraph in enumerate(chapter.paragraphs, 1):
                        digest = compute_sha256(paragraph)
                        counts[digest] += 1
                        paragraph_id = ids['paragraphs'][chapter.chapter_id][f'{digest}|{counts[digest]}']
                        db.execute('INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?)', (
                            SNAPSHOT, paragraph_id, chapter.chapter_id, order, paragraph, offset, offset + len(paragraph)))
                        offset += len(paragraph) + 2
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        refresh_manifest(snapshot_path)
        settings.SNAPSHOT_ROOT = str(fixture_info['snapshot_root'])
        settings.CONTROL_ROOT = str(fixture_info['control_root'])
        settings.SMARTLIBAI_DEMO_SNAPSHOT = None
        settings.CLASSROOM_DEMO_SNAPSHOT = None

        with TestClient(app) as client:
            for book in provenance['books']:
                result = client.get(f"/api/v1/books/{book['book_id']}/chapters", params={'snapshot_id': SNAPSHOT})
                assert result.status_code == 200, result.text
                items = result.json()['items']
                assert [(row['chapter_id'], row['order_no'], row['title']) for row in items] == [
                    (row['chapter_id'], row['order_no'], row['title']) for row in book['chapters']]
                checked['chapter_lists_200'] += 1
                for entry in book['chapters']:
                    result = client.get(f"/api/v1/chapters/{entry['chapter_id']}", params={'snapshot_id': SNAPSHOT})
                    assert result.status_code == 200, result.text
                    row = result.json()['chapter']
                    assert row['book_id'] == book['book_id'] and row['title'] == entry['title']
                    assert compute_sha256(row['text']) == entry['text_sha256']
                    assert len(row['paragraphs']) == entry['paragraph_count']
                    checked['chapter_details_200'] += 1
                    for paragraph in row['paragraphs']:
                        assert row['text'][paragraph['char_start']:paragraph['char_end']] == paragraph['text']
                        checked['paragraph_offsets'] += 1

    verify_reader_data(root)
    return {'status': 'PASS', 'data': data_result, 'chapter_importer': report.model_dump(), 'metadata_only_import': metadata_only,
            'temporary_C25_contract_test': dict(checked), 'rights_unchanged': True,
            'temporary_SQLite_integrity': 'ok', 'temporary_SQLite_foreign_key_violations': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise FileExistsError(args.output)
    package = verify_package(args.root, 'reader')
    result = {'data_root': str(args.root.resolve()), 'package': package, **verify(args.root)}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
