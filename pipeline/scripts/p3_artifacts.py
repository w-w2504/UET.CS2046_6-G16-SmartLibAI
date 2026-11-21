"""Component-scoped, SHA-256-bound P3 repository data validation."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


MANIFEST = 'data/raw/p3_v4/integration_manifest.json'
GROUPS = {'search': 'search_v4', 'reader': 'reader_staging',
          'baseline': 'regression_v1', 'reader-sources': 'reader_provenance'}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def contained(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f'Path outside data root: {relative}')
    return path


def check_files(root, files):
    for relative, expected in files.items():
        blob = contained(root, relative).read_bytes()
        if len(blob) != expected['bytes'] or sha256(blob).hexdigest() != expected['sha256']:
            raise ValueError(f'Checksum/size mismatch: {relative}')
    return len(files)


def verify_group(root, component):
    manifest = json.loads(contained(root, MANIFEST).read_bytes())
    if manifest['schema_version'] != 2:
        raise ValueError('P3 integration manifest schema_version=2 required')
    group = manifest['groups'][GROUPS[component]]
    return check_files(root, group['files'])


def verify_package(root, component):
    path = Path(root) / 'handoff_manifest.json'
    if not path.exists():
        return {'status': 'SKIP', 'reason': 'Repository mode; no package envelope'}
    manifest = json.loads(path.read_bytes())
    if manifest['component'] != component:
        raise ValueError('Package/component mismatch')
    files = manifest['files']
    integration = json.loads(contained(root, MANIFEST).read_bytes())
    required = integration['groups'][GROUPS[component]]['files']
    if MANIFEST not in files or not set(required).issubset(files):
        raise ValueError('Package envelope omits required data/manifest')
    return {'status': 'PASS', 'files_sha256_checked': check_files(root, files)}


def verify_reader_data(root):
    from ai_library.importer import validate_and_load_batch

    checked = verify_group(root, 'reader')
    batch = Path(root) / 'data/raw/p3_reader'
    report, data = validate_and_load_batch(batch, taxonomy_path=batch / 'taxonomy.json')
    assert not report.errors and report.valid == {'books': 2, 'chapters': 28}
    assert all(not book.fulltext_approved for book in data['books'].values())
    assert all(source.rights_status == 'pending' for book in data['books'].values()
               for source in book.sources if source.content_type == 'fulltext')
    catalog = {b['book_id']: b for b in read_jsonl(Path(root) / 'data/raw/p3_v4/catalog.jsonl')}
    search = {b['book_id']: b for b in read_jsonl(Path(root) / 'data/raw/p3_v4/search/catalog.jsonl')}
    registry = json.loads((batch / 'id_registry.json').read_bytes())
    provenance = json.loads((batch / 'source_manifest.json').read_bytes())
    chapters = read_jsonl(batch / 'chapters.jsonl')
    assert len(chapters) == len({c['chapter_id'] for c in chapters}) == 28
    paragraphs = []
    counts = {}
    for book in provenance['books']:
        bid = book['book_id']
        assert registry['registry'][bid] == catalog[bid]['work_id'] == search[bid]['work_id']
        for target in (catalog[bid], search[bid]):
            assert target['title'] == book['title'] and target['authors'] == [book['author']]
        rows = sorted((c for c in chapters if c['book_id'] == bid), key=lambda c: c['order_no'])
        count, paragraph_count = (10, 880) if bid == 'SLB_B0001' else (18, 3421)
        assert len(rows) == count and [c['order_no'] for c in rows] == list(range(1, count + 1))
        assert sum(len(c['paragraphs']) for c in rows) == paragraph_count
        for chapter, entry in zip(rows, book['chapters'], strict=True):
            assert (chapter['chapter_id'], chapter['title']) == (entry['chapter_id'], entry['title'])
            assert sha256('\n\n'.join(chapter['paragraphs']).encode()).hexdigest() == entry['text_sha256']
            assert len(chapter['paragraphs']) == entry['paragraph_count']
            occurrences = Counter()
            for paragraph in chapter['paragraphs']:
                checksum = sha256(paragraph.encode()).hexdigest()
                occurrences[checksum] += 1
                paragraphs.append(registry['paragraphs'][chapter['chapter_id']][f'{checksum}|{occurrences[checksum]}'])
        counts[bid] = {'chapters': count, 'paragraphs': paragraph_count}
    assert len(paragraphs) == len(set(paragraphs)) == 4301
    for name, checksum in provenance['batch_sha256'].items():
        assert sha256((batch / name).read_bytes()).hexdigest() == checksum
    return {'status': 'PASS', 'books': 2, 'chapters': 28, 'paragraphs': 4301,
            'per_book': counts, 'files_sha256_checked': checked, 'rights_unchanged': True}


def verify_reader_sources(root):
    checked = verify_group(root, 'reader-sources')
    batch = Path(root) / 'data/raw/p3_reader'
    provenance = json.loads((batch / 'source_manifest.json').read_bytes())
    for book in provenance['books']:
        assert sha256((batch / 'raw' / book['source_url'].rsplit('/', 1)[-1]).read_bytes()).hexdigest() == book['source_sha256']
    return {'status': 'PASS', 'epub_count': len(provenance['books']),
            'files_sha256_checked': checked, 'epub_required_for_reader_runtime': False}
