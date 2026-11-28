"""Synthetic review exchange tests only. No human judgements or metric runs."""

import csv
import json
from pathlib import Path
import zipfile

import pytest

from test_recommendation_evaluation import bundle, fill_labels, edit_sheet
from src.config import settings
from src.evaluation.review import (LABEL_EDIT, FINAL_EDIT, _rows, _csv, export_review,
    import_review, compare_reviews)
from src.evaluation.recommendation import read_json, read_rows, sha, validate_labels
from src.services.recommendation_snapshot import load_recommendation_snapshot


@pytest.fixture
def handoff(bundle):
    directory=settings.snapshot_path/'rec-v1'
    before={p.name:sha(p) for p in bundle.iterdir() if p.is_file()}
    output=bundle.parent/'handoff'
    export_review(bundle,load_recommendation_snapshot(),directory,output)
    assert before=={p.name:sha(p) for p in bundle.iterdir() if p.is_file()}
    return bundle,output


def edited(path,output,change):
    columns,rows=_rows(path)
    change(rows)
    _csv(output,columns,rows)
    return output


def confirm_all(rows,actor='fixture:P02',label='1'):
    for row in rows:
        row.update(relevance=label,rationale='Synthetic fixture only',evidence='fixture://summary',
            annotator_id=actor,annotated_at='2026-11-27T12:00:00+07:00',review_status='confirmed',reviewer_confirmed='yes')


def test_export_bom_blank_fields_metadata_and_fixed_sample(handoff):
    run,out=handoff
    manifest=read_json(out/'manifest.json')
    _,cases=_rows(out/'scenarios-review.csv')
    assert len(cases)==20 and sum(c['split']=='dev' for c in cases)==8
    assert all(c['technical_status']=='PASS' and not c['human_approval'] and not c['approved_by'] for c in cases)
    assert read_json(out/'scenario-checks.json')['near_duplicate_warnings']
    for split in ('dev','test'):
        _,primary=_rows(out/split/'primary.csv');_,p4=_rows(out/split/'p4.csv')
        assert len(p4)>=.2*len(primary)
        for role in ('primary','p4'):
            path=out/split/(role+'.csv')
            assert path.read_bytes().startswith(b'\xef\xbb\xbf')
            columns,rows=_rows(path)
            assert not set(columns)&{'method','rank','score','primary_label'}
            assert all(not r[k] for r in rows for k in LABEL_EDIT)
            assert all(r['seed_summaries'] and r['candidate_summaries'] and r['candidate_titles'] for r in rows)
    with zipfile.ZipFile(out/'P4-independent-review.zip') as archive:
        assert set(archive.namelist())=={'dev/p4.csv','test/p4.csv','HOW-TO-LABEL.md','manifest.json'}
        private=json.loads(archive.read('manifest.json'))
        import hashlib
        assert all(hashlib.sha256(archive.read(n)).hexdigest()==h for n,h in private['files'].items())


def test_blank_and_partial_drafts_are_preserved_not_finalized(handoff,tmp_path):
    run,out=handoff;source=out/'dev/primary.csv'
    report=import_review(run,out,source,'primary','dev',tmp_path/'blank-draft')
    assert report['confirmed']==0 and report['blank']==report['rows']
    assert not (tmp_path/'blank-draft/canonical.csv').exists()
    change=edited(source,tmp_path/'partial.csv',lambda rows:rows[0].update(relevance='0',review_status='needs_review',review_note='Synthetic need more evidence'))
    report=import_review(run,out,change,'primary','dev',tmp_path/'partial')
    assert report['blank']==report['rows']-1 and report['needs_review']==1
    assert (tmp_path/'partial/raw-input.csv').read_bytes()==change.read_bytes()
    with pytest.raises(ValueError,match='Cannot finalize'):
        import_review(run,out,change,'primary','dev',tmp_path/'no',finalize=True)


@pytest.mark.parametrize('field,value',[
    ('relevance','3'),('relevance','-1'),('relevance','1.0'),('relevance','TRUE'),
    ('snapshot_id','other'),('pool_sha256','0'*64),('run_sha256','0'*64),
    ('candidate_work_id','changed'),('seed_book_ids','changed'),('candidate_titles','changed'),
    ('scenario_id',' R01'),('reviewer_confirmed','true'),
])
def test_bad_excel_value_or_binding_is_refused(handoff,tmp_path,field,value):
    run,out=handoff
    source=edited(out/'dev/primary.csv',tmp_path/'edited.csv',lambda rows:rows[0].update({field:value}))
    with pytest.raises(ValueError):import_review(run,out,source,'primary','dev',tmp_path/'no')


