"""Intent-only versioning on authored fixtures; no metric or human approval."""

import copy

import pytest

from test_recommendation_evaluation import bundle, edit_sheet
from src.config import settings
from src.services.recommendation_snapshot import load_recommendation_snapshot
from src.evaluation.recommendation import read_json, read_rows, sha, write_json, verified_run
from src.evaluation.revision import revise_scenarios
from src.evaluation.review import export_review, import_review, _rows


def new_cases(bundle,tmp_path):
    data=read_json(bundle/'scenarios.json')
    data['scenario_version']='fixture-v2'
    data['scenarios'][2].update(intent='Revised authored fixture intent',judging_guidance='Fixture rubric, not a real label')
    path=tmp_path/'cases-v2.json';write_json(path,data)
    return path


def test_intent_revision_reuses_retrieval_and_keeps_guidance_in_all_sheets(bundle,tmp_path):
    cases=new_cases(bundle,tmp_path);output=tmp_path/'v2'
    before={p.name:sha(p) for p in bundle.iterdir() if p.is_file()}
    report=revise_scenarios(bundle,cases,output)
    assert report['changed_scenarios']==['R03'] and not report['rankings_recomputed']
    assert not report['metrics_computed'] and report['human_approval'] is None
    for name in ('pool.jsonl','rankings.jsonl','review_sample.json'):
        assert (output/name).read_bytes()==(bundle/name).read_bytes()
    assert before=={p.name:sha(p) for p in bundle.iterdir() if p.is_file()}
    verified_run(output)
    handoff=tmp_path/'handoff-v2'
    export_review(output,load_recommendation_snapshot(),settings.snapshot_path/'rec-v1',handoff)
    for role in ('primary','p4'):
        _,rows=_rows(handoff/'dev'/(role+'.csv'))
        matches=[r for r in rows if r['scenario_id']=='R03']
        assert matches and all(r['judging_guidance']=='Fixture rubric, not a real label' for r in matches)
        assert all(not r['relevance'] and not r['reviewer_confirmed'] for r in rows)
    assert 'Fixture rubric' in (handoff/'scenarios-review.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('field,value',[
    ('seed_book_ids',['B']),('exclude_book_ids',['A']),('filters',{'genres':['g1']}),('status','approved'),
])
def test_retrieval_or_approval_change_cannot_reuse_rankings(bundle,tmp_path,field,value):
    path=new_cases(bundle,tmp_path);data=read_json(path)
    data['scenarios'][2][field]=value;write_json(path,data)
    with pytest.raises(ValueError):revise_scenarios(bundle,path,tmp_path/'no')


def test_existing_label_is_audited_preserved_and_never_migrated(bundle,tmp_path):
    path=new_cases(bundle,tmp_path)
    edit_sheet(bundle/'primary.csv',lambda rows:next(r for r in rows if r['scenario_id']=='R03').update(relevance='0',rationale='Synthetic existing judgement'))
    digest=sha(bundle/'primary.csv')
    report=revise_scenarios(bundle,path,tmp_path/'v2')
    assert report['label_review_required']
    assert any('R03' in row['affected_scenarios'] for row in report['label_audit'])
    assert sha(bundle/'primary.csv')==digest
    assert all(not r['relevance'] for r in _rows(tmp_path/'v2/primary.csv')[1])


def test_old_exchange_cannot_be_imported_into_new_scenario_version(bundle,tmp_path):
    source=load_recommendation_snapshot();directory=settings.snapshot_path/'rec-v1'
    old=tmp_path/'old-handoff';export_review(bundle,source,directory,old)
    output=tmp_path/'v2';revise_scenarios(bundle,new_cases(bundle,tmp_path),output)
    new=tmp_path/'new-handoff';export_review(output,source,directory,new)
    with pytest.raises(ValueError):
        import_review(output,new,old/'dev/primary.csv','primary','dev',tmp_path/'bad-import')
