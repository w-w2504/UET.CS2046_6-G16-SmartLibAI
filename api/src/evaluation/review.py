"""C31 blinded Excel exchange, draft imports and human adjudication. No metrics."""

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import zipfile

from src.schemas.recommend import RecommendationRequest
from src.services.recommendation_response import validate_catalog_input
from src.services.recommendation_response import build_response
from .recommendation import (METHODS, LABEL_COLUMNS, FINAL_COLUMNS, read_cases, read_json,
    read_rows, review_sample, sha, source_hashes, verified_run, write_json, _identity)
from ai_library.bm25_search import tokenize

CONTEXT = ['snapshot_id','run_sha256','scenario_sha256','pool_sha256']
LABEL_EDIT = ['relevance','rationale','evidence','annotator_id','annotated_at',
              'review_status','review_note','reviewer_confirmed']
FINAL_EDIT = ['final_label','final_rationale','final_evidence','final_status',
              'adjudicator_id','adjudicated_at','resolution','reviewer_confirmed']
META = ['scenario_id','split','intent','judging_guidance','filters','exclude_book_ids','exclude_titles','seed_book_ids','seed_titles','seed_summaries',
        'candidate_work_id','candidate_book_ids','candidate_titles','candidate_authors',
        'candidate_genres','candidate_topics','candidate_summaries','edition_relationship','evidence_refs']
RELATION = 'Một nhãn cho work; các book_id bên dưới là các ấn bản làm căn cứ, không phải nhãn độc lập.'


def _new_dir(path):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    return path


def _csv(path,columns,rows):
    with Path(path).open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def _rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream,strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
            raise ValueError('Missing/duplicate CSV columns; import as UTF-8 comma-delimited text')
        rows=list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('Malformed CSV row/column count')
    return reader.fieldnames,rows


def _pair(row):
    return row['scenario_id'],row.get('work_id',row.get('candidate_work_id'))


def _indexed(rows):
    indexed={}
    for row in rows:
        key=_pair(row)
        if key in indexed: raise ValueError('Duplicate scenario/work row')
        indexed[key]=row
    return indexed


def _binding(run,directory):
    return dict(snapshot_id=run['snapshot_id'],run_sha256=sha(directory/'run.json'),
        scenario_sha256=run['scenario_sha256'],pool_sha256=sha(directory/'pool.jsonl'))


def _metadata(source,bid):
    book=source.books[bid];meta=source.metadata[bid]
    return dict(book_id=bid,work_id=book.work_id,title=book.title,authors=list(book.authors),
        genres=[source.labels['genre'][c] for c in sorted(book.genres)],
        topics=[source.labels['topic'][c] for c in sorted(meta.topics)],summary=book.summary,
        has_fulltext=book.has_fulltext,evidence_ref=f'{source.snapshot_id}/catalog.sqlite#books/{bid}')


