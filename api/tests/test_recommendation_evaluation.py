"""C31/C33 technical fixtures. Synthetic judgements are never human ground truth."""

import csv
import json
import math
from pathlib import Path
import shutil
import unicodedata

import numpy as np
import pytest

from recommendation_fixture import create_snapshot
from src.config import settings
from src.evaluation.baselines import Tfidf, genre_scores, normalize
from src.evaluation.metrics import precision_ndcg_at5
from src.evaluation.recommendation import (create_pool, evaluate, freeze, rank_methods, read_cases,
    read_json, read_rows, review_sample, sha, validate_labels, write_json)
from src.services.recommendation import RecommendationRanker, NumpyBookScorer, select_candidate_ids
from src.services.recommendation_snapshot import load_recommendation_snapshot
from src.services.preference_source import BookMetadata
from src.schemas.common import Filters


@pytest.mark.parametrize('ranking,p,ndcg',[
    (['A','B','C'],.4,1),
    (['C','B','A'],.4,(1/math.log2(3)+3/math.log2(4))/(3+1/math.log2(3))),
    (['A'],.2,3/(3+1/math.log2(3))),
    ([],0,0),
])
def test_hand_computed_metrics(ranking,p,ndcg):
    result=precision_ndcg_at5(ranking,{'A':2,'B':1,'C':0})
    assert result['precision_at5']==p
    assert result['ndcg_at5']==pytest.approx(ndcg)


def test_no_relevant_and_missing_labels():
    assert precision_ndcg_at5(['A'],{'A':0})==dict(precision_at5=0,ndcg_at5=0,no_relevant_in_pool=True)
    with pytest.raises(ValueError,match='Unjudged'):precision_ndcg_at5(['A'],{})


@pytest.mark.parametrize('bad',[True,-1,3,1.5,'1',None])
def test_metric_bad_relevance(bad):
    with pytest.raises(ValueError):precision_ndcg_at5(['A'],{'A':bad})


def test_duplicate_ranked_work():
    with pytest.raises(ValueError):precision_ndcg_at5(['A','A'],{'A':2})


def test_tfidf_math_and_vietnamese_tokens():
    model=Tfidf({'a':'mèo mèo chó','b':'mèo'})
    assert model.idf['mèo']==1
    assert model.idf['chó']==pytest.approx(math.log(3/2)+1)
    a=1+math.log(2); b=math.log(3/2)+1
    assert model.vectors['a']['mèo']==pytest.approx(a/math.sqrt(a*a+b*b))
    assert model.score(['a'])['a']==pytest.approx(1)
    assert model.score(['a','b'])==pytest.approx(model.score(['b','a']))
    nfc='Tiếng Việt 123';nfd=unicodedata.normalize('NFD',nfc)
    assert Tfidf({'a':nfc,'b':nfd.upper()}).vectors['a']==Tfidf({'a':nfc,'b':nfd.upper()}).vectors['b']
    assert 'mèo' in model.idf and 'meo' not in model.idf


@pytest.mark.parametrize('texts',[{}, {'a':''},{'a':'__!!!'}])
def test_zero_tfidf_is_error(texts):
    with pytest.raises(ValueError):Tfidf(texts)


def test_zero_mean_profile():
    with pytest.raises(ValueError):normalize({'x':1e-9})


def metadata(work, genres=('g1',), author='Author',full=False):
    return BookMetadata('placeholder',work,(author,),genres,full)


def test_shared_selector_filters_before_dedup_and_exact_tie():
    books={bid:BookMetadata(bid,work,(author,),genres,full) for bid,work,author,genres,full in [
        ('S','WS','Author',('g1',),False),('A','WA','Wrong',('g1',),True),
        ('A_alt','WA','Match',('g1',),True),('B','WB','Match',('g2',),True),
        ('C','WC','Match',('g1',),True),('Pending','WP','Match',('g1',),True)]}
    scores={'S':1.,'A':.99,'A_alt':.8,'B':.8,'C':.80000001,'Pending':1.}
    eligible=set(books)-{'Pending'}
    filters=Filters(authors=['Match','Other'],genres=['g1','g2'],has_fulltext=True)
    assert select_candidate_ids(books,scores,eligible_ids=eligible,blocked_works={'WS'},filters=filters,limit=20)==['C','A_alt','B']
    assert select_candidate_ids(books,scores,eligible_ids=eligible,blocked_works={'WS','WA'},filters=filters,limit=20)==['C','B']
    assert genre_scores(books,['S','B'])['A']==1


