# Tasks

Checkbox ghi tiến độ có bằng chứng. P3 giữ ba sách pending trong catalog, loại khỏi Search/Recommendation demo; PR #23–#25 đã tích hợp và v11 đã kiểm chứng API trên r8 thật. Phase 2 phụ thuộc C41 và xác nhận Reader từ P4. Kết quả kiểm phải ghi đúng phạm vi quyền, input hash và snapshot ID.

## Kết quả closure Phase 1 — 23/11/2026

Bộ `data/reports/c45-phase1-final-closure-20261123/` có 33 dòng check (28 check_id duy nhất; khóa ghép source_id), 24 PASS, 7 WARNING, 0 FAIL, 2 UNVERIFIED. `remediation_matrix.json` ghi tiêu chí gốc và kết luận cho mọi dòng. Các checkbox yêu cầu rộng hơn bằng chứng vẫn để mở; không đánh dấu toàn C45 Done.

- `C45-REVIEW-URL` được sửa phép đối chiếu: cả 114 nguồn khớp source_replacements theo ID và URL. Có regression test để ID sai hoặc URL cũ không được tính khớp. Không suy ra giấy phép công khai.
- Hồ sơ 572 nguồn approved: P3/P4 inferred theo xác nhận owner và trách nhiệm lô, ngày Git là review_record_date; reviewed_at null. Không coi attribution suy luận là chữ ký đã chứng minh hay quyền ngoài demo.
- Số 119/63/64 thiếu baseline lượt nội bộ; có đính chính và phép đếm full diff 116 summary / 101 sách đổi URL / 114 nguồn thay thế, không coi hai phép đo tương đương.
- Bằng chứng r8 v11/v12 còn hiệu lực qua hash và code: 286 eligible, ba pending bị loại khỏi API; seed pending 422. Giữ bảy WARNING có chủ đích, không đổi approval/index để ép PASS.
- `acceptance.md`: đủ bằng chứng nghiệm thu kỹ thuật demo với ngoại lệ được ghi rõ; nghiệm thu đầy đủ quyền/lịch sử và toàn C45 còn mở. Phase 2 chưa triển khai.

## 1. Phase 1 — Chốt đầu vào và Catalog & source audit

- [x] 1.1 Pin commit, đường dẫn/hash catalog P3, Search r8, taxonomy, review, manifest và snapshot; xác nhận chạy read-only và SHA trước/sau bằng `audit_run.json`, không có file đầu vào đổi. Bằng chứng: `data/reports/c45-r8-phase1-20261122-v8/audit_run.json`, 19 file input, SHA không đổi.
- [ ] 1.2 Tái sử dụng importer/schema/source validator để kiểm required fields, approved/pending/rejected theo metadata/summary/cover/fulltext và scope; đối chiếu `review.json`, xuất exceptions theo book_id/source_id; kiểm ba pending có thể xuất hiện trong Search demo và đối chiếu yêu cầu sách đã duyệt của SPEC UC-S; test fixture thiếu nguồn, approval thiếu căn cứ và pending có trạng thái riêng.
- [ ] 1.3 Đối chiếu 294 catalog, 289 Search, năm sách QC v4 và 286 approved/3 pending của r8, taxonomy, registry/ID, orphan, duplicate và near-duplicate; kiểm tổng bằng phép đếm độc lập và test ID/nhãn sai, ghi nghi trùng chờ người duyệt.
- [ ] 1.4 Xác định baseline P4 ngay trước r8 cho 119/63/64 và lập bảng source URL/summary diff với commit/path; nếu thiếu baseline, ghi UNVERIFIED có lý do trong báo cáo và test không lấy diff P3 v4 làm phép xác nhận tăng thêm r8.
- [x] 1.5 Ghi nhận quyết định của P1/P2/P3/P4: giữ nguyên ba ID pending và approval trong catalog, loại khỏi kết quả Search/Recommendation demo; khảo sát tầng index, candidate, API và đưa ra phương án/owner/test/tiêu chí nghiệm thu trong báo cáo v10. Đây là quyết định và thiết kế, chưa phải bằng chứng đã lọc ở runtime.
- [ ] 1.6 P1/P2 triển khai theo quy trình riêng, chạy regression Search/Similar/Recommendation trên r8 và chứng minh ba ID không xuất hiện ở response trong mọi đường truy vấn liên quan; P3 kiểm lại quyền nguồn, hash và báo cáo sau thay đổi.

## 2. Phase 1 — Text, E5 và snapshot consistency

- [ ] 2.1 Kiểm NFC/summary rỗng hoặc bất thường, dựng biểu diễn năm dòng và content_hash cho từng book_id; dùng tokenizer đúng revision để đo 480 token gồm prefix/special tokens nếu sẵn có, nếu thiếu ghi UNVERIFIED; test 480/481 và sai hash.
- [ ] 2.2 Kiểm bundle r8 model/revision/metadata, `vectors.npy` float32 `(289,384)`/finite/L2, ID/row order và SHA; so 63 summary theo đúng baseline và per-record lineage, phân biệt structural PASS với inference UNVERIFIED; test vector NaN/sai norm/mapping trùng trên bản sao cô lập.
- [ ] 2.3 Đối soát FAISS IndexFlatIP, mapping, SQLite read-only (FK/quick_check), manifest/hash/size/snapshot ID, cùng tập sách có vector và top-k mẫu; test hash, index count và orphan sai trên fixture, không rebuild index hay chuyển active.
- [ ] 2.4 Tạo tài liệu lệnh chạy Phase 1 bằng đường dẫn r8 đã pin và xác nhận test/validator tái sử dụng chạy trên bản sao hoặc chỉ đọc, không tạo tác dụng phụ ở dữ liệu nhóm.

