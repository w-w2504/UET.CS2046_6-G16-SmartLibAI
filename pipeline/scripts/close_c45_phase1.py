"""Build a reproducible C45 closure package without changing r8 or prior audits."""
import argparse
import copy
import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R8 = ROOT/'data/demo/p4-w03-c38-reviewed-r8-20261122'
REPORTS = ROOT/'data/reports'
V12 = REPORTS/'c45-r8-phase1-20261123-v12'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def lines(p): return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8').strip()
def commit(ref):
    h,author,authored,committed,subject=git('show','-s','--format=%H|%an|%aI|%cI|%s',ref).split('|',4)
    return dict(sha=h,author=author,author_date=authored,commit_date=committed,subject=subject)
def identity(c): return (c['check_id'],c.get('record_id'),c.get('book_id'))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    out=a.output.resolve();assert not out.exists(),'Use a new report directory'
    assert out.is_relative_to(REPORTS.resolve())
    assert git('branch','--show-current')=='feature/data-embedding'
    # Protect complete existing audit packages, r8 and uncommitted C41 data/scripts.
    protected=[]
    for directory in (R8, V12, REPORTS/'c45-r8-review-provenance-20261123', REPORTS/'c45-r8-review-reconciliation-20261123', ROOT/'data/raw/c41_reader20_batch1'):
        protected.extend(p for p in directory.rglob('*') if p.is_file())
    protected.extend(p for p in (ROOT/'pipeline/scripts').glob('*c41*') if p.is_file())
    protected.extend(p for p in (ROOT/'pipeline/tests').glob('*c41*') if p.is_file())
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    audit=read(V12/'audit_run.json');checks=lines(V12/'checks.jsonl')
    assert len(checks)==33 and len({identity(c) for c in checks})==33
    for name,entry in audit['inputs'].items():
        p=Path(entry['path']);p=p if p.is_absolute() else ROOT/p
        assert sha(p)==entry['sha256'],name
    books={b['book_id']:b for b in lines(R8/'search/catalog.jsonl')}
    decisions={d['book_id']:d for d in read(R8/'review.json')['decisions']}
    sources={s['source_id']:(b,s) for b in books.values() for s in b['sources']}
    assert len(books)==289 and len(sources)==578
    p3=commit('a0666cc');p4=commit('86bc2b6')
    quality={x['book_id']:x for x in lines(ROOT/'data/raw/c35_reviewed150/quality_by_book_id.jsonl')}
    recovered=[]
    for sid,(b,s) in sources.items():
        if s['rights_status']!='approved':continue
        sample=b['book_id'] not in decisions
        if sample:assert quality[b['book_id']]['quality_status']=='approved_sample'
        c=p3 if sample else p4;role='P3' if sample else 'P4'
        recovered.append(dict(source_id=sid,book_id=b['book_id'],work_id=b['work_id'],content_type=s['content_type'],
            rights_status=s['rights_status'],review_decision='approved',reviewed_by=role,reviewed_at=None,
            review_record_date=c['commit_date'],date_source='git_commit',reference_commit=c['sha'],
            review_confidence='inferred',review_scope='demo_internal_metadata_summary_only',
            assignment_basis='Owner confirms historical review by P3/P4; sample responsibility assigned P3, r8 review/handoff responsibility assigned P4; individual source attribution inferred',
            catalog_recorded_reviewed_at=s.get('reviewed_at'),historical_timestamp_verified=False,
            review_evidence=['owner_attestation: current closure request section 6.1',
                'data/raw/c35_reviewed150/quality_by_book_id.jsonl' if sample else 'data/demo/p4-w03-c38-reviewed-r8-20261122/review.json',
                'git:'+c['sha']],contributed_by=c['author']))
    assert len(recovered)==len({x['source_id'] for x in recovered})==572
    url=[]
    for pair in lines(V12/'url_comparison.jsonl'):
        d=decisions[pair['book_id']];replacement=d.get('source_replacements',{}).get(pair['content_type'],{})
        matches=replacement.get('source_id')==pair['source_id'] and replacement.get('source_url')==pair['catalog_url']
        assert matches
        url.append({**pair,'provenance_resolution':'documented_source_replacement_matches_current_source',
                    'original_review_url_role':'original reference before replacement',
                    'catalog_url_role':'selected replacement source', 'replacement':replacement,
                    'review_number':d['review_number'],'review_reason':d['reason'],
                    'content_equivalence_claim':False,'rights_use':'demo decision recorded; third-party/public rights not inferred',
                    'method':'offline exact book_id/content_type/source_id/source_url comparison',
                    'evidence':'data/demo/p4-w03-c38-reviewed-r8-20261122/review.json:source_replacements'})
    assert len(url)==114
    old={b['book_id']:b for b in lines(ROOT/'data/raw/p3_v4/search/catalog.jsonl')}
    shared=set(old)&set(books);summary_changed=[i for i in sorted(shared) if old[i]['summary']!=books[i]['summary']]
    urls_changed=[i for i in sorted(shared) if [s['source_url'] for s in old[i]['sources']]!=[s['source_url'] for s in books[i]['sources']]]
    metrics=dict(original_claim={'reviewed':122,'approved':119,'summary_changed':63,'source_books_changed':64},
        original_evidence=['data/demo/p4-w03-c38-reviewed-r8-20261122/README.md','specs/p4/week-03/acceptance.md'],
        original_commit=p4['sha'],exact_iteration_baseline_available=False,
        correction='119/63/64 remains an unverified iteration-local statement; do not cite it as reproduced. Use the following explicit full-dataset comparison instead.',
        reproduced_full_diff=dict(baseline='data/raw/p3_v4/search/catalog.jsonl',baseline_sha256=sha(ROOT/'data/raw/p3_v4/search/catalog.jsonl'),
            target_sha256=sha(R8/'search/catalog.jsonl'),shared_books=len(shared),summary_changed=len(summary_changed),
            url_changed_books=len(urls_changed),replacement_sources=len(url),
            summary_changed_ids=summary_changed,url_changed_ids=urls_changed),
        reviewed_decisions=len(decisions),dispositions=dict(Counter(d['disposition'] for d in decisions.values())),
        remaining_requirement='Exact pre-iteration catalog/review subset and counting rules are required to reproduce 119/63/64')
    row=next(c for c in checks if c['check_id']=='C45-REVIEW-URL')
    row.update(status='PASS',observed={'pairs':114,'replacement_id_url_matches':114,'unresolved_references':0},
        evidence=str(out.relative_to(ROOT)/'url_resolution.jsonl'),recommended_action=None)
    for c in checks:
        c['closure_disposition']='satisfied' if c['status']=='PASS' else 'documented_exception'
        if c['check_id'] in ('C45-PENDING-SOURCE','C45-PENDING-INDEX'):
            c['closure_disposition']='owner_accepted_pending_exclusion'
            c['recommended_action']='Keep pending and exclude from Search/Recommendation; do not change approval.'
        if c['check_id']=='C45-REVIEW-SCOPE':
            c['observed']={'historical_approved_sources':572,'inferred_reviewers':{'P3':40,'P4':532},
                'reference_dates_bound_to_commits':572,'actual_review_times_verified':0,
                'public_or_outside_demo_permissions':'not established'}
            c['evidence']+='; '+str(out.relative_to(ROOT)/'historical_review_recovered.jsonl')
        if c['check_id']=='C45-P4-BASELINE':
            c['evidence']+='; '+str(out.relative_to(ROOT)/'historical_lineage_resolution.json')
        if c['check_id']=='C45-PYTHON-VALIDATORS':
            c['evidence']+='; '+str(out.relative_to(ROOT)/'validation.json:tests')
    totals=dict(Counter(c['status'] for c in checks));exceptions=[c for c in checks if c['status']!='PASS']
    assert totals=={'PASS':24,'WARNING':7,'UNVERIFIED':2} and len(exceptions)==9
    # Reuse real ASGI evidence only if source artifacts and production code at tested HEAD still match.
    search=read(REPORTS/'c45-r8-search-api-20261123.json');rec=read(REPORTS/'c45-r8-recommendation-api-20261123.json')
    snap=R8/'snapshot/p4-w03-c38-reviewed-r8-20261122'
    for evidence in (search,rec):
        assert evidence['status']=='passed' and evidence['eligible_count']==286 and evidence['source_unchanged']
        assert all(sha(snap/name)==h for name,h in evidence['source_hashes'].items())
    assert not git('diff','HEAD','--','api/src','pipeline/ai_library')
    conn=sqlite3.connect(f'file:{(snap/"catalog.sqlite").as_posix()}?mode=ro',uri=True)
    eligible={r[0] for r in conn.execute("SELECT book_id FROM sources WHERE rights_status='approved' AND content_type IN ('metadata','summary') GROUP BY book_id HAVING count(DISTINCT content_type)=2")}
    assert len(eligible)==286;conn.close()
    assert len(set(books)-eligible)==3 and sum(s['rights_status']=='pending' for _,s in sources.values())==6
    out.mkdir(parents=True)
    def write(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def jsonl(name,values): (out/name).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in values),encoding='utf-8')
    write('checks_final.json',checks);write('exceptions_final.json',exceptions)
    jsonl('historical_review_recovered.jsonl',recovered);jsonl('url_resolution.jsonl',url)
    write('historical_lineage_resolution.json',metrics)
    matrix=[dict(check_id=c['check_id'],record_id=c.get('record_id'),book_id=c.get('book_id'),
                 original_status=next(x['status'] for x in lines(V12/'checks.jsonl') if identity(x)==identity(c)),
                 final_status=c['status'],pass_condition=c['expected'],evidence=c['evidence'],
                 resolution=c['closure_disposition'],next_action=c['recommended_action']) for c in checks]
    write('remediation_matrix.json',matrix)
    after={str(p.relative_to(ROOT)):sha(p) for p in protected};assert before==after
    write('validation.json',dict(git_head=git('rev-parse','HEAD'),totals={**totals,'FAIL':0},
        rows=33,unique_composite_keys=33,unique_check_ids=len({c['check_id'] for c in checks}),
        input_hashes_verified=19,protected_file_hashes_before=before,protected_files_unchanged=before==after,
        approved_review_records=572,books=289,sources=578,eligible=286,pending=3,
        reused_ASGI={'search_cases':len(search['cases']),'recommend_cases':len(rec['cases']),
                     'source_hashes_still_valid':True},phase1_technical_acceptance='with_documented_exceptions',
        absolute_closure=False,phase2_started=False))
    summary='''# C45 Phase 1 final closure — 23/11/2026

33 check rows (28 check IDs, composite source keys unique): **24 PASS / 7 WARNING / 0 FAIL / 2 UNVERIFIED**; 9 exceptions.

Compared with v12, C45-REVIEW-URL becomes PASS: all 114 explicit source_replacements match book/type/source_id/URL. Prior reports omitted this field; their 114 unresolved provenance references are superseded by this exact comparison. No public-use license or full content equivalence is inferred.

572 historical approved records: inferred P3 for 40 sample sources, inferred P4 for 532 r8 review sources, based on owner attestation and batch responsibility. Every reference date is bound to a real commit. reviewed_at stays null; original catalog timestamps are retained separately. This recovers administrative attribution, not independently witnessed signatures or public permissions.

119/63/64 is not reproducible without the exact iteration input. The correction reports full P3-v4→r8 differences: 116 changed summaries, 101 books with URL changes, 114 replacement source entries. Original expected remains UNVERIFIED.

Seven WARNINGs track six intentional pending sources and three pending index members. Real ASGI reports still bind to unchanged r8 artifacts; Search returns 10 approved results even for each pending title ranked first in the unfiltered index, and pending Recommendation/Similar seeds are rejected. Keep 286 eligible, 3 pending, 578 sources intact.

Narrow technical acceptance for internal metadata/summary demo is supported by OpenSpec's documented-exception route. Full 33/33 closure and public/source rights verification are not established. Phase 2 and entire C45 remain open. The remaining two UNVERIFIEDs concern exact historical iteration figures and evidence beyond demo/actual historical review attribution. See acceptance.md and exceptions_final.json.
'''
    (out/'summary.md').write_text(summary,encoding='utf-8')
    (out/'acceptance.md').write_text('''# Phase 1 acceptance

Decision: technical acceptance with documented exceptions for the frozen r8 internal classroom metadata/summary demo. It is not 33/33 PASS or C45 Done.

Basis: OpenSpec c45-data-quality-audit/specs/data-quality-audit/spec.md allows Phase 1 independently of Reader Phase 2 with reviewed documented exceptions. The owner explicitly accepts three pending books remaining excluded; seven pending-source/index warnings are intentional retained records. No rights_status is changed.

Runtime evidence retained: v11 Search 13 ASGI cases with real E5/SQLite/FAISS, Recommendation 11 cases plus 4 error cases, importer 289/289, full E5 correspondence and FAISS/NumPy verification from v12. Hashes and production source remain unchanged. This package does not claim new HTTP TCP/browser E2E or 503 fault injection.

Unresolved: exact baseline/subset for 119/63/64; human attribution is inferred from owner statement and responsibility, exact review times and outside-demo permissions remain unproven. These limit historical/public-rights conclusions, not safe exclusion of pending records in the scoped demo.

No snapshot activation, production data change, Phase 2, Git commit/push or PR action is performed. Global C45 completion and OpenSpec archival are not authorized by this acceptance.

Reproduce package: python -B pipeline/scripts/close_c45_phase1.py --output data/reports/<new-closure-directory>
Required verification commands: node --experimental-sqlite --test pipeline/tests/test_c45_phase1.mjs pipeline/tests/test_c45_review_replacements.mjs; python -B -m pytest -q -p no:cacheprovider pipeline/tests/test_importer_quarantine.py api/tests/test_eligibility.py; openspec validate c45-data-quality-audit --strict. The portable Python environment uses the existing .venv site-packages through PYTHONPATH plus pipeline and api roots. Record fresh command results in validation.json rather than assuming them from an earlier run.
''',encoding='utf-8')
    print(json.dumps({'totals':{**totals,'FAIL':0},'exceptions':len(exceptions),'protected_files':len(before),'output':str(out)}))

if __name__=='__main__':main()
