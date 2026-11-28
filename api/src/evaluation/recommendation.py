"""C31 pool preparation and C33 gated offline evaluation. No HTTP/encoder calls."""

import csv
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import zipfile
from time import monotonic
from types import SimpleNamespace

import faiss
import numpy as np

from ai_library.book_embeddings import book_text
from src.schemas.common import Filters
from src.schemas.recommend import RecommendationRequest
from src.services.recommendation import select_candidate_ids
from src.services.recommendation_response import validate_catalog_input
from .baselines import Tfidf, genre_scores
from .metrics import precision_ndcg_at5

METHODS = ('e5_faiss', 'genre', 'tfidf')
ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def write_rows(path, rows):
    Path(path).write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n' for row in rows), encoding='utf-8')


def read_cases(path):
    data = read_json(path)
    cases = data['scenarios']
    if (data.get('format_version') != 1 or len(cases) != 20
            or Counter(c['split'] for c in cases) != {'dev':8, 'test':12}
            or len({c['scenario_id'] for c in cases}) != 20):
        raise ValueError('C31 requires unique 20 scenarios, 8 dev/12 test')
    for case in cases:
        if (case.get('status') not in ('draft','approved','frozen') or not case.get('intent')
                or not case.get('rationale') or not case.get('evidence_refs')
                or not isinstance(case['scenario_id'], str)):
            raise ValueError('Scenario requires intent, evidence, rationale and review status')
        RecommendationRequest(seed_book_ids=case['seed_book_ids'], exclude_book_ids=case['exclude_book_ids'],
                              filters=case['filters'], snapshot_id=data['snapshot_id'])
    return data


def rank_methods(source, tfidf, case):
    payload = RecommendationRequest(seed_book_ids=case['seed_book_ids'],
        exclude_book_ids=case['exclude_book_ids'], filters=case['filters'], snapshot_id=source.snapshot_id)
    excluded = validate_catalog_input(source, payload)
    seeds = payload.seed_book_ids
    blocked = excluded | {source.metadata[bid].work_id for bid in seeds}
    representative={book.work_id:bid for bid,book in source.ranker.books.items()}
    indexed_excludes=[representative[wid] for wid in excluded if wid in representative]
    hits = source.ranker.evaluation_top20(seeds, exclude_book_ids=indexed_excludes, filters=payload.filters)
    rankings = {'e5_faiss': [dict(book_id=h.book_id, work_id=h.work_id, score=float(h.score), rank=h.rank) for h in hits]}
    for method, scores in [('genre',genre_scores(source.ranker.books,seeds)), ('tfidf',tfidf.score(seeds))]:
        ids = select_candidate_ids(source.ranker.books, scores, eligible_ids=source.eligible_ids,
            blocked_works=blocked, filters=payload.filters or Filters(), limit=20)
        rankings[method] = [dict(book_id=bid, work_id=source.metadata[bid].work_id,
                                score=float(scores[bid]), rank=i) for i,bid in enumerate(ids,1)]
    return rankings


def review_sample(pool):
    """At least ceil(20%) of (scenario_id, work_id) in EACH split, fixed before labels."""
    sample = []
    for split in ('dev','test'):
        pairs = sorted((row for row in pool if row['split']==split),
            key=lambda r: hashlib.sha256((r['scenario_id']+'/'+r['work_id']).encode()).hexdigest())
        sample.extend(pairs[:math.ceil(len(pairs)*.2)])
    return [(r['scenario_id'],r['work_id']) for r in sample]


LABEL_COLUMNS = ['scenario_id','work_id','relevance','rationale','evidence','annotator_id','annotated_at']
FINAL_COLUMNS = ['scenario_id','work_id','relevance','rationale','evidence','status','approved_by','approved_at','resolution']


def write_sheet(path, columns, pairs):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
        writer.writeheader()
        writer.writerows(dict(scenario_id=sid, work_id=wid) for sid,wid in pairs)


def source_hashes(directory):
    return {name:sha(directory/name) for name in ('manifest.json','catalog.sqlite','mapping.jsonl','books.faiss')}