@pytest.mark.parametrize('defect',['missing','duplicate','missing_identity','missing_timezone','unconfirmed'])
def test_missing_duplicate_or_unconfirmed_reviewer_refused(handoff,tmp_path,defect):
    run,out=handoff
    def change(rows):
        confirm_all(rows)
        if defect=='missing':rows.pop()
        elif defect=='duplicate':rows.append(dict(rows[0]))
        elif defect=='missing_identity':rows[0]['annotator_id']=''
        elif defect=='missing_timezone':rows[0]['annotated_at']='27/11/2026'
        else:rows[0].update(review_status='draft',reviewer_confirmed='')
    source=edited(out/'dev/primary.csv',tmp_path/'edited.csv',change)
    with pytest.raises(ValueError):import_review(run,out,source,'primary','dev',tmp_path/'no',finalize=True)


def test_successful_canonical_import_and_no_overwrite(handoff,tmp_path):
    run,out=handoff
    source=edited(out/'dev/primary.csv',tmp_path/'edited.csv',confirm_all)
    destination=tmp_path/'converted'
    report=import_review(run,out,source,'primary','dev',destination,finalize=True)
    assert report['confirmed']==report['rows'] and report['canonical_sha256']==sha(destination/'canonical.csv')
    _,rows=_rows(destination/'canonical.csv')
    assert all(r['relevance']=='1' and r['work_id'].startswith('W_') and r['reviewer_confirmed']=='yes' for r in rows)
    with pytest.raises(FileExistsError):import_review(run,out,source,'primary','dev',destination)


def test_dev_test_cannot_be_mixed(handoff,tmp_path):
    run,out=handoff
    with pytest.raises(ValueError):import_review(run,out,out/'test/primary.csv','primary','dev',tmp_path/'no')


def test_blanks_only_generate_pending_adjudication_no_final_label(handoff,tmp_path):
    run,out=handoff;dest=tmp_path/'comparison'
    report=compare_reviews(run,out,out/'dev/primary.csv',out/'dev/p4.csv','dev',dest)
    assert report['awaiting_primary']==report['rows'] and report['disagreements']==0
    assert report['awaiting_p4']==len(_rows(out/'dev/p4.csv')[1])
    assert report['confirmed_primary']==report['confirmed_p4']==0
    _,rows=_rows(dest/'adjudication.csv')
    assert all(not row[k] for row in rows for k in FINAL_EDIT)
    assert not _rows(dest/'disagreements.csv')[1]
    with pytest.raises(ValueError):import_review(run,out,dest/'adjudication.csv','final','dev',tmp_path/'no',finalize=True,comparison=dest)


def test_disagreement_keeps_both_labels_and_requires_human_resolution(handoff,tmp_path):
    run,out=handoff
    primary=edited(out/'dev/primary.csv',tmp_path/'p.csv',lambda rows:confirm_all(rows,'fixture:P02','1'))
    p4=edited(out/'dev/p4.csv',tmp_path/'c.csv',lambda rows:confirm_all(rows,'fixture:P4','2'))
    old_hashes=(sha(primary),sha(p4));comparison=tmp_path/'comparison'
    report=compare_reviews(run,out,primary,p4,'dev',comparison)
    _,sample=_rows(p4)
    assert report['disagreements']==len(sample)
    def decide(rows):
        for row in rows:
            row.update(final_label='1',final_rationale='Synthetic decision',final_evidence='fixture://book',final_status='approved',
                adjudicator_id='fixture:owner',adjudicated_at='2026-11-27T12:30:00+07:00',reviewer_confirmed='yes')
    final=edited(comparison/'adjudication.csv',tmp_path/'final-no-resolution.csv',decide)
    with pytest.raises(ValueError,match='resolution'):
        import_review(run,out,final,'final','dev',tmp_path/'no',finalize=True,comparison=comparison)
    final=edited(final,tmp_path/'final.csv',lambda rows:[r.update(resolution='Synthetic human decision fixture') for r in rows if r['p4_required']=='yes'])
    import_review(run,out,final,'final','dev',tmp_path/'canonical-final',finalize=True,comparison=comparison)
    _,rows=_rows(tmp_path/'canonical-final/canonical.csv')
    assert all(r['status']=='approved' and r['relevance']=='1' for r in rows)
    assert old_hashes==(sha(primary),sha(p4))
    # End-to-end exchange conversion into the existing validator, without metrics.
    approval=fill_labels(run)['approval'] # Authored fixture approvals only.
    import_review(run,out,primary,'primary','dev',tmp_path/'primary-canonical',finalize=True)
    import_review(run,out,p4,'p4','dev',tmp_path/'p4-canonical',finalize=True)
    valid=validate_labels(run,primary=tmp_path/'primary-canonical/canonical.csv',
        cross=tmp_path/'p4-canonical/canonical.csv',final=tmp_path/'canonical-final/canonical.csv',approval=approval,split='dev')
    assert len(valid)==report['rows']