def verify_review_source(directory,source,snapshot_dir):
    run=verified_run(directory);cases=read_cases(directory/'scenarios.json')['scenarios']
    for relative,digest in run['code_hashes'].items():
        portable=relative.replace('\\','/')
        if portable.endswith(('baselines.py','preference.py','recommendation_faiss.py','services/recommendation.py')):
            path=Path(__file__).resolve().parents[3]/portable
            if sha(path)!=digest:raise ValueError('Scoring code changed: review/rebuild pool and judge new candidates first')
    if source.snapshot_id!=run['snapshot_id'] or source_hashes(snapshot_dir)!=run['source_hashes']:
        raise ValueError('Snapshot/hash differs from original pool')
    if source.manifest_sha256!=run['source_hashes']['manifest.json']:
        raise ValueError('Loaded snapshot differs from pool')
    pool=read_rows(directory/'pool.jsonl');by_pool=_indexed(pool)
    cards=_indexed(read_rows(directory/'judging_cards.jsonl'))
    rankings=read_rows(directory/'rankings.jsonl')
    by_rank={(r['scenario_id'],r['method']):r for r in rankings}
    if len(by_rank)!=len(rankings) or set(by_rank)!={(c['scenario_id'],m) for c in cases for m in METHODS}:
        raise ValueError('Missing/duplicate scenario/method ranking')
    expected={}
    for case in cases:
        payload=RecommendationRequest(seed_book_ids=case['seed_book_ids'],exclude_book_ids=case['exclude_book_ids'],filters=case['filters'])
        excluded=validate_catalog_input(source,payload)
        response=build_response(source,payload,'00000000-0000-4000-8000-000000000031')
        if [h.book_id for h in response.items]!=[h['book_id'] for h in by_rank[case['scenario_id'],'e5_faiss']['items'][:5]]:
            raise ValueError('E5 pool top5 differs from current C17')
        blocked=excluded | {source.metadata[bid].work_id for bid in payload.seed_book_ids}
        for method in METHODS:
            ranking=by_rank[case['scenario_id'],method]
            if ranking['split']!=case['split'] or len(ranking['items'])>20:
                raise ValueError('Ranking split/depth changed')
            seen=set()
            for rank,hit in enumerate(ranking['items'],1):
                bid=hit['book_id'];meta=source.metadata[bid]
                if (bid not in source.eligible_ids or meta.work_id!=hit['work_id'] or meta.work_id in blocked
                        or meta.work_id in seen or hit['rank']!=rank or not math.isfinite(hit['score'])):
                    raise ValueError('Invalid/duplicate/ineligible ranked work')
                seen.add(meta.work_id);f=payload.filters
                if f and ((f.authors and not set(f.authors).intersection(meta.authors))
                    or (f.genres and not set(f.genres).intersection(meta.genres))
                    or (f.has_fulltext is not None and f.has_fulltext!=meta.has_fulltext)):
                    raise ValueError('Ranked book violates filters')
                key=case['scenario_id'],hit['work_id']
                expected.setdefault(key,[]).append(dict(method=method,**hit))
    if set(expected)!=set(by_pool) or set(cards)!=set(by_pool):
        raise ValueError('Pool/cards/rankings do not describe the same pairs')
    for case in cases:
        for key,row in by_pool.items():
            if key[0]!=case['scenario_id']:continue
            card=cards[key]
            if (row['origins']!=expected[key] or row['split']!=case['split']
                    or set(row['book_ids'])!={o['book_id'] for o in expected[key]}
                    or card['candidates']!=[_metadata(source,bid) for bid in row['book_ids']]
                    or card['seeds']!=[_metadata(source,bid) for bid in case['seed_book_ids']]
                    or card['intent']!=case['intent'] or card['filters']!=case['filters']
                    or card.get('judging_guidance','')!=case.get('judging_guidance','')):
                raise ValueError('Pool or judging metadata differs from snapshot/scenario')
    sample={tuple(x) for x in read_json(directory/'review_sample.json')}
    if sample!=set(review_sample(pool)):raise ValueError('Review sample differs from fixed SHA sample')
    for name,keys in [('primary.csv',set(by_pool)),('final.csv',set(by_pool)),('cross_review.csv',sample)]:
        _,rows=_rows(directory/name)
        if set(_indexed(rows))!=keys:raise ValueError('Original sheet IDs differ from pool/sample')
    return run,cases,pool,cards,sample