def create_pool(source, directory, cases_path, output):
    """Source MUST be a validated C17 RecommendationSnapshot, not a C11-only bundle."""
    from src.services.recommendation_faiss import FaissBookScorer
    if not isinstance(source.ranker.scorer, FaissBookScorer):
        raise ValueError('Real pool requires C14 FaissBookScorer')
    data = read_cases(cases_path)
    if data['snapshot_id'] != source.snapshot_id:
        raise ValueError('Cases belong to another snapshot')
    before=source_hashes(directory)
    manifest=read_json(directory/'manifest.json')
    if (before['manifest.json']!=source.manifest_sha256
            or any(before.get(row['path'])!=row['sha256'] for row in manifest['files'] if row['path'] in before)):
        raise ValueError('Loaded snapshot and current artifact hashes differ')
    corpus=sorted(source.eligible_ids & source.ranker.books.keys())
    texts={bid:book_text(SimpleNamespace(title=source.books[bid].title, authors=source.metadata[bid].authors,
        genres=source.metadata[bid].genres, topics=source.metadata[bid].topics, summary=source.books[bid].summary),
        source.labels['genre'],source.labels['topic']) for bid in corpus}
    tfidf=Tfidf(texts)
    pool, rankings, cards = [], [], []
    for case in data['scenarios']:
        by_work = {}
        for method, hits in rank_methods(source,tfidf,case).items():
            rankings.append(dict(scenario_id=case['scenario_id'],split=case['split'],method=method,items=hits))
            for hit in hits:
                entry=by_work.setdefault(hit['work_id'],dict(scenario_id=case['scenario_id'],split=case['split'],
                    work_id=hit['work_id'], book_ids=[],origins=[]))
                entry['book_ids']=sorted(set(entry['book_ids']) | {hit['book_id']})
                entry['origins'].append(dict(method=method,**hit))
        for wid,row in sorted(by_work.items()):
            pool.append(row)
            def display(bid):
                b=source.books[bid]
                return dict(book_id=bid,work_id=b.work_id,title=b.title,authors=list(b.authors),
                    genres=[source.labels['genre'][c] for c in sorted(b.genres)],
                    topics=[source.labels['topic'][c] for c in sorted(source.metadata[bid].topics)],
                    summary=b.summary,has_fulltext=b.has_fulltext,
                    evidence_ref=f'{source.snapshot_id}/catalog.sqlite#books/{bid}')
            cards.append(dict(scenario_id=case['scenario_id'],split=case['split'],work_id=wid,
                intent=case['intent'],judging_guidance=case.get('judging_guidance',''),rationale=case['rationale'],filters=case['filters'],
                seeds=[display(bid) for bid in case['seed_book_ids']],
                candidates=[display(bid) for bid in row['book_ids']]))
    if before != source_hashes(directory):
        raise ValueError('Source changed during pooling')
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    (output/'scenarios.json').write_bytes(Path(cases_path).read_bytes())
    write_rows(output/'pool.jsonl',pool);write_rows(output/'rankings.jsonl',rankings)
    cards.sort(key=lambda r:hashlib.sha256((r['scenario_id']+'/'+r['work_id']).encode()).hexdigest())
    write_rows(output/'judging_cards.jsonl',cards)
    pairs=[(r['scenario_id'],r['work_id']) for r in cards]
    sample=review_sample(pool)
    write_json(output/'review_sample.json',[list(p) for p in sample])
    write_sheet(output/'primary.csv',LABEL_COLUMNS,pairs)
    write_sheet(output/'cross_review.csv',LABEL_COLUMNS,sample)
    write_sheet(output/'final.csv',FINAL_COLUMNS,pairs)
    card_columns=['scenario_id','work_id','split','intent','judging_guidance','filters','seeds','candidates']
    def card_sheet(path, items):
        with path.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=card_columns,lineterminator='\n');writer.writeheader()
            writer.writerows({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],(dict,list)) else r[k]
                             for k in card_columns} for r in items)
    card_sheet(output/'judging_cards.csv',cards)
    card_sheet(output/'cross_review_cards.csv',[c for c in cards if (c['scenario_id'],c['work_id']) in set(sample)])
    with zipfile.ZipFile(output/'handoff-p4.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ('cross_review.csv','cross_review_cards.csv','review_sample.json'):
            archive.write(output/name,arcname=name)
        archive.writestr('README.txt',
            'C31 draft independent review. No human approval is implied.\n'
            'Unit: (scenario_id, work_id). Read all candidate editions and seed summaries.\n'
            'Relevance: 0 unrelated; 1 partially relevant; 2 clearly relevant.\n'
            'Fill cross_review.csv with rationale, evidence, actual annotator_id and timezone timestamp.\n'
            'Do not inspect retrieval methods/ranks or the primary annotator labels.\n'
            'Return the original file; disagreements are resolved separately, never overwrite raw labels.\n'
            'Cases/split and review protocol still require Van/P02 approval. No test metrics authorized.\n')
    code_paths=sorted((ROOT/'api/src/evaluation').glob('*.py')) + [ROOT/'api/src/services'/name for name in (
        'recommendation.py','recommendation_snapshot.py','recommendation_faiss.py','preference.py','eligibility.py')]
    run=dict(format_version=1,status='awaiting_human_approval_and_labels',snapshot_id=source.snapshot_id,
        snapshot_dir=str(directory.resolve()), source_hashes=before, model=manifest['embedding'],
        data_kind=manifest.get('data_kind'), catalog_books=len(source.books), corpus_books=len(corpus), corpus_works=len({source.metadata[b].work_id for b in corpus}),
        corpus_ids_sha256=hashlib.sha256('\n'.join(corpus).encode()).hexdigest(),corpus_ids=corpus,
        scenario_sha256=sha(cases_path), code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        code_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
        code_hashes={str(p.relative_to(ROOT)):sha(p) for p in code_paths},
        config=dict(methods=list(METHODS),pool_depth=20,metric_k=5,tf='1+ln(count)',idf='ln((1+N)/(1+df))+1',
            corpus='all eligible indexed editions before scenario filters',tokenizer='bm25_search.tokenize NFC casefold Unicode letter/number runs',
            normalization='L2 document; mean L2 seeds then L2',genre='count intersection with seed genre union',
            tie='exact score descending then book_id BINARY',review_unit='scenario_id/work_id',review_fraction=.2),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,faiss=faiss.__version__),
        pool_pairs=len(pool),review_pairs=len(sample),counts_by_split=dict(Counter(r['split'] for r in pool)),
        artifacts={name:sha(output/name) for name in ('scenarios.json','pool.jsonl','rankings.jsonl','judging_cards.jsonl',
            'judging_cards.csv','cross_review_cards.csv','handoff-p4.zip','review_sample.json')})
    write_json(output/'run.json',run)
    return run


