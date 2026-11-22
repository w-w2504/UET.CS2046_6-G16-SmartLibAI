"""Verify P4 handoffs from a checkout without model downloads or hidden data roots."""
from pathlib import Path
import argparse,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'pipeline'),str(ROOT/'api')]
sys.stdout.reconfigure(encoding='utf-8')


def verify(component: str, root: Path) -> dict:
    relative = {'index':'data/demo/p4-w03-c38-289-20261122',
                'reader':'data/demo/p4-w03-c42-reader2-20261122'}[component]
    directory=root/relative
    manifest=json.loads((directory/'handoff_manifest.json').read_bytes())
    assert manifest['component']==component and manifest['schema_version']==1
    for row in manifest['files']:
        assert not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts and '\\' not in row['path'] and ':' not in row['path']
        path=root/row['path']
        assert not path.is_symlink() and path.resolve().is_relative_to(root.resolve())
        content=path.read_bytes()
        assert len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256'],row['path']
    if component=='index':
        import numpy as np
        from ai_library.book_index import load_book_index
        from ai_library.c11_bundle import load_c11_bundle
        source=root/'data/demo/smartlibai-fasttrack/smartlibai-demo-v4'
        bundle=load_c11_bundle(source/'bundle',batch_dir=root/'data/raw/p3_v4/search',taxonomy_path=source/'taxonomy.json',classroom_demo=True)
        index=load_book_index(directory/'index',classroom_demo=True)
        assert len(index.book_ids)==289 and index.book_ids==bundle.book_ids
        assert all(np.array_equal(index.get_vector(bid),v) for bid,v in zip(bundle.book_ids,bundle.vectors))
        assert sum(index.search(v,1)[0].book_id==bid for bid,v in zip(bundle.book_ids,bundle.vectors))==289
        return {'component':component,'files':len(manifest['files']),'vectors_roundtrip':289,'self_top1':289,'scope':manifest['scope']}
    from src.services.catalog import open_catalog
    sid=manifest['snapshot_id']
    with open_catalog(directory/'snapshots'/sid,sid) as handle:
        books=handle.rows('SELECT * FROM books WHERE has_fulltext=1')
        chapters=handle.rows('SELECT * FROM chapters')
        paragraphs=handle.rows('SELECT * FROM paragraphs')
        assert len(books)==2 and len(chapters)==28 and len(paragraphs)==4301
        assert not handle.rows("SELECT * FROM sources WHERE rights_status='approved' AND (reviewed_at IS NULL OR reviewed_by IS NULL)")
        raw=[json.loads(line) for line in (root/'data/raw/p4_w03_reader2/chapters.jsonl').read_bytes().splitlines()]
        expected={r['chapter_id']:r for r in raw}
        for c in chapters:
            assert c['text']=='\n\n'.join(expected[c['chapter_id']]['paragraphs'])
    return {'component':component,'files':len(manifest['files']),'books':2,'chapters':28,'paragraphs':4301,'scope':manifest['scope']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component',choices=['index','reader','all'],default='all')
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    components=['index','reader'] if args.component=='all' else [args.component]
    print(json.dumps([verify(c,args.root.resolve()) for c in components],ensure_ascii=False))