def near_duplicates(cases,source):
    warnings=[]
    for i,a in enumerate(cases):
        for b in cases[i+1:]:
            works=[{source.metadata[x].work_id for x in c['seed_book_ids']} for c in (a,b)]
            same=(works[0]==works[1] and a['filters']==b['filters'] and set(a['exclude_book_ids'])==set(b['exclude_book_ids']))
            shared=works[0]&works[1]
            tokens=[set(tokenize(c['intent'])) for c in (a,b)]
            overlap=len(tokens[0]&tokens[1])/len(tokens[0]|tokens[1]) if tokens[0]|tokens[1] else 0
            if same or shared or overlap>=.5:
                warnings.append(dict(scenarios=[a['scenario_id'],b['scenario_id']],
                    kind='same_inputs_review_intent' if same else 'shared_seed_work' if shared else 'similar_intent_tokens',
                    cross_split=a['split']!=b['split'],shared_work_ids=sorted(shared),intent_token_jaccard=overlap))
    return warnings


GUIDE='''# Chấm C31 độc lập — chưa có phê duyệt hoặc ground truth

Mỗi dòng là một cặp scenario_id/work_id. Chỉ điền các cột nhập được liệt kê;
không sửa ID, metadata, snapshot hoặc hash. Tất cả nhãn/xác nhận ban đầu để trống.
Nhập CSV bằng Excel Data → From Text/CSV, UTF-8, dấu phẩy; giữ cột ID/hash và
relevance dạng Text. Lưu một bản mới CSV UTF-8, không ghi đè bản gốc.

0 = không phù hợp; 1 = liên quan một phần; 2 = phù hợp rõ. Chấm theo ý định và
summary/metadata, không chỉ vì cùng tác giả/thể loại. Nếu thiếu căn cứ: để trống
relevance, review_status=needs_review và ghi review_note. Ô trống không phải 0.
Không đặt công thức hoặc đổi 1 thành 1.0/1,0. Có nhiều ấn bản thì đọc tất cả các
căn cứ và ghi một nhãn cho work đó, không thêm dòng.

Cột được điền: relevance, rationale, evidence, annotator_id, annotated_at,
review_status, review_note, reviewer_confirmed. annotated_at dùng thời điểm thật
có timezone, ví dụ định dạng YYYY-MM-DDTHH:MM:SS+07:00. Khi thực sự xác nhận dòng:
review_status=confirmed, reviewer_confirmed=yes, đủ lý do/evidence và danh tính.
Chưa xác nhận thì để trống hoặc draft/needs_review; được lưu và nhập nháp, chưa
được chuyển thành nhãn chuẩn dùng cho metric.

P4 chấm độc lập trước khi xem nhãn primary. Hai thư mục dev/test tách riêng;
không dùng nhãn test để phân tích/chỉnh phương pháp. Đây là pool để chấm, không
phải kết quả chất lượng test. Không đo metric khi chưa duyệt dữ liệu.
'''