def verified_run(directory):
    run=read_json(directory/'run.json')
    for name,digest in run['artifacts'].items():
        if Path(name).name != name or sha(directory/name)!=digest:
            raise ValueError('Pool artifact hash mismatch')
    if sha(directory/'scenarios.json') != run['scenario_sha256']:
        raise ValueError('Scenario hash mismatch')
    return run


def _identity(record, name, date):
    if not isinstance(record.get(name),str) or not record[name].strip():
        raise ValueError('Missing human identity')
    try:
        stamp=datetime.fromisoformat(record[date].replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError()
    except (TypeError,KeyError,ValueError) as exc:
        raise ValueError('Human record requires timezone-aware timestamp') from exc


def _sheet(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream,strict=True))
    found={}
    for row in rows:
        pair=(row['scenario_id'],row['work_id'])
        if pair in found: raise ValueError('Duplicate label pair')
        found[pair]=row
    return found


def validate_labels(directory, *, primary, cross, final, approval, split):
    run=verified_run(directory)
    if split not in ('dev','test'): raise ValueError('Choose one split')
    approved=read_json(approval)
    if (approved.get('status')!='approved' or approved.get('scenario_sha256')!=run['scenario_sha256']
            or approved.get('run_sha256')!=sha(directory/'run.json')
            or approved.get('protocol') not in ('c31-c33-v1','c31-c33-v2-joint-review-test')):
        raise ValueError('Cases/protocol/run not approved by human')
    _identity(approved,'approved_by','approved_at')
    if (not isinstance(approved.get('primary_annotator_id'),str) or not approved['primary_annotator_id'].strip()
            or not isinstance(approved.get('cross_annotator_id'),str) or not approved['cross_annotator_id'].strip()
            or approved.get('cross_reviewer_role')!='P4'
            or approved['primary_annotator_id'].strip().casefold()==approved['cross_annotator_id'].strip().casefold()):
        raise ValueError('Approval must name independent primary and P4 reviewers')
    pool=read_rows(directory/'pool.jsonl')
    expected={(r['scenario_id'],r['work_id']) for r in pool if r['split']==split}
    all_pairs={(r['scenario_id'],r['work_id']) for r in pool}
    sample={tuple(p) for p in read_json(directory/'review_sample.json')}
    if sample!=set(review_sample(pool)): raise ValueError('Cross-review sample changed')
    sheets=[_sheet(p) for p in (primary,cross,final)]
    for sheet in sheets:
        if not set(sheet)<=all_pairs: raise ValueError('Unknown label pair')
    joint_test=split=='test' and approved['protocol']=='c31-c33-v2-joint-review-test'
    if not expected<=sheets[0].keys() or not expected<=sheets[2].keys() or (not joint_test and not expected & sample <= sheets[1].keys()):
        raise ValueError('Missing labels')
    if approved['protocol']=='c31-c33-v2-joint-review-test':
        from .joint_review import exception_files, validate_exception
        # Pin all additional provenance even for dev; the exception only replaces test cross-review.
        exception_files(approval,approved)
        if joint_test:
            validate_exception(directory,approval,approved,run,expected,sample,*sheets)
    labels={}
    for pair in expected:
        raw=sheets[0][pair]; decision=sheets[2][pair]
        def relevance(row):
            binding=dict(snapshot_id=run['snapshot_id'],run_sha256=sha(directory/'run.json'),
                scenario_sha256=run['scenario_sha256'],pool_sha256=sha(directory/'pool.jsonl'))
            if any(k in row for k in binding) and any(row.get(k)!=v for k,v in binding.items()):
                raise ValueError('Label snapshot/pool/run hash differs')
            if 'reviewer_confirmed' in row and row['reviewer_confirmed']!='yes':
                raise ValueError('Reviewer has not confirmed exchange row')
            if 'review_status' in row and row['review_status']!='confirmed':
                raise ValueError('Reviewer status not confirmed')
            if row.get('relevance') not in ('0','1','2') or not row.get('rationale','').strip() or not row.get('evidence','').strip():
                raise ValueError('Invalid/missing relevance, rationale or evidence')
            return int(row['relevance'])
        first=relevance(raw); result=relevance(decision)
        _identity(raw,'annotator_id','annotated_at');_identity(decision,'approved_by','approved_at')
        if raw['annotator_id']!=approved['primary_annotator_id']: raise ValueError('Unexpected primary annotator')
        if decision.get('status')!='approved': raise ValueError('Final label not approved')
        disagreement = result!=first
        if pair in sample and not joint_test:
            other=sheets[1][pair]
            second=relevance(other);_identity(other,'annotator_id','annotated_at')
            if other['annotator_id']!=approved['cross_annotator_id']: raise ValueError('Unexpected P4 annotator')
            if other['annotator_id'].strip().casefold()==raw['annotator_id'].strip().casefold():
                raise ValueError('Cross-review must be independent')
            disagreement = disagreement or first!=second or result!=second
        if disagreement and not decision.get('resolution','').strip():
            raise ValueError('Unresolved disagreement')
        labels[pair]=result
    return labels