def test_internal_top20_keeps_public_limit_and_fills_after_blocking():
    books={f'B{i:02}':BookMetadata(f'B{i:02}',f'W{i:02}',(),(),False) for i in range(35)}
    v=np.zeros(384,np.float32);v[0]=1
    ranker=RecommendationRanker(books,NumpyBookScorer(tuple(reversed(books)),lambda _:v),genre_codes=frozenset(),dataset_id='fixture')
    hits=ranker.evaluation_top20(['B00'],exclude_book_ids=['B01','B02'])
    assert len(hits)==20 and hits[0].book_id=='B03' and hits[-1].book_id=='B22'
    with pytest.raises(ValueError):ranker.recommend(['B00'],k=20)


@pytest.fixture
def bundle(tmp_path,monkeypatch):
    directory=create_snapshot(tmp_path)
    monkeypatch.setattr(settings,'SNAPSHOT_ROOT',str(tmp_path/'snapshots'))
    monkeypatch.setattr(settings,'CONTROL_ROOT',str(tmp_path/'control'))
    monkeypatch.setattr(settings,'SMARTLIBAI_DEMO_SNAPSHOT',None)
    monkeypatch.setattr(settings,'CLASSROOM_DEMO_SNAPSHOT',None)
    source=load_recommendation_snapshot()
    cases=tmp_path/'cases.json'
    write_json(cases,dict(format_version=1,snapshot_id=directory.name,scenarios=[dict(
        scenario_id=f'R{i:02}',split='dev' if i<=8 else 'test',status='draft',seed_book_ids=['Seed'],
        exclude_book_ids=[],filters={},intent='Authored technical fixture',rationale='Synthetic, not quality evaluation',
        evidence_refs=['fixture://metadata']) for i in range(1,21)]))
    output=tmp_path/'pool'
    before={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    create_pool(source,directory,cases,output)
    assert before=={p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    return output


def fill_labels(bundle):
    for name in ('primary','cross_review','final'):
        path=bundle/(name+'.csv')
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream);columns=reader.fieldnames;rows=list(reader)
        for row in rows:
            row.update(relevance='2' if row['work_id']=='W_A' else '0',rationale='Synthetic test only',evidence='fixture://book')
            if name=='final':row.update(status='approved',approved_by='fixture:adjudicator',approved_at='2026-11-27T00:00:00Z')
            else:row.update(annotator_id='fixture:P4' if name=='cross_review' else 'fixture:P02',annotated_at='2026-11-27T00:00:00Z')
        with path.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    approval=bundle/'approval.json'
    write_json(approval,dict(status='approved',approved_by='fixture:owner',approved_at='2026-11-27T00:00:00Z',
        scenario_sha256=sha(bundle/'scenarios.json'),run_sha256=sha(bundle/'run.json'),protocol='c31-c33-v1',
        primary_annotator_id='fixture:P02',cross_annotator_id='fixture:P4',cross_reviewer_role='P4'))
    return dict(primary=bundle/'primary.csv',cross=bundle/'cross_review.csv',final=bundle/'final.csv',approval=approval)


def edit_sheet(path,change):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames;rows=list(reader)
    change(rows)
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)


def test_pool_work_union_blindness_sample_and_source_integrity(bundle):
    run=read_json(bundle/'run.json');pool=read_rows(bundle/'pool.jsonl')
    assert run['catalog_books']==9 and run['corpus_books']==7 and run['corpus_works']==6
    assert len({(r['scenario_id'],r['work_id']) for r in pool})==len(pool)
    assert all(not set(r['book_ids']) & {'Seed','Pending1','Pending2'} for r in pool)
    for row in pool:
        assert {o['method'] for o in row['origins']}=={'e5_faiss','genre','tfidf'}
    cards=read_rows(bundle/'judging_cards.jsonl')
    assert all(not {'score','rank','method','origins'} & r.keys() for r in cards)
    sample=set(review_sample(pool))
    for split in ('dev','test'):
        pairs={(r['scenario_id'],r['work_id']) for r in pool if r['split']==split}
        assert len(sample & pairs)>=math.ceil(.2*len(pairs))
    assert (bundle/'handoff-p4.zip').is_file()