def export_review(directory,source,snapshot_dir,output):
    before=source_hashes(snapshot_dir)
    run,cases,pool,cards,sample=verify_review_source(directory,source,snapshot_dir)
    output=_new_dir(output);binding=_binding(run,directory)
    warnings=near_duplicates(cases,source)
    reviews=[]
    for c in cases:
        filter_labels=dict(c['filters'])
        if 'genres' in filter_labels:filter_labels['genres']=[source.labels['genre'][x] for x in filter_labels['genres']]
        row=dict(scenario_id=c['scenario_id'],split=c['split'],
            seed_book_ids='; '.join(c['seed_book_ids']),seed_titles='; '.join(source.books[x].title for x in c['seed_book_ids']),
            seed_work_ids='; '.join(source.metadata[x].work_id for x in c['seed_book_ids']),
            filters=json.dumps(c['filters'],ensure_ascii=False),filter_labels=json.dumps(filter_labels,ensure_ascii=False),
            exclude_book_ids='; '.join(c['exclude_book_ids']),exclude_titles='; '.join(source.books[x].title for x in c['exclude_book_ids']),
            intent=c['intent'],judging_guidance=c.get('judging_guidance',''),rationale=c['rationale'],evidence_refs='; '.join(c['evidence_refs']),
            technical_status='PASS',human_approval='',approved_by='',approved_at='',edit_notes='',**binding)
        reviews.append(row)
    _csv(output/'scenarios-review.csv',list(reviews[0]),reviews)
    def esc(value):return str(value).replace('|','\\|').replace('\n','<br>')
    markdown=['# Duyệt 20 case C31 — nháp, chưa được người duyệt','',
        'Kỹ thuật PASS không đồng nghĩa tình huống đã được duyệt. Điền human_approval, approved_by, approved_at, edit_notes trong CSV mới. Không tự sửa seed/split trong pool.',
        '', '| Case / split | Sách seed (ID/work ở chi tiết) | Filters / exclude | Ý định | Hướng dẫn chấm riêng | Duyệt / người / ghi chú |',
        '| --- | --- | --- | --- | --- | --- |']
    for c,row in zip(cases,reviews):
        seeds='<br>'.join(source.books[bid].title for bid in c['seed_book_ids'])
        markdown.append('| '+' | '.join(map(esc,[c['scenario_id']+' / '+c['split'],seeds,
            row['filter_labels']+' / '+(row['exclude_titles'] or '(không)'),c['intent'],c.get('judging_guidance',''),'']))+' |')
    markdown+=['','## Cặp cần xem lại (không tự xóa)','']+[f"- {w['scenarios'][0]} / {w['scenarios'][1]}: {w['kind']}; cross_split={w['cross_split']}." for w in warnings]
    markdown+=['','## Chi tiết ID và căn cứ','']
    for c in cases:
        markdown+=[f"### {c['scenario_id']} ({c['split']})",'']
        markdown += [f"- {source.books[bid].title}: book_id=`{bid}`, work_id=`{source.metadata[bid].work_id}`." for bid in c['seed_book_ids']]
        markdown += [f"- Ý định: {c['intent']}",f"- Hướng dẫn chấm riêng: {c.get('judging_guidance') or 'Theo rubric chung.'}",f"- Căn cứ đề xuất: {c['rationale']}",
            '- Nguồn metadata: '+'; '.join(c['evidence_refs']),
            '- Exclude: '+('; '.join(f"{source.books[bid].title} (`{bid}`)" for bid in c['exclude_book_ids']) or '(không)'),
            '- Duyệt / người duyệt / thời điểm / ghi chú: để trống, chờ con người.','']
    (output/'scenarios-review.md').write_text('\n'.join(markdown)+'\n',encoding='utf-8')
    write_json(output/'scenario-checks.json',dict(technical_status='passed',case_count=20,dev_cases=8,test_cases=12,
        human_approval=None,near_duplicate_warnings=warnings,sample_method='SHA256(scenario_id/work_id), ceil(20%) per split; no RNG',
        source_hashes=before))
    role_counts={}
    for split in ('dev','test'):
        (output/split).mkdir()
        rows=[]
        for key,card in sorted(cards.items(),key=lambda x:hashlib.sha256(('/'.join(x[0])).encode()).hexdigest()):
            if card['split']!=split:continue
            seeds,candidates=card['seeds'],card['candidates']
            case=next(c for c in cases if c['scenario_id']==key[0])
            def joined(items,field):
                return '\n\n'.join(f"{b['book_id']}: "+( '; '.join(b[field]) if isinstance(b[field],list) else str(b[field])) for b in items)
            row=dict(scenario_id=key[0],split=split,intent=card['intent'],judging_guidance=case.get('judging_guidance',''),filters=json.dumps(card['filters'],ensure_ascii=False),
                exclude_book_ids='; '.join(case['exclude_book_ids']),exclude_titles='; '.join(source.books[x].title for x in case['exclude_book_ids']),
                seed_book_ids='; '.join(b['book_id'] for b in seeds),
                seed_titles=joined(seeds,'title'),seed_summaries=joined(seeds,'summary'),candidate_work_id=key[1],
                candidate_book_ids='; '.join(b['book_id'] for b in candidates),candidate_titles=joined(candidates,'title'),
                candidate_authors=joined(candidates,'authors'),candidate_genres=joined(candidates,'genres'),
                candidate_topics=joined(candidates,'topics'),candidate_summaries=joined(candidates,'summary'),
                edition_relationship=RELATION,evidence_refs='; '.join(b['evidence_ref'] for b in candidates),**binding)
            row.update({col:'' for col in LABEL_EDIT});rows.append(row)
        cross=[row for row in rows if (row['scenario_id'],row['candidate_work_id']) in sample]
        _csv(output/split/'primary.csv',META+CONTEXT+LABEL_EDIT,rows)
        _csv(output/split/'p4.csv',META+CONTEXT+LABEL_EDIT,cross)
        role_counts[split]=dict(primary=len(rows),p4=len(cross),review_fraction=len(cross)/len(rows) if rows else 0)
        if len(cross)<math.ceil(len(rows)*.2):raise ValueError('Review fraction below 20%')
    (output/'HOW-TO-LABEL.md').write_text(GUIDE,encoding='utf-8')
    payload_files=['scenarios-review.csv','scenarios-review.md','scenario-checks.json','HOW-TO-LABEL.md']+[
        f'{s}/{role}.csv' for s in ('dev','test') for role in ('primary','p4')]
    original_label_counts={}
    for name in ('primary.csv','cross_review.csv','final.csv'):
        _,old_rows=_rows(directory/name)
        original_label_counts[name]=dict(sha256=sha(directory/name),nonblank_labels=sum(bool(r['relevance']) for r in old_rows))
    manifest=dict(format_version=1,exported_at=datetime.now(timezone.utc).isoformat(),**binding,
        scenario_approval=None,label_approval=None,counts=role_counts,
        scenario_split_frozen_at=None,pool_created_at=run.get('created_at'),labels_version=None,
        original_sheets=original_label_counts,
        files={name:sha(output/name) for name in payload_files},
        exporter_sha256=sha(Path(__file__)),snapshot_source_hashes=before)
    write_json(output/'manifest.json',manifest)
    private_manifest=dict(format_version=1,exported_at=manifest['exported_at'],**binding,counts=role_counts,
        files={name:sha(output/name) for name in ('dev/p4.csv','test/p4.csv','HOW-TO-LABEL.md')})
    with zipfile.ZipFile(output/'P4-independent-review.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in private_manifest['files']:archive.write(output/name,arcname=name)
        archive.writestr('manifest.json',json.dumps(private_manifest,ensure_ascii=False,indent=2))
    if before!=source_hashes(snapshot_dir):raise ValueError('Snapshot changed during export')
    return manifest


def verified_exchange(directory,bundle):
    run=verified_run(directory);manifest=read_json(bundle/'manifest.json')
    if any(manifest.get(key)!=value for key,value in _binding(run,directory).items()):
        raise ValueError('Exchange belongs to another snapshot/pool/run')
    for name,digest in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or sha(bundle/name)!=digest:
            raise ValueError('Original exchange template hash changed')
    return manifest


def _validate_edit(row,role):
    final=role=='final';label=row['final_label'] if final else row['relevance']
    if label not in ('','0','1','2'):raise ValueError('Relevance must be blank or exactly 0/1/2; Excel changed a value')
    if row['reviewer_confirmed'] not in ('','yes'):raise ValueError('reviewer_confirmed must be blank or yes')
    if final:
        if row['final_status'] not in ('','draft','needs_review','approved'):raise ValueError('Invalid final status')
        confirmed=row['final_status']=='approved' and row['reviewer_confirmed']=='yes'
        status=row['final_status'];name,date='adjudicator_id','adjudicated_at';rationale,evidence='final_rationale','final_evidence'
    else:
        if row['review_status'] not in ('','draft','needs_review','confirmed'):raise ValueError('Invalid review_status')
        confirmed=row['review_status']=='confirmed' and row['reviewer_confirmed']=='yes'
        status=row['review_status'];name,date='annotator_id','annotated_at';rationale,evidence='rationale','evidence'
    if (status in ('confirmed','approved') or row['reviewer_confirmed']=='yes') and not confirmed:
        raise ValueError('Confirmation and status must agree')
    if confirmed:
        _identity(row,name,date)
        if not label or not row[rationale].strip() or not row[evidence].strip():
            raise ValueError('Confirmed label requires relevance/rationale/evidence')
        if final:
            primary=row['primary_label'];cross=row['p4_label']
            if row['primary_confirmed']!='yes' or (row['p4_required']=='yes' and row['p4_confirmed']!='yes'):
                raise ValueError('Final decision requires confirmed primary/P4 where required')
            if (label!=primary or cross and label!=cross or primary and cross and primary!=cross) and not row['resolution'].strip():
                raise ValueError('Disagreement/final change requires human resolution')
    return confirmed


def _checked_exchange(directory,bundle,input_path,role,split,comparison=None,representation_changes=None):
    verified_exchange(directory,bundle)
    if role=='final':
        if comparison is None:raise ValueError('Final import requires --comparison')
        comp=read_json(comparison/'comparison.json')
        if comp['run_sha256']!=sha(directory/'run.json') or comp['split']!=split:
            raise ValueError('Comparison belongs to another run/split')
        if sha(comparison/'adjudication.csv')!=comp['template_sha256']:
            raise ValueError('Original adjudication template changed')
        original=comparison/'adjudication.csv';editable=FINAL_EDIT
    else:
        if role not in ('primary','p4') or split not in ('dev','test'):raise ValueError('Invalid role/split')
        original=bundle/split/(role+'.csv');editable=LABEL_EDIT
    columns,expected_rows=_rows(original);actual_columns,rows=_rows(input_path)
    if set(actual_columns)!=set(columns):raise ValueError('CSV columns changed; use exported template')
    expected,actual=_indexed(expected_rows),_indexed(rows)
    if set(expected)!=set(actual):raise ValueError('Missing/unknown IDs or Excel changed an ID')
    for key,row in actual.items():
        for column in columns:
            if column in editable or row[column]==expected[key][column]:continue
            # CSV copied through Windows/Excel can use CRLF inside quoted cells.
            # Accept only equivalent line endings; never trim IDs, text or labels.
            if row[column].replace('\r\n','\n')!=expected[key][column].replace('\r\n','\n'):
                raise ValueError('Read-only ID/metadata/snapshot/hash changed')
            if representation_changes is not None:
                representation_changes.append(dict(scenario_id=key[0],work_id=key[1],column=column,kind='CRLF_LF_only'))
        _validate_edit(row,role)
    return rows


def import_review(directory,bundle,input_path,role,split,output,*,finalize=False,comparison=None):
    representation_changes=[]
    rows=_checked_exchange(directory,bundle,input_path,role,split,comparison,representation_changes)
    confirmed=sum(_validate_edit(r,role) for r in rows)
    if finalize and confirmed!=len(rows):raise ValueError('Cannot finalize: blank, needs-review or unconfirmed rows remain')
    output=_new_dir(output)
    (output/'raw-input.csv').write_bytes(Path(input_path).read_bytes())
    columns=list(rows[0]) if rows else []
    _csv(output/'draft.csv',columns,rows)
    binding=_binding(verified_run(directory),directory)
    if finalize:
        canonical=[]
        for row in rows:
            if role=='final':
                record=dict(scenario_id=row['scenario_id'],work_id=row['candidate_work_id'],
                    relevance=row['final_label'],rationale=row['final_rationale'],evidence=row['final_evidence'],
                    status=row['final_status'],approved_by=row['adjudicator_id'],approved_at=row['adjudicated_at'],resolution=row['resolution'])
            else:
                record=dict(scenario_id=row['scenario_id'],work_id=row['candidate_work_id'],
                    **{k:row[k] for k in LABEL_COLUMNS if k not in ('scenario_id','work_id')})
                record['review_status']=row['review_status']
            record.update(binding,reviewer_confirmed=row['reviewer_confirmed']);canonical.append(record)
        _csv(output/'canonical.csv',list(canonical[0]) if canonical else [],canonical)
    report=dict(status='finalized_exchange_not_metric_approval' if finalize else 'draft_saved',role=role,split=split,
        rows=len(rows),confirmed=confirmed,blank=sum(r['final_label' if role=='final' else 'relevance']=='' for r in rows),
        needs_review=sum(r['final_status' if role=='final' else 'review_status']=='needs_review' for r in rows),
        unconfirmed=len(rows)-confirmed,input_sha256=sha(input_path),**binding,
        canonical_sha256=sha(output/'canonical.csv') if finalize else None,
        read_only_newline_differences=len(representation_changes),
        newline_policy='CRLF/LF representation equivalence only; original bytes and all labels preserved',
        warning='Drafts and finalized exchange files do not approve scenarios/final labels or authorize any metric run')
    report['per_scenario']={sid:dict(rows=sum(r['scenario_id']==sid for r in rows),
        confirmed=sum(r['scenario_id']==sid and _validate_edit(r,role) for r in rows)) for sid in sorted({r['scenario_id'] for r in rows})}
    write_json(output/'completeness.json',report)
    return report


def compare_reviews(directory,bundle,primary,p4,split,output):
    a=_indexed(_checked_exchange(directory,bundle,primary,'primary',split))
    b=_indexed(_checked_exchange(directory,bundle,p4,'p4',split))
    output=_new_dir(output);rows=[]
    for key,row in a.items():
        cross=b.get(key);pc=_validate_edit(row,'primary');cc=_validate_edit(cross,'p4') if cross else False
        if not pc:status='waiting_primary'
        elif cross and not cc:status='waiting_p4'
        elif cross and row['relevance']!=cross['relevance']:status='disagreement'
        else:status='awaiting_human_final'
        result={k:v for k,v in row.items() if k not in LABEL_EDIT}
        result.update(primary_label=row['relevance'],primary_rationale=row['rationale'],primary_evidence=row['evidence'],
            primary_reviewer=row['annotator_id'],primary_confirmed='yes' if pc else '',
            p4_required='yes' if cross else 'no',p4_label=cross['relevance'] if cross else '',
            p4_rationale=cross['rationale'] if cross else '',p4_evidence=cross['evidence'] if cross else '',
            p4_reviewer=cross['annotator_id'] if cross else '',p4_confirmed='yes' if cc else '',comparison_status=status)
        if cross and pc and cc and row['annotator_id'].strip().casefold()==cross['annotator_id'].strip().casefold():
            raise ValueError('P4 review must be independent')
        result.update({c:'' for c in FINAL_EDIT});rows.append(result)
    columns=list(rows[0]) if rows else []
    _csv(output/'adjudication.csv',columns,rows)
    _csv(output/'disagreements.csv',columns,[r for r in rows if r['comparison_status']=='disagreement'])
    record=dict(split=split,run_sha256=sha(directory/'run.json'),rows=len(rows),
        disagreements=sum(r['comparison_status']=='disagreement' for r in rows),
        awaiting_primary=sum(r['comparison_status']=='waiting_primary' for r in rows),
        awaiting_p4=sum(not _validate_edit(row,'p4') for row in b.values()),
        confirmed_primary=sum(_validate_edit(row,'primary') for row in a.values()),
        confirmed_p4=sum(_validate_edit(row,'p4') for row in b.values()),
        primary_input_sha256=sha(primary),p4_input_sha256=sha(p4),template_sha256=sha(output/'adjudication.csv'),
        final_label_approval=None)
    write_json(output/'comparison.json',record)
    return record