def test_independent_reviewer_and_template_hash_required(handoff,tmp_path):
    run,out=handoff
    p=edited(out/'dev/primary.csv',tmp_path/'p.csv',confirm_all)
    c=edited(out/'dev/p4.csv',tmp_path/'c.csv',confirm_all)
    with pytest.raises(ValueError,match='independent'):compare_reviews(run,out,p,c,'dev',tmp_path/'no')
    with (out/'test/p4.csv').open('a',encoding='utf-8') as stream:stream.write('\n')
    with pytest.raises(ValueError,match='hash'):import_review(run,out,p,'primary','dev',tmp_path/'no-2')


@pytest.mark.parametrize('defect',['wrong_pool','unconfirmed'])
def test_metric_validator_rejects_wrong_exchange_binding_or_unconfirmed_labels(bundle,tmp_path,defect):
    args=fill_labels(bundle)
    columns,rows=_rows(args['primary'])
    columns+=['snapshot_id','run_sha256','scenario_sha256','pool_sha256','reviewer_confirmed','review_status']
    for row in rows:
        row.update(snapshot_id='rec-v1',run_sha256=sha(bundle/'run.json'),scenario_sha256=sha(bundle/'scenarios.json'),
            pool_sha256=sha(bundle/'pool.jsonl'),reviewer_confirmed='yes',review_status='confirmed')
    row=next(r for r in rows if int(r['scenario_id'][1:])<=8)
    if defect=='wrong_pool':row['pool_sha256']='0'*64
    else:row['reviewer_confirmed']=''
    path=tmp_path/'bad.csv';_csv(path,columns,rows)
    with pytest.raises(ValueError):validate_labels(bundle,primary=path,cross=args['cross'],final=args['final'],approval=args['approval'],split='dev')


def test_pool_metadata_source_mismatch_stops_export(handoff,tmp_path):
    run,_=handoff;directory=settings.snapshot_path/'rec-v1'
    source=load_recommendation_snapshot()
    with (directory/'catalog.sqlite').open('ab') as stream:stream.write(b'changed fixture bytes')
    with pytest.raises(ValueError,match='Snapshot/hash'):export_review(run,source,directory,tmp_path/'bad')


def test_all_pooled_editions_are_shown_once_per_work(monkeypatch,request,tmp_path):
    from src.evaluation.baselines import Tfidf
    # Mock only this fixture's lexical scores to select another edition than FAISS.
    monkeypatch.setattr(Tfidf,'score',lambda self,seeds:{bid:1. if bid=='A_alt' else 0. for bid in self.vectors})
    run=request.getfixturevalue('bundle');directory=settings.snapshot_path/'rec-v1'
    out=tmp_path/'multi-edition'
    export_review(run,load_recommendation_snapshot(),directory,out)
    _,rows=_rows(out/'dev/primary.csv')
    works=[r for r in rows if r['scenario_id']=='R01' and r['candidate_work_id']=='W_A']
    assert len(works)==1
    assert works[0]['candidate_book_ids']=='A; A_alt'
    assert 'Title A' in works[0]['candidate_titles'] and 'Title A_alt' in works[0]['candidate_titles']
    assert 'Summary A_alt' in works[0]['candidate_summaries']


@pytest.mark.parametrize('change_text',[False,True])
def test_windows_csv_line_endings_are_equivalent_but_text_changes_are_rejected(monkeypatch,request,tmp_path,change_text):
    from src.evaluation.baselines import Tfidf
    monkeypatch.setattr(Tfidf,'score',lambda self,seeds:{bid:1. if bid=='A_alt' else 0. for bid in self.vectors})
    run=request.getfixturevalue('bundle');out=tmp_path/'handoff'
    export_review(run,load_recommendation_snapshot(),settings.snapshot_path/'rec-v1',out)
    def windows(rows):
        for row in rows:
            row['candidate_summaries']=row['candidate_summaries'].replace('\n','\r\n')
        if change_text:rows[0]['candidate_summaries']+=' changed text'
    input_path=edited(out/'dev/primary.csv',tmp_path/'returned.csv',windows)
    if change_text:
        with pytest.raises(ValueError,match='Read-only'):import_review(run,out,input_path,'primary','dev',tmp_path/'no')
    else:
        report=import_review(run,out,input_path,'primary','dev',tmp_path/'draft')
        assert report['read_only_newline_differences']>0 and report['confirmed']==0
        assert (tmp_path/'draft/raw-input.csv').read_bytes()==input_path.read_bytes()