def test_blank_labels_never_become_zero(bundle):
    args=fill_labels(bundle)
    edit_sheet(args['final'],lambda rows:next(r for r in rows if int(r['scenario_id'][1:])<=8).update(relevance=''))
    with pytest.raises(ValueError):validate_labels(bundle,split='dev',**args)


@pytest.mark.parametrize('defect',['missing','duplicate','bad','unapproved','unresolved','same_annotator','unknown'])
def test_labels_refuse_invalid_or_unreviewed(bundle,defect):
    args=fill_labels(bundle)
    pair=next(p for p in read_json(bundle/'review_sample.json') if int(p[0][1:])<=8)
    def change(rows):
        row=next(r for r in rows if [r['scenario_id'],r['work_id']]==pair)
        if defect=='missing':rows.remove(row)
        elif defect=='duplicate':rows.append(dict(row))
        elif defect=='bad':row['relevance']='3'
        elif defect=='unapproved':row['status']='draft'
        elif defect=='unresolved':row['relevance']='1' if row['relevance']!='1' else '0'
        elif defect=='same_annotator':row['annotator_id']='fixture:P02'
        else:rows.append(dict(row,work_id='UNKNOWN'))
    edit_sheet(args['cross'] if defect=='same_annotator' else args['final'],change)
    with pytest.raises(ValueError):validate_labels(bundle,split='dev',**args)


def test_synthetic_dev_test_gate_freeze_and_one_use(bundle):
    args=fill_labels(bundle)
    dev=evaluate(bundle,split='dev',output=bundle/'dev-metric.json',**args)
    assert dev['case_count']==8 and len(dev['per_case'])==8
    with pytest.raises(ValueError,match='Test requires'):
        evaluate(bundle,split='test',output=bundle/'test-denied.json',**args)
    frozen=bundle/'freeze.json';freeze(bundle,output=frozen,**args)
    auth=bundle/'auth.json'
    write_json(auth,dict(action='run_test_once',freeze_sha256=sha(frozen),authorized_by='fixture:owner',
        authorized_at='2026-11-27T00:00:00Z',test_used_for_tuning=False,test_usage_history=[]))
    report=evaluate(bundle,split='test',output=bundle/'test-fixture.json',frozen=frozen,authorization=auth,**args)
    assert report['case_count']==12
    with pytest.raises(FileExistsError):
        evaluate(bundle,split='test',output=bundle/'again.json',frozen=frozen,authorization=auth,**args)


