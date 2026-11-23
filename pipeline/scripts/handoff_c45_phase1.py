"""Create an unstaged C45 handoff and a dependency-aware exact commit manifest."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REPORTS=ROOT/'data/reports'
FINAL=REPORTS/'c45-phase1-final-closure-20261123'
OUT=REPORTS/'c45-phase1-handoff-20261123'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True,encoding='utf-8').strip()
def key(c):return (c['check_id'],c.get('record_id'),c.get('book_id'))
def main():
    assert not OUT.exists(),'Never overwrite a published handoff'
    assert git('branch','--show-current')=='feature/data-embedding'
    checks=read(FINAL/'checks_final.json');exceptions=read(FINAL/'exceptions_final.json')
    assert len(checks)==33 and len(exceptions)==9 and len({key(c) for c in checks})==33
    assert Counter(c['status'] for c in checks)=={'PASS':24,'WARNING':7,'UNVERIFIED':2}
    protected={str(p.relative_to(ROOT)):sha(p) for directory in
               (FINAL,REPORTS/'c45-r8-phase1-20261123-v12',ROOT/'data/raw/c41_reader20_batch1',ROOT/'data/demo/p4-w03-c38-reviewed-r8-20261122')
               for p in directory.rglob('*') if p.is_file()}
    for p in [ROOT/'.gitignore',ROOT/'.gitattributes',*ROOT.glob('pipeline/scripts/*c41*'),*ROOT.glob('pipeline/tests/*c41*')]:
        if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    register=[]
    for c in exceptions:
        pending=c['check_id'] in ('C45-PENDING-SOURCE','C45-PENDING-INDEX')
        assert c['status']=='UNVERIFIED' or pending
        historical=c['check_id']=='C45-P4-BASELINE'
        register.append(dict(check_id=c['check_id'],record_id=c.get('record_id'),book_id=c.get('book_id'),
            check_name=c['expected'],technical_status=c['status'],description=c['observed'],
            root_cause='Intentional pending sources remain in frozen catalog/index; excluded at API eligibility' if pending else
                       'Exact pre-iteration artifact and counting rules unavailable' if historical else
                       'Review attribution inferred; historical review timestamps and outside-demo permissions unproven',
            evidence=c['evidence'],disposition='proposed_exception',
            disposition_reason='Propose accepting this technical residual for frozen internal demo; no blanket exception approval has been recorded',
            owner='P3',scope='Phase 1 internal metadata/summary demo only',
            reopen_condition='Catalog/snapshot/source/rights/eligibility change, or any pending API leak' if pending else
                             'New historical artifact or explicit requirement to reproduce 119/63/64' if historical else
                             'New attributable review evidence, contradictory evidence or expansion to public use',
            approval_status='awaiting_explicit_exception_acceptance',followup_phase='triggered recheck only' if historical else 'pre-demo or relevant data/scope change',
            approved_by=None,approved_at=None))
    OUT.mkdir(parents=True)
    (OUT/'exception_register.json').write_text(json.dumps(register,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'audit_recheck_policy.md').write_text('''# C45 — quy tắc audit lại

Sau commit C45: kiểm file trong commit_manifest, checkout sạch có đủ dependency, tái lập báo cáo vào thư mục mới và chạy test C45. Không chạy lại E5/FAISS nặng nếu đầu vào/model không đổi.

Khi C41 đủ 20 toàn văn: mở C45 Phase 2 cho provenance/quyền của tác phẩm và phiên bản, chapter/paragraph, manifest/hash, offsets và Reader API. Không tự mở lại lịch sử Phase 1 không liên quan.

Trước demo/bàn giao cuối kỳ: kiểm snapshot thực sự phục vụ Search, Recommendation, Reader; eligibility, quyền nguồn, integrity và hiệu lực exception register.

Mở sớm đúng check bị ảnh hưởng nếu catalog/snapshot, metadata/summary/URL, rights_status, eligibility thay đổi; pending lọt API; có lỗi/bằng chứng mâu thuẫn mới; hoặc chuyển từ demo nội bộ sang phát hành công khai. Đổi ngày chạy audit không tự mở lại ngoại lệ.

Mọi lần chạy ghi phiên bản/hash đầu vào và xuất thư mục mới. Không sửa báo cáo lịch sử; không tính ngoại lệ được chấp nhận là PASS. Không tự động chạy theo lịch hoặc kích hoạt Phase 2 từ tài liệu này.
''',encoding='utf-8')
    (OUT/'phase1_handoff.md').write_text('''# C45 Phase 1 handoff

Technical assessment: Phase 1 — Technically accepted for internal demo, with documented exceptions.

Administrative status: đề xuất nghiệm thu có điều kiện; chín ngoại lệ đang proposed_exception, chưa có chữ ký hoặc phê duyệt thay nhóm/giảng viên. Quyết định owner giữ ba sách pending được ghi nhận; quyết định này không được dùng như phê duyệt mặc nhiên toàn bộ register.

Kết quả nguyên gốc giữ 24 PASS / 7 WARNING / 0 FAIL / 2 UNVERIFIED, 33 dòng (28 check_id; khóa ghép định danh nguồn). r8 có 289 sách, 286 eligible, ba pending, 578 nguồn (572 approved, sáu pending). Bảy WARNING là sáu nguồn pending và một check membership trong index; hai UNVERIFIED là baseline 119/63/64 và review scope/lịch sử ngoài demo.

Bằng chứng kỹ thuật còn ràng buộc với hash: importer 289/289, E5 289/289, FAISS/NumPy, Search 13 ASGI, Recommendation 11 ASGI + bốn ca lỗi. Pytest focused 28/28, Node 5/5 và OpenSpec strict đã đạt trong closure; không gọi đây là browser E2E hoặc HTTP TCP.

Reviewer P3/P4 inferred và ngày Git là ngày tham chiếu. Hồ sơ này không xác nhận toàn bộ giấy phép sử dụng bên thứ ba hoặc quyền công khai. Toàn C45 chưa Done; Phase 2 chờ C41 và Reader.

Bước tiếp: P3 có thể ghi quyết định chấp nhận ngoại lệ theo từng khóa trong register, sau đó stage đúng manifest ở lượt riêng. Sau commit thực hiện kiểm clean checkout theo audit_recheck_policy.md.
''',encoding='utf-8')
    # Minimal workflow: baseline machine checks + closure builder + snapshot-bound API smoke.
    candidates=[ROOT/p for p in ['pipeline/scripts/audit_c45_phase1.mjs','pipeline/scripts/close_c45_phase1.py',
        'pipeline/scripts/check_c45_r8_search.py','pipeline/scripts/handoff_c45_phase1.py',
        'pipeline/tests/test_c45_phase1.mjs','pipeline/tests/test_c45_review_replacements.mjs',
        'pipeline/requirements-c45-tests.txt']]
    candidates+=list((ROOT/'openspec/changes/c45-data-quality-audit').rglob('*.md'))+list((ROOT/'openspec/changes/c45-data-quality-audit').glob('*.yaml'))
    candidates+=list(FINAL.glob('*'))
    candidates+=[REPORTS/'c45-r8-phase1-20261123-v12'/n for n in ('audit_run.json','checks.jsonl','url_comparison.jsonl','e5_full_inference.json')]
    candidates+=[REPORTS/n for n in ('c45-r8-search-api-20261123.json','c45-r8-recommendation-api-20261123.json',
        'c45-r8-recommendation-errors-20261123.json','c45-r8-recommendation-faiss-20261123.json',
        'c45-r8-faiss-top5-20261123.json','c45-r8-token-limit-20261123.json')]
    # closure only optionally hashes these directories; absent historical intermediate reports are not runtime inputs.
    for c in candidates:assert c.is_file(),c
    # Required tracked inputs and declared runtimes are recorded separately, never copied into this commit.
    base=read(REPORTS/'c45-r8-phase1-20261123-v12/audit_run.json')
    dependencies=[Path(x['path']) for x in base['inputs'].values()]
    dependencies+=[ROOT/'data/raw/c35_reviewed150/quality_by_book_id.jsonl',ROOT/'data/raw/c20_c34/id_registry.json',
        ROOT/'pipeline/scripts/in_memory_http.py',ROOT/'pipeline/requirements-p3-demo.txt',
        ROOT/'pipeline/requirements-embedding.txt',ROOT/'pipeline/requirements.txt']
    dependency_rows=[]
    for p in dependencies:
        p=p if p.is_absolute() else ROOT/p
        assert p.is_file(),p
        rel=str(p.relative_to(ROOT)).replace('\\','/')
        tracked=bool(git('ls-files','--',rel));assert tracked,rel
        dependency_rows.append(dict(path=rel,sha256=sha(p),tracked=True))
    (OUT/'precommit_review.md').write_text('''# C45 pre-commit review

Không stage/commit trong lượt này. Commit riêng chỉ dùng các đường dẫn trong commit_manifest.json. `.gitignore` và `.gitattributes` đang modified chỉ thêm quy tắc C41, nên không đưa vào commit C45. Không lấy data/raw/c41_reader20_batch1 hoặc script/test C41.

Các báo cáo và OpenSpec C45 bị ignore: cần explicit `git add -f -- <exact-path>` ở lượt đã được cho phép stage; không sửa ignore dùng chung để lấy cả C41. Manifest ghi status/kích thước/hash từng file. Không đưa mọi báo cáo v8–v12 hay script khảo sát cũ vào commit; giữ đúng bốn baseline v12 và sáu báo cáo runtime được closure/checks_final tham chiếu.

Tái lập được kiểm bằng dependency manifest, file tồn tại/tracked và test; chưa thực hiện clean checkout Git độc lập. Root được suy từ __file__/import.meta.dirname; dùng đường dẫn repo và output mới. Absolute interpreter/cache paths trong bằng chứng cũ chỉ là chẩn đoán môi trường đã chạy, không phải cấu hình cần sao chép. Không đưa model/cache/venv vào commit. Runtime Node >=22 có --experimental-sqlite, Python và các dependencies khai báo trong pipeline/requirements-p3-demo.txt; pytest là công cụ kiểm thử cần có trong môi trường test.

Lệnh nhẹ: node --experimental-sqlite --test pipeline/tests/test_c45_phase1.mjs pipeline/tests/test_c45_review_replacements.mjs; python -B -m pytest -q -p no:cacheprovider pipeline/tests/test_importer_quarantine.py api/tests/test_eligibility.py; openspec validate c45-data-quality-audit --strict.

Lệnh tái lập closure: python -B pipeline/scripts/close_c45_phase1.py --output data/reports/<new-closure-dir>. Không chạy lại pipeline tạo embedding. Sau commit cần kiểm checkout thật và hash report dữ liệu; timestamp hoặc danh sách file bảo vệ có thể khác theo checkout.
''',encoding='utf-8')
    candidates+=list(OUT.glob('*'))
    entries=[]
    for p in sorted(set(candidates)):
        rel=str(p.relative_to(ROOT)).replace('\\','/')
        tracked=bool(git('ls-files','--',rel))
        ignored=subprocess.run(['git','check-ignore','-q','--',rel],cwd=ROOT).returncode==0
        entries.append(dict(path=rel,purpose='C45 script/test/spec or pinned evidence needed for handoff and reproduction',
            git_status='tracked' if tracked else 'ignored' if ignored else 'untracked',size_bytes=p.stat().st_size,sha256=sha(p)))
    manifest=dict(files=entries,file_count=len(entries)+1,total_bytes_without_manifest=sum(x['size_bytes'] for x in entries),
        self=dict(path=str((OUT/'commit_manifest.json').relative_to(ROOT)).replace('\\','/'),purpose='This manifest; self hash omitted to avoid circular hashing'),
        tracked_dependencies=dependency_rows,excluded_shared_files=['.gitignore','.gitattributes'],
        excluded_work=['C41 datasets/scripts/tests','old C45 exploratory reports and scripts not used by closure'],
        clean_checkout_verification='dependency manifest simulation only; real clean checkout required after commit')
    (OUT/'commit_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert all(sha(ROOT/p)==h for p,h in protected.items())
    print(json.dumps(dict(exceptions=len(register),dispositions=dict(Counter(r['disposition'] for r in register)),
        commit_files=manifest['file_count'],bytes_without_manifest=manifest['total_bytes_without_manifest'],protected_unchanged=True)))

if __name__=='__main__':main()
