"""Synthetic validation only: no metric execution or freeze creation."""

import copy
import shutil

import pytest

from test_recommendation_evaluation import bundle, fill_labels
from test_recommendation_review import handoff
from src.evaluation.review import _rows, _csv
from src.evaluation.recommendation import read_json, sha, validate_labels, write_json, freeze_files
from src.evaluation.joint_review import PROTOCOL


@pytest.fixture
def joint(handoff):
    directory, exchange = handoff
    args = fill_labels(directory)
    release = directory.parent/'joint'
    release.mkdir()
    columns, raw = _rows(exchange/'test/primary.csv')
    for row in raw:
        row.update(relevance='2', rationale='Synthetic rationale', evidence='fixture://summary',
                   annotator_id='AI_fixture', review_status='draft')
    _csv(release/'raw.csv', columns, raw)
    confirmed = copy.deepcopy(raw)
    for row in confirmed:
        row.update(annotator_id='fixture:P02', annotated_at='2026-11-28T00:00:00Z',
                   reviewer_confirmed='yes', review_status='confirmed')
    _csv(release/'confirmed.csv', columns, confirmed)
    binding = {k: raw[0][k] for k in ('snapshot_id', 'run_sha256', 'scenario_sha256', 'pool_sha256')}
    canonical = [dict(scenario_id=r['scenario_id'], work_id=r['candidate_work_id'],
                     **{k:r[k] for k in ('relevance', 'rationale', 'evidence', 'annotator_id',
                                        'annotated_at', 'reviewer_confirmed', 'review_status')}, **binding)
                 for r in confirmed]
    _csv(release/'canonical.csv', list(canonical[0]), canonical)
    sample = {tuple(p) for p in read_json(directory/'review_sample.json') if int(p[0][1:]) > 8}
    confirmation = dict(record_type='explicit_user_review_confirmation_and_P4_agreement_attestation',
        confirmed_by='fixture:P02', confirmation_recorded_at='2026-11-28T00:00:00Z',
        user_answer='Synthetic user confirmation', p4_reviewer_identity=None,
        p4_asserted_role='P4',
        p4_independent_review_verified=False, primary_rows_user_confirmed=len(raw),
        p4_pairs_user_attests_agreement=len(sample), review_sample_sha256=sha(directory/'review_sample.json'),
        source_primary_sha256=sha(release/'raw.csv'), confirmed_primary_sha256=sha(release/'confirmed.csv'),
        canonical_primary_sha256=sha(release/'canonical.csv'), pairs=[dict(scenario_id=r['scenario_id'],
        work_id=r['work_id'], relevance=2, p4_agreement_attested=(r['scenario_id'],r['work_id']) in sample)
        for r in canonical], **binding)
    write_json(release/'confirmation.json', confirmation)
    write_json(release/'acceptance.json', dict(
        record_type='user_attested_team_acceptance_of_joint_review_exception',
        reported_by='fixture:P02', recorded_at='2026-11-28T00:00:00Z', user_statement='Synthetic acceptance',
        review_confirmation_sha256=sha(release/'confirmation.json'),
        shared_review_accepted_by_team_as_reported=True, independent_review_performed=False, **binding))
    write_json(release/'parent.json', dict(protocol='c31-c33-v1'))
    write_json(release/'protocol.json', dict(protocol=PROTOCOL, parent_protocol_sha256=sha(release/'parent.json'),
        exception_scope='test_only_fixed_sample', independent_test_review_satisfied=False,
        spec_acceptance_claim=False, **binding))
    approval = read_json(args['approval'])
    approval.update(protocol=PROTOCOL, joint_review_files={role:dict(path=name,sha256=sha(release/name))
        for role,name in dict(protocol='protocol.json',parent_protocol='parent.json',confirmation='confirmation.json',
        acceptance='acceptance.json',primary_source='raw.csv',confirmed_primary='confirmed.csv',
        canonical_primary='canonical.csv').items()})
    write_json(release/'approval.json', approval)
    _, primary = _rows(args['primary'])
    primary = [dict(r,review_status='confirmed',reviewer_confirmed='yes',**binding)
               for r in primary if int(r['scenario_id'][1:]) <= 8] + canonical
    _csv(release/'primary.csv', list(primary[0]), primary)
    cross_cols, cross = _rows(args['cross'])
    _csv(release/'cross.csv', cross_cols, [r for r in cross if int(r['scenario_id'][1:]) <= 8])
    _, final = _rows(args['final'])
    for row in final:
        row.update(binding, reviewer_confirmed='yes')
        row.update(review_mode='', joint_review_confirmation_sha256='', team_exception_sha256='',
                   original_independent_protocol_satisfied='')
        if int(row['scenario_id'][1:]) > 8:
            row.update(relevance='2', rationale='Synthetic rationale', evidence='fixture://summary',
                       approved_by='fixture:owner', review_mode='joint_review_exception',
                       joint_review_confirmation_sha256=sha(release/'confirmation.json'),
                       team_exception_sha256=sha(release/'acceptance.json'), original_independent_protocol_satisfied='no')
    _csv(release/'final.csv', list(final[0]), final)
    return directory, dict(primary=release/'primary.csv',cross=release/'cross.csv',
                           final=release/'final.csv',approval=release/'approval.json')