def test_frozen_file_mutation_blocks_test(bundle):
    args=fill_labels(bundle);frozen=bundle/'freeze.json';freeze(bundle,output=frozen,**args)
    auth=bundle/'auth.json'
    write_json(auth,dict(action='run_test_once',freeze_sha256=sha(frozen),authorized_by='fixture:owner',
        authorized_at='2026-11-27T00:00:00Z',test_used_for_tuning=False,test_usage_history=[]))
    args['final'].write_text(args['final'].read_text(encoding='utf-8')+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Frozen inputs changed'):
        evaluate(bundle,split='test',output=bundle/'no.json',frozen=frozen,authorization=auth,**args)


def test_freeze_is_portable_and_authorization_cannot_be_reused_by_renaming(bundle):
    args=fill_labels(bundle);frozen=bundle/'freeze.json';freeze(bundle,output=frozen,**args)
    moved=bundle.parent/'copied';shutil.copytree(bundle,moved)
    moved_args={role:moved/path.name for role,path in args.items()}
    auth=moved/'auth.json'
    write_json(auth,dict(action='run_test_once',freeze_sha256=sha(moved/'freeze.json'),authorized_by='fixture:owner',
        authorized_at='2026-11-27T00:00:00Z',test_used_for_tuning=False,test_usage_history=[]))
    report=evaluate(moved,split='test',output=moved/'test-fixture.json',frozen=moved/'freeze.json',authorization=auth,**moved_args)
    assert report['case_count']==12
    copy=moved/'renamed-auth.json';shutil.copyfile(auth,copy)
    with pytest.raises(FileExistsError):
        evaluate(moved,split='test',output=moved/'again.json',frozen=moved/'freeze.json',authorization=copy,**moved_args)


def test_tampered_pool_hash_refused(bundle):
    args=fill_labels(bundle)
    with (bundle/'pool.jsonl').open('a',encoding='utf-8') as f:f.write('{}\n')
    with pytest.raises(ValueError,match='hash'):validate_labels(bundle,split='dev',**args)


@pytest.fixture
def authored_scenarios(tmp_path):
    """Scenario validation must run without the private evaluation release."""
    path=tmp_path/'authored-scenarios.json'
    write_json(path,dict(format_version=1,snapshot_id='synthetic-scenarios',scenarios=[dict(
        scenario_id=f'R{i:02}',split='dev' if i<=8 else 'test',status='draft',
        seed_book_ids=[f'SyntheticBook{j}' for j in range(1,1+(i-1)%3+1)],
        exclude_book_ids=[],filters={},intent='Synthetic reading interest',
        rationale='Authored technical fixture; not a real evaluation scenario',
        evidence_refs=['fixture://synthetic-metadata']) for i in range(1,21)]))
    return path


def test_authored_case_split_is_draft_no_labels(authored_scenarios):
    data=read_cases(authored_scenarios)
    assert all(c['status']=='draft' for c in data['scenarios'])
    assert {len(c['seed_book_ids']) for c in data['scenarios']}=={1,2,3}


@pytest.mark.parametrize('filters,excluded,expected',[
    ({'authors':['Alternate']},[],{'W_A'}),
    ({'authors':['Alternate'],'genres':['g2']},[],set()),
    ({},['A_alt'],{'W_B','W_C','W_D','W_E'}),
    ({'genres':['g1','g2'],'authors':['Alternate','Author']},[],{'W_A','W_B','W_C','W_D','W_E'}),
])
def test_three_methods_share_eligibility_filters_and_work_exclusion(bundle,filters,excluded,expected):
    source=load_recommendation_snapshot()
    tfidf=Tfidf({bid:source.books[bid].summary for bid in source.eligible_ids})
    results=rank_methods(source,tfidf,dict(seed_book_ids=['Seed'],exclude_book_ids=excluded,filters=filters))
    for hits in results.values():
        assert {h['work_id'] for h in hits}==expected
        assert len({h['work_id'] for h in hits})==len(hits)
        if filters.get('authors')==['Alternate'] and expected:
            assert hits[0]['book_id']=='A_alt'


def test_dev_does_not_require_test_labels_and_disagreement_can_be_resolved(bundle):
    args=fill_labels(bundle)
    edit_sheet(args['final'],lambda rows:[r.update(relevance='') for r in rows if int(r['scenario_id'][1:])>8])
    assert len(validate_labels(bundle,split='dev',**args))>0
    pair=next(p for p in read_json(bundle/'review_sample.json') if int(p[0][1:])<=8)
    edit_sheet(args['cross'],lambda rows:next(r for r in rows if [r['scenario_id'],r['work_id']]==pair).update(relevance='1'))
    with pytest.raises(ValueError,match='Unresolved'):validate_labels(bundle,split='dev',**args)
    edit_sheet(args['final'],lambda rows:next(r for r in rows if [r['scenario_id'],r['work_id']]==pair).update(resolution='Synthetic adjudication, retain primary label'))
    assert len(validate_labels(bundle,split='dev',**args))>0


@pytest.mark.parametrize('defect',['wrong_split','duplicate_case'])
def test_scenario_split_rejected(tmp_path,defect,authored_scenarios):
    data=read_json(authored_scenarios)
    if defect=='wrong_split':data['scenarios'][0]['split']='test'
    else:data['scenarios'][0]['scenario_id']=data['scenarios'][1]['scenario_id']
    path=tmp_path/'cases.json';write_json(path,data)
    with pytest.raises(ValueError):read_cases(path)
