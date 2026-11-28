"""Version judgement intent/guidance while retaining identical retrieval bytes."""

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

from .recommendation import (LABEL_COLUMNS, FINAL_COLUMNS, read_cases, read_json, read_rows,
    sha, verified_run, write_json, write_rows, write_sheet)
from .review import _csv, _rows


def revise_scenarios(directory,cases_path,output,*,label_files=()):
    old_run=verified_run(directory)
    old=read_cases(directory/'scenarios.json');new=read_cases(cases_path)
    if new['snapshot_id']!=old['snapshot_id']:
        raise ValueError('Snapshot changed: rebuild rankings/pool')
    if [c['scenario_id'] for c in old['scenarios']]!=[c['scenario_id'] for c in new['scenarios']]:
        raise ValueError('Scenario IDs/order changed: rebuild rankings/pool')
    allowed={'intent','judging_guidance'};changed=[]
    for a,b in zip(old['scenarios'],new['scenarios']):
        if {k:v for k,v in a.items() if k not in allowed}!={k:v for k,v in b.items() if k not in allowed}:
            raise ValueError('Retrieval or other scenario fields changed: rebuild/review pool')
        if b['status']!='draft':raise ValueError('Revision cannot assert human approval')
        if any(a.get(k,'')!=b.get(k,'') for k in allowed):changed.append(b['scenario_id'])
    version=new.get('scenario_version')
    if not isinstance(version,str) or not version.strip() or version==old.get('scenario_version') or not changed:
        raise ValueError('A new scenario_version and intent/guidance changes are required')
    labels=[]
    files=list(dict.fromkeys([directory/n for n in ('primary.csv','cross_review.csv','final.csv')]+list(label_files)))
    for path in files:
        _,rows=_rows(path)
        affected=set();count=0
        for row in rows:
            if any(row.get(k,'') for k in ('relevance','final_label','primary_label','p4_label','human_approval')):
                count+=1
                if row['scenario_id'] in changed:affected.add(row['scenario_id'])
        labels.append(dict(path=str(Path(path).resolve()),sha256=sha(path),nonblank_rows=count,
            affected_scenarios=sorted(affected)))
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    stable=['pool.jsonl','rankings.jsonl','review_sample.json']
    for name in stable:(output/name).write_bytes((directory/name).read_bytes())
    (output/'scenarios.json').write_bytes(Path(cases_path).read_bytes())
    by_case={c['scenario_id']:c for c in new['scenarios']}
    cards=read_rows(directory/'judging_cards.jsonl')
    for card in cards:
        case=by_case[card['scenario_id']]
        card.update(intent=case['intent'],judging_guidance=case.get('judging_guidance',''))
    write_rows(output/'judging_cards.jsonl',cards)
    sample={tuple(x) for x in read_json(output/'review_sample.json')}
    columns=['scenario_id','work_id','split','intent','judging_guidance','filters','seeds','candidates']
    for name,rows in [('judging_cards.csv',cards),('cross_review_cards.csv',[c for c in cards if (c['scenario_id'],c['work_id']) in sample])]:
        values=[{k:json.dumps(c[k],ensure_ascii=False) if isinstance(c[k],(dict,list)) else c[k] for k in columns} for c in rows]
        _csv(output/name,columns,values)
    pairs=[(c['scenario_id'],c['work_id']) for c in cards]
    write_sheet(output/'primary.csv',LABEL_COLUMNS,pairs)
    write_sheet(output/'cross_review.csv',LABEL_COLUMNS,[p for p in pairs if p in sample])
    write_sheet(output/'final.csv',FINAL_COLUMNS,pairs)
    with zipfile.ZipFile(output/'handoff-p4.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ('cross_review.csv','cross_review_cards.csv','review_sample.json'):
            archive.write(output/name,arcname=name)
        archive.writestr('README.txt','Scenario intent/guidance revised. Read the per-case guidance.\n'
            'Labels/approval remain blank. Old labels require review, never migrate automatically.\n'
            'No rankings or metrics were recomputed. Independent P4 review is still required.\n')
    revision=dict(kind='intent_guidance_only',scenario_version=version,
        revised_at=datetime.now(timezone.utc).isoformat(),parent_run_sha256=sha(directory/'run.json'),
        previous_scenario_sha256=old_run['scenario_sha256'],scenario_sha256=sha(cases_path),changed_scenarios=changed,
        changes=[dict(scenario_id=a['scenario_id'],previous_intent=a['intent'],intent=b['intent'],
            previous_guidance=a.get('judging_guidance',''),judging_guidance=b.get('judging_guidance',''))
            for a,b in zip(old['scenarios'],new['scenarios']) if a['scenario_id'] in changed],
        retrieval_inputs_unchanged=True,rankings_recomputed=False,metrics_computed=False,
        retained_artifacts={name:sha(output/name) for name in stable},label_audit=labels,
        label_review_required=any(r['affected_scenarios'] for r in labels),human_approval=None,
        note='Old inputs/labels preserved. Fresh empty sheets; no automatic approval or label migration.',
        revision_tool_sha256=sha(Path(__file__)))
    write_json(output/'revision.json',revision)
    run=copy.deepcopy(old_run)
    run.update(status='awaiting_human_review_after_intent_revision',scenario_version=version,
        scenario_sha256=sha(cases_path),parent_run_sha256=sha(directory/'run.json'),
        ranking_provenance=dict(run_sha256=sha(directory/'run.json'),code_commit=old_run['code_commit'],
            rankings_sha256=sha(directory/'rankings.jsonl')),revision_sha256=sha(output/'revision.json'))
    names=['scenarios.json','pool.jsonl','rankings.jsonl','judging_cards.jsonl','judging_cards.csv',
        'cross_review_cards.csv','handoff-p4.zip','review_sample.json','revision.json']
    run['artifacts']={name:sha(output/name) for name in names}
    write_json(output/'run.json',run)
    return revision
