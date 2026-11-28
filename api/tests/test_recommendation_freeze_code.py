"""Code pinning uses synthetic bundles only, never real test labels/metrics."""

import pytest

from test_recommendation_evaluation import bundle, fill_labels
from src.evaluation import recommendation as evaluation


@pytest.fixture
def pinned_code(bundle,monkeypatch):
    directory=bundle.parent/'code-copy'
    directory.mkdir()
    paths={}
    for role,path in evaluation.metric_code_paths().items():
        dest=directory/(role+'.py')
        dest.write_bytes(path.read_bytes())
        paths[role]=dest
    monkeypatch.setattr(evaluation,'metric_code_paths',lambda:paths)
    return paths


@pytest.mark.parametrize('role',['metrics','evaluator','joint_review','review','cli'])
def test_code_changed_after_fixture_freeze_blocks_test_before_metrics(bundle,pinned_code,role):
    args=fill_labels(bundle)
    frozen=bundle/'freeze.json'
    evaluation.freeze(bundle,output=frozen,**args)
    record=evaluation.read_json(frozen)
    assert record['format_version']==2 and 'code/'+role in record['files']
    authorization=bundle/'authorization.json'
    evaluation.write_json(authorization,dict(action='run_test_once',freeze_sha256=evaluation.sha(frozen),
        authorized_by='fixture:owner',authorized_at='2026-11-28T00:00:00Z',
        test_used_for_tuning=False,test_usage_history=[]))
    with pinned_code[role].open('ab') as stream:stream.write(b'\n# Changed after fixture freeze\n')
    output=bundle/'blocked-metrics.json'
    with pytest.raises(ValueError,match='Frozen inputs changed'):
        evaluation.evaluate(bundle,split='test',output=output,frozen=frozen,
                            authorization=authorization,**args)
    assert not output.exists() and not list(bundle.glob('test-use-*.json'))


def test_code_hashes_are_portable_across_lf_crlf_and_paths(pinned_code):
    before=evaluation.metric_code_hashes()
    for path in pinned_code.values():
        normalized=path.read_bytes().replace(b'\r\n',b'\n')
        path.write_bytes(normalized.replace(b'\n',b'\r\n'))
    assert evaluation.metric_code_hashes()==before
    for path in pinned_code.values():path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
    assert evaluation.metric_code_hashes()==before


def test_legacy_freeze_without_code_pins_is_rejected(bundle):
    args=fill_labels(bundle)
    frozen=bundle/'legacy-freeze.json'
    evaluation.write_json(frozen,dict(format_version=1,status='frozen',
        files={k:v for k,v in evaluation.freeze_files(bundle,**args).items() if not k.startswith('code/')},
        run_sha256=evaluation.sha(bundle/'run.json')))
    authorization=bundle/'authorization.json'
    evaluation.write_json(authorization,dict(action='run_test_once',freeze_sha256=evaluation.sha(frozen),
        authorized_by='fixture:owner',authorized_at='2026-11-28T00:00:00Z',
        test_used_for_tuning=False,test_usage_history=[]))
    with pytest.raises(ValueError,match='Frozen inputs changed'):
        evaluation.evaluate(bundle,split='test',output=bundle/'blocked.json',frozen=frozen,
                            authorization=authorization,**args)