## 3. Phase 2 — Fulltext integrity (sau C41/P4)

- [ ] 3.1 Pin P3 Reader pending và C42 Reader localhost Việt Nam thành hai nguồn độc lập; kiểm source_manifest/review/registry, fulltext approval theo từng lô, không chuyển trạng thái giữa lô; test fixture thiếu approval và ghi ngoại lệ theo book_id.
- [ ] 3.2 Đối soát trực tiếp JSONL và SQLite Reader cho baseline 2 work/28 chương/4.301 đoạn: book/work/chapter/paragraph ID, order_no, NFC, hash, FK, code-point offsets/text slices; test chapter mồ côi, thứ tự sai và offset hỏng ở snapshot fixture chỉ đọc.
- [ ] 3.3 Lấy từ P4 bằng chứng Reader API và browser thật trên đúng snapshot, kiểm chapter/snapshot lookup và highlight; phân loại từng tầng JSONL, import, API, frontend thành PASS/FAIL/UNVERIFIED, kiểm Search/RAG flag độc lập.
- [ ] 3.4 Khi C41 thêm tác phẩm, kiểm từng batch mới cùng bộ check và ít nhất 20 work_id khác nhau chỉ khi đã có dữ liệu/approval; ghi số thực đạt, quyền và các tác phẩm thiếu vào exceptions, không tự thực hiện C41/C50/C53/C60.

## 4. Regression tests theo nhóm

- [ ] 4.1 Chạy lại test importer/quarantine và source rights trên fixture cô lập; ghi command/commit/output, chứng minh pending/rejected và duplicate/orphan được phân loại đúng, không sửa catalog thật.
- [ ] 4.2 Chạy test C11 bundle/index/snapshot trên fixture cô lập và kiểm trường hợp summary đổi nhưng content hash/vector lineage thiếu; chứng minh kết quả UNVERIFIED không bị chuyển PASS.
- [ ] 4.3 Chạy test Reader registry/offset/API theo từng tầng khi runtime sẵn có, ghi phần không chạy được thành UNVERIFIED thay vì trích kết quả bàn giao như test độc lập.

## 5. Report generation và ngoại lệ

- [x] 5.1 Xuất `audit_run.json`, `checks.jsonl`, `exceptions.jsonl`, `summary.md` với schema ở design.md và bằng chứng file/key/hash/command theo ID; test parse và tính lại số dòng/status/phase từ báo cáo. Bằng chứng: `node --experimental-sqlite --test pipeline/tests/test_c45_phase1.mjs` (4/4).
- [ ] 5.2 Kiểm severity theo chức năng/scope: blocking snapshot, blocking content, warning/human review và environment dependency; test hash sai chặn đúng snapshot, pending chỉ nêu đúng phạm vi, không có PASS giả.
- [ ] 5.3 Ghi danh sách remediation owner và các câu hỏi P4 (baseline r8, model lineage, Reader runtime/approval C41); đối chiếu mỗi ngoại lệ với record gốc và hạn chế chưa xác minh trong summary.

## 6. Validation và documentation tích hợp

- [x] 6.1 Chạy audit lặp trên cùng inputs đóng băng trong môi trường chỉ đọc; so kết quả ổn định trừ timestamp, SHA dữ liệu trước/sau khớp; ghi các tool/tokenizer/runtime thiếu và phạm vi tác động. Hai lần chạy cho output byte-identical trừ `generated_at`; test fixture Node 4/4.
- [ ] 6.2 Đối chiếu báo cáo với SPEC v0.1 §3/§10/§11/§14/§15 và workbook C45; ghi nguồn của từng check (bắt buộc SPEC, chính thức C45, hay đề xuất sau PR #22); xác nhận không đánh dấu đạt SRS hay Reader production khi chỉ kiểm staging.

## 7. Review / acceptance

- [ ] 7.1 P3/P1 review Phase 1, đối chiếu exceptions theo book_id và bằng chứng thực thi quyết định đã thống nhất; chỉ ghi Phase 1 complete khi check bắt buộc đã có kết luận rõ, không tính UNVERIFIED là PASS.
- [ ] 7.2 P3/P4 review Phase 2 sau khi có C41/Reader evidence và từng batch; ghi chấp nhận ngoại lệ có thẩm quyền và điều kiện ảnh hưởng C50/C53/C60; chỉ khi cả hai phase đủ bằng chứng mới đề nghị cập nhật C45 Done ở tracker riêng.

## Workflow follow-up

- Việc sửa dữ liệu, phê duyệt nguồn, rebuild embedding/index/snapshot và chuyển active cần luồng công việc và review riêng sau audit; checklist này không cho phép thực hiện chúng trong lượt planning.
