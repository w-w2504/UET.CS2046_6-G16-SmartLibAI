"""Verify the P3 checkpoints, existing E5 artifacts and temporary Reader contract."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from unicodedata import is_normalized

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / path) for path in ('pipeline', 'api', 'api/tests')]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_library.book_index import load_book_index
from ai_library.c11_bundle import load_c11_bundle
from ai_library.catalog_sqlite import import_catalog_to_sqlite
from ai_library.classroom_demo import load_demo_books
from ai_library.importer import validate_and_load_batch
from in_memory_http import enable_for_restricted_windows
from p3_artifacts import verify_group, verify_package, verify_reader_data, verify_reader_sources



def read_jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def verify_search(root, model_root=None, api_smoke=False, semantic_smoke=False):
    data = root / 'data'
    raw = data / 'raw/p3_v4'
    release = data / 'demo/smartlibai-fasttrack/smartlibai-demo-v4'
    snapshot = release / 'snapshot/smartlibai-demo-v4'
    checked = verify_group(root, 'search')
    report, imported = validate_and_load_batch(raw, taxonomy_path=raw / 'taxonomy.json', metadata_only=True)
    assert not report.errors and report.valid['books'] == 294
    books = {book['book_id']: book for book in read_jsonl(raw / 'catalog.jsonl')}
    assert len(books) == 294
    for original in read_jsonl(data / 'raw/sample_batch/catalog.jsonl'):
        assert books[original['book_id']] == original, original['book_id']
    demo = load_demo_books(raw / 'search', taxonomy_path=raw / 'taxonomy.json')
    assert len(demo) == 289
    bundle_source = json.loads((release / 'bundle/manifest.json').read_bytes())['source']
    assert sha256((raw / 'search/catalog.jsonl').read_bytes()).hexdigest() == bundle_source['catalog_sha256']
    assert all(is_normalized('NFC', book['summary']) for book in books.values())
    bundle = load_c11_bundle(release / 'bundle', batch_dir=raw / 'search',
                            taxonomy_path=raw / 'taxonomy.json', classroom_demo=True)
    assert bundle.manifest['embedding']['model_id'] == 'intfloat/multilingual-e5-small'
    assert bundle.manifest['embedding']['revision'] == 'fd1525a9fd15316a2d503bf26ab031a61d056e98'
    index = load_book_index(release / 'index', classroom_demo=True)
    assert index.book_ids == bundle.book_ids and len(index.book_ids) == 289
    for vector in bundle.vectors:
        scores = bundle.vectors @ vector
        expected = sorted(range(289), key=lambda row: (-float(scores[row]), bundle.book_ids[row]))[:5]
        hits = index.search(vector, 5)
        assert [hit.row_id for hit in hits] == expected
        np.testing.assert_allclose([hit.score for hit in hits], scores[expected], atol=1e-6, rtol=0)
    for manifest_path in (release / 'index/index_manifest.json', snapshot / 'manifest.json'):
        for entry in json.loads(manifest_path.read_bytes())['files']:
            blob = (manifest_path.parent / entry['path']).read_bytes()
            assert sha256(blob).hexdigest() == entry['sha256'] and len(blob) == entry['size_bytes']
    with TemporaryDirectory(prefix='p3-catalog-import-') as temp:
        database = Path(temp) / 'catalog.sqlite'
        loaded = import_catalog_to_sqlite(raw, database, taxonomy_path=raw / 'taxonomy.json',
                                         snapshot_id='p3-catalog-v4-staging')
        assert not loaded.errors and loaded.valid['books'] == 294
        for path, count in ((database, 294), (snapshot / 'catalog.sqlite', 289)):
            with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as db:
                assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
                assert db.execute('PRAGMA foreign_key_check').fetchall() == []
                assert db.execute('SELECT count(*) FROM books').fetchone() == (count,)
                assert db.execute('SELECT count(*) FROM chapters').fetchone() == (0,)
                if count == 289:
                    mapping = read_jsonl(snapshot / 'mapping.jsonl')
                    actual = db.execute('SELECT row_id,object_id,content_hash FROM vector_mapping ORDER BY row_id').fetchall()
                    assert actual == [(r['row_id'], r['object_id'], r['content_hash']) for r in mapping]
    result = {'status': 'PASS', 'catalog_import': loaded.model_dump(), 'original_20_preserved': True,
              'search_books': 289, 'vectors': 289, 'dimension': 384,
              'faiss_top5_reference_checks': 289, 'files_sha256_checked': checked,
              'api': {'status': 'SKIP', 'reason': 'Pass --api-smoke'},
              'semantic': {'status': 'SKIP', 'reason': 'Pass --semantic-smoke and --model-root'}}
    np.testing.assert_allclose(np.linalg.norm(bundle.vectors, axis=1), 1, atol=1e-5, rtol=0)
    assert bundle.vectors.shape == (289, 384)
    assert bundle.manifest['embedding']['normalization'] == 'L2'
    assert len(books.keys() - demo.keys()) == 5
    if not api_smoke and not semantic_smoke:
        return result
    from fastapi.testclient import TestClient
    from src.config import settings
    from src.main import app
    enable_for_restricted_windows()
    if model_root is not None:
        settings.MODEL_ROOT = str(model_root)
    settings.SNAPSHOT_ROOT = str(root / 'data/snapshots')
    settings.CONTROL_ROOT = str(root / 'data/control')
    settings.SMARTLIBAI_DEMO_SNAPSHOT = str(snapshot)
    import logging
    logging.getLogger('httpx').setLevel(logging.WARNING)
    if semantic_smoke:
        if model_root is None:
            raise ValueError('--model-root required with --semantic-smoke')
        from src.services.search import search_service
        encoder = search_service.get_encoder(bundle.manifest['embedding'])
        encoder.encode_queries(['thư viện'])
        print('E5 loaded; warm-up query completed. No book vectors generated.', flush=True)
    with TestClient(app) as client:
        settings.SMARTLIBAI_DEMO_SNAPSHOT = str(snapshot)
        params = {'snapshot_id': snapshot.name}
        response = client.get('/api/v1/books', params=params)
        assert response.status_code == 200 and response.json()['total'] == 289, response.text
        assert client.get('/api/v1/facets', params=params).status_code == 200
        for book_id in demo:
            response = client.get(f'/api/v1/books/{book_id}', params=params)
            assert response.status_code == 200 and response.json()['book']['title'] == demo[book_id].title
        for book_id in books.keys() - demo.keys():
            assert client.get(f'/api/v1/books/{book_id}', params=params).status_code == 404
        result['api'] = {'status': 'PASS', 'books': 289, 'details_200': 289, 'excluded_details_404': 5}
        if semantic_smoke:
            prior_queries = json.loads((release / 'verification.json').read_bytes())['api']['queries']
            for query in prior_queries:
                response = client.post('/api/v1/search', json={**params, 'q': query['query'], 'k': 5,
                    'filters': {'genres': [books[query['book_id']]['genres'][-1]]}})
                assert response.status_code == 200, response.text
                assert response.json()['items'][0]['book_id'] == query['book_id'], response.text
            result['semantic'] = {'status': 'PASS', 'queries_top1': len(prior_queries), 'model_warmed': True}
    verify_group(root, 'search')
    return result


def verify_baseline(root):
    checked = verify_group(root, 'baseline')
    from fastapi.testclient import TestClient
    from src.config import settings
    from src.main import app
    enable_for_restricted_windows()
    settings.SMARTLIBAI_DEMO_SNAPSHOT = str(root / 'data/demo/smartlibai-demo-v1/snapshot/smartlibai-demo-v1')
    with TestClient(app) as client:
        response = client.get('/api/v1/books', params={'snapshot_id': 'smartlibai-demo-v1'})
        assert response.status_code == 200 and response.json()['total'] == 95
    return {'status': 'PASS', 'books': 95, 'files_sha256_checked': checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=REPO, help='All data is read strictly under this root')
    parser.add_argument('--component', choices=['search', 'reader', 'all', 'baseline', 'reader-sources'], default='search')
    parser.add_argument('--api-smoke', action='store_true')
    parser.add_argument('--semantic-smoke', action='store_true')
    parser.add_argument('--model-root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise FileExistsError(args.output)
    root = args.root.resolve(strict=True)
    import ai_library.importer
    result = {'data_root': str(root), 'component': args.component,
              'pipeline_code': str(Path(ai_library.importer.__file__).resolve())}
    components = ['search', 'reader', 'reader-sources', 'baseline'] if args.component == 'all' else [args.component]
    for component in components:
        if component in ('search', 'reader'):
            result[component + '_package'] = verify_package(root, component)
        if component == 'search':
            result['search'] = verify_search(root, args.model_root, args.api_smoke, args.semantic_smoke)
        elif component == 'reader':
            if args.api_smoke:
                import p3_reader_check
                result['reader'] = p3_reader_check.verify(root)
            else:
                result['reader'] = verify_reader_data(root)
        elif component == 'baseline':
            result['baseline'] = verify_baseline(root)
        else:
            result['reader_sources'] = verify_reader_sources(root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