def metric_code_paths():
    """Code affecting evaluation/validation; stable roles, portable across checkouts."""
    module=Path(__file__).resolve()
    return {'evaluator':module,'metrics':module.with_name('metrics.py'),
            'joint_review':module.with_name('joint_review.py'),'review':module.with_name('review.py'),
            'cli':module.parents[2]/'scripts/evaluate_recommendation.py'}


def metric_code_hashes():
    # Python source newline translation is platform-independent; data hashes remain byte-exact.
    return {role:hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for role,path in metric_code_paths().items()}


def freeze_files(directory, *, primary, cross, final, approval):
    paths=dict(primary=primary,cross=cross,final=final,approval=approval)
    paths.update({name:directory/name for name in ('run.json','scenarios.json','pool.jsonl','rankings.jsonl','review_sample.json')})
    approved=read_json(approval)
    if approved.get('protocol')=='c31-c33-v2-joint-review-test':
        from .joint_review import exception_files
        paths.update({'joint_review/'+role:path for role,path in exception_files(approval,approved).items()})
    result={role:sha(path) for role,path in paths.items()}
    result.update({'code/'+role:digest for role,digest in metric_code_hashes().items()})
    return result


def freeze(directory, *, primary, cross, final, approval, output):
    for split in ('dev','test'):
        validate_labels(directory,primary=primary,cross=cross,final=final,approval=approval,split=split)
    if Path(output).exists(): raise FileExistsError(output)
    files=freeze_files(directory,primary=primary,cross=cross,final=final,approval=approval)
    write_json(output,dict(format_version=2,status='frozen',files=files,run_sha256=sha(directory/'run.json'),
        code_hash_policy='python_source_crlf_to_lf; data_exact_bytes'))