def mutate(path, change):
    data = read_json(path)
    change(data)
    write_json(path,data)


def repin(args, role):
    approval = read_json(args['approval'])
    ref = approval['joint_review_files'][role]
    ref['sha256'] = sha(args['approval'].parent/ref['path'])
    write_json(args['approval'],approval)


def test_joint_validation_preserves_dev_and_discloses_exception(joint):
    directory,args = joint
    assert validate_labels(directory,split='dev',**args)
    assert validate_labels(directory,split='test',**args)
    assert not (directory/'freeze.json').exists()
    pins = freeze_files(directory,**args)  # Computes hashes only, does not create freeze.
    assert 'joint_review/acceptance' in pins and 'joint_review/primary_source' in pins
    moved = directory.parent/'moved'
    shutil.copytree(args['approval'].parent,moved)
    assert validate_labels(directory,split='test',**{k:moved/v.name for k,v in args.items()})


@pytest.mark.parametrize('role', ['protocol','parent_protocol','confirmation','acceptance',
                                  'primary_source','confirmed_primary','canonical_primary'])
def test_joint_provenance_hash_tampering_refused(joint,role):
    directory,args = joint
    ref = read_json(args['approval'])['joint_review_files'][role]
    with (args['approval'].parent/ref['path']).open('a',encoding='utf-8') as stream:
        stream.write('\n')
    with pytest.raises(ValueError,match='hash'):
        validate_labels(directory,split='test',**args)


@pytest.mark.parametrize('defect', ['missing_pair','duplicate_pair','invalid_label','wrong_sample',
    'missing_acceptance','different_snapshot','invented_p4','independent_claim','wrong_final_evidence',
    'wrong_final_label','missing_final_binding','missing_primary','cross_impersonation','path_escape'])
def test_joint_semantic_defects_refused_even_with_updated_file_hash(joint,defect):
    directory,args = joint
    root=args['approval'].parent
    if defect in ('missing_pair','duplicate_pair','invalid_label','wrong_sample','invented_p4'):
        def change(data):
            if defect=='missing_pair':data['pairs'].pop()
            elif defect=='duplicate_pair':data['pairs'].append(data['pairs'][0])
            elif defect=='invalid_label':data['pairs'][0]['relevance']=True
            elif defect=='wrong_sample':data['pairs'][0]['p4_agreement_attested']=not data['pairs'][0]['p4_agreement_attested']
            else:data['p4_reviewer_identity']='invented'
        mutate(root/'confirmation.json',change)
        repin(args,'confirmation')
        mutate(root/'acceptance.json',lambda d:d.update(review_confirmation_sha256=sha(root/'confirmation.json')))
        repin(args,'acceptance')
    elif defect in ('missing_acceptance','different_snapshot'):
        mutate(root/'acceptance.json',lambda d:d.update(**({'shared_review_accepted_by_team_as_reported':False}
            if defect=='missing_acceptance' else {'snapshot_id':'other'})))
        repin(args,'acceptance')
    elif defect=='independent_claim':
        mutate(root/'protocol.json',lambda d:d.update(independent_test_review_satisfied=True))
        repin(args,'protocol')
    elif defect=='path_escape':
        mutate(args['approval'],lambda d:d['joint_review_files']['acceptance'].update(path='../acceptance.json'))
    else:
        cols,rows=_rows(args['primary'] if defect=='missing_primary' else args['final'])
        if defect=='missing_primary':rows=[r for r in rows if r != next(r for r in rows if int(r['scenario_id'][1:])>8)]
        elif defect=='cross_impersonation':
            cols,rows=_rows(args['cross']);sample=read_json(root/'confirmation.json')['pairs'][0]
            rows.append(dict(rows[0],scenario_id=sample['scenario_id'],work_id=sample['work_id']))
        else:
            row=next(r for r in rows if int(r['scenario_id'][1:])>8)
            field={'wrong_final_evidence':'evidence','wrong_final_label':'relevance',
                   'missing_final_binding':'team_exception_sha256'}[defect]
            row[field]='1' if field=='relevance' else 'changed'
        path=args['primary'] if defect=='missing_primary' else args['cross'] if defect=='cross_impersonation' else args['final']
        path.unlink();_csv(path,cols,rows)
    with pytest.raises((ValueError,OSError)):
        validate_labels(directory,split='test',**args)


def test_joint_cannot_silently_downgrade_to_original_protocol(joint):
    directory,args=joint
    mutate(args['approval'],lambda d:d.update(protocol='c31-c33-v1'))
    with pytest.raises(ValueError,match='Missing labels'):
        validate_labels(directory,split='test',**args)