def evaluate(directory, *, primary, cross, final, approval, split, output, frozen=None, authorization=None):
    if Path(output).exists(): raise FileExistsError(output)
    labels=validate_labels(directory,primary=primary,cross=cross,final=final,approval=approval,split=split)
    if split=='test':
        if frozen is None or authorization is None: raise ValueError('Test requires freeze and explicit user authorization')
        record=read_json(frozen); auth=read_json(authorization)
        required=freeze_files(directory,primary=primary,cross=cross,final=final,approval=approval)
        if (record.get('format_version')!=2
                or record.get('code_hash_policy')!='python_source_crlf_to_lf; data_exact_bytes'
                or record.get('status')!='frozen' or record.get('files')!=required
                or record.get('run_sha256')!=sha(directory/'run.json')):
            raise ValueError('Frozen inputs changed')
        if (auth.get('action')!='run_test_once' or auth.get('freeze_sha256')!=sha(frozen)
                or auth.get('test_used_for_tuning') is not False or not isinstance(auth.get('test_usage_history'),list)):
            raise ValueError('Test not authorized/independent; record usage history')
        _identity(auth,'authorized_by','authorized_at')
        # Same authorization cannot silently generate a second official test report.
        used=directory/('test-use-'+sha(authorization)+'.json')
        with used.open('x',encoding='utf-8') as stream: stream.write(str(Path(output).resolve()))
    scenarios=read_cases(directory/'scenarios.json')['scenarios']
    wanted={c['scenario_id'] for c in scenarios if c['split']==split}
    rows=read_rows(directory/'rankings.jsonl')
    by_pair={(r['scenario_id'],r['method']):r for r in rows}
    if len(by_pair)!=len(rows) or set(by_pair)!={(c['scenario_id'],m) for c in scenarios for m in METHODS}:
        raise ValueError('Missing/duplicate method ranking')
    per_case=[]
    for sid in sorted(wanted):
        judged={wid:v for (scenario,wid),v in labels.items() if scenario==sid}
        methods={}
        for method in METHODS:
            row=by_pair[sid,method]
            if row['split']!=split or any(h['rank']!=i for i,h in enumerate(row['items'],1)):
                raise ValueError('Ranking split/ranks invalid')
            methods[method]=precision_ndcg_at5([h['work_id'] for h in row['items']],judged)
        best=max(methods[m]['ndcg_at5'] for m in ('genre','tfidf'))
        per_case.append(dict(scenario_id=sid,methods=methods,e5_minus_best_baseline_ndcg=methods['e5_faiss']['ndcg_at5']-best,
            analysis_status='requires_human_metadata_analysis',intent=next(c['intent'] for c in scenarios if c['scenario_id']==sid)))
    macro={m:{metric:math.fsum(c['methods'][m][metric] for c in per_case)/len(per_case)
              for metric in ('precision_at5','ndcg_at5')} for m in METHODS}
    run=verified_run(directory)
    report=dict(split=split,evaluation='pooled_work_level',case_count=len(per_case),macro=macro,per_case=per_case,
        no_relevant_cases=[c['scenario_id'] for c in per_case if c['methods']['e5_faiss']['no_relevant_in_pool']],
        run_sha256=sha(directory/'run.json'),label_hashes={str(p):sha(p) for p in (primary,cross,final,approval)},
        snapshot_id=run['snapshot_id'],source_hashes=run['source_hashes'],config=run['config'],
        metric_code_hashes=metric_code_hashes(),
        strongest_baseline_by_macro_ndcg=max(('genre','tfidf'),key=lambda m:macro[m]['ndcg_at5']),
        e5_not_below_strongest_baseline=macro['e5_faiss']['ndcg_at5']>=max(macro[m]['ndcg_at5'] for m in ('genre','tfidf')),
        frozen_sha256=sha(frozen) if frozen else None,authorization_sha256=sha(authorization) if authorization else None,
        test_usage_history=read_json(authorization)['test_usage_history'] if authorization else None,
        review_protocol=read_json(approval)['protocol'],
        test_review_mode='joint_review_exception' if read_json(approval)['protocol']=='c31-c33-v2-joint-review-test' else 'original_protocol',
        original_independent_test_review_satisfied=False if read_json(approval)['protocol']=='c31-c33-v2-joint-review-test' else None,
        limitations='Pooled labels; unjudged corpus is unknown; no Recall or C40 acceptance claim')
    write_json(output,report)
    return report
