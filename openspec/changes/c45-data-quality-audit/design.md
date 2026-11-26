# Design

## Context

Theo `proposal.md` và `specs/data-quality-audit/spec.md`, C45 là QA dữ liệu W3, không phải thay đổi quyền duyệt hoặc phát hành. SPEC v0.1 §3/§3.1 yêu cầu nguồn riêng từng content type, báo cáo cách ly và ID ổn định; §10.4 quy định E5 revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, biểu diễn năm dòng, 480 token sau prefix/special tokens, float32 384 L2; §14.6 yêu cầu snapshot/manifest/hash; §11/§15 quy định Reader offset code point, liên kết và nghiệm thu. Workbook `02_Tasks` C45 chính thức nêu source rights metadata/summary/cover/fulltext, orphan/duplicate, token quá dài và import report, output `Data audit + exceptions`; C37/C41 là dependency. Kiểm lineage r8 và cross-artefact được bổ sung để đánh giá thay đổi của PR #22.

Baseline HEAD `ae417fe` (merge PR #22) có P3 294 metadata, Search v4 và r8 mỗi tập 289; năm sách ngoài Search là nhóm QC v4, khác ba sách nguồn pending của r8. r8 có 286 sách/572 nguồn approved cho demo nội bộ, 3 sách/6 nguồn pending; snapshot tự đánh dấu `unverified_rights: true`. `review.json` ghi 269 quyết định (266 pass, 3 needs_evidence), còn README/báo cáo PR ghi 122 sách đối chiếu, 119 duyệt, 63 summary và 64 nguồn thay. So với P3 Search v4 cũ, có 116 summary khác và 101 bản ghi đổi URL: mốc so sánh khác với lượt review r8, không được suy thành mâu thuẫn khi chưa xác định baseline trung gian P4.

Mã `pipeline/ai_library/classroom_demo.py` và `api/src/services/search.py::_sources_are_approved` có nhánh cho nguồn pending trong scope classroom demo; kết luận runtime cần chạy Search API thực. Audit đo source ID pending trong catalog/SQLite và book ID trong vector mapping rồi ghi khả năng xuất hiện qua API là UNVERIFIED khi chưa chạy được. SPEC v0.1 UC-S §5.1 yêu cầu chọn sách đã duyệt. Sau v9, P1/P2/P3/P4 đã thống nhất giữ ba sách pending trong catalog gốc nhưng loại khỏi kết quả Semantic Search và Recommendation demo. Quyết định này chưa được triển khai hoặc kiểm chứng bằng response. Gói r8 bỏ trường người duyệt nội bộ khỏi nguồn chia sẻ; thiếu `reviewed_by`/`reviewed_at` ở gói công khai không chứng minh chưa từng có review nội bộ.

Kiểm tra chỉ đọc trong lượt planning xác nhận 13 hash của `handoff_manifest.json`, hash biểu diễn năm dòng cho 289 mapping, vector r8 float32 `(289,384)` hữu hạn với norm khoảng 0.999999889–1.000000100, index/mapping/SQLite cùng 289 sách, SQLite 578 nguồn (572/6), 0 chapters và FK check rỗng; 116 sách đổi summary so với P3 v4 cũng đổi content hash và vector row. Điều này chứng minh liên kết công bố text/hash/vector/index hiện tại, **chưa chứng minh từng row đã được inference bằng đúng revision**; token thật/model execution cần cache/log hoặc kiểm chứng riêng. C42 có hai tác phẩm, 28 chương, 4.301 đoạn ở lô Reader riêng, phê duyệt cho localhost Việt Nam; lô P3 vẫn pending. Hash chương P3/C42 trùng, snapshot C42 khai Reader=true, Search/RAG=false. Không suy staging hoặc tài liệu test thành kiểm chứng API/frontend độc lập.

## Goals / Non-Goals

**Goals:** Có kết quả audit tái lập trên input đóng băng, exceptions truy vết theo ID, điều kiện chặn phát hành theo từng chức năng/phạm vi, và trạng thái chưa xác minh tường minh. Có thể hoàn thành Phase 1 riêng trong khi Phase 2 chờ C41/P4.

**Non-Goals:** Tự phán quyền nguồn bên thứ ba, thay approval, sửa metadata/summary/fulltext, tái mã hóa E5, xây FAISS/snapshot, chuyển active, đổi API/Reader schema hay triển khai C50/C53/C60. Audit không tự xác nhận Search/Reader production.

## Decisions

### 1. Audit chỉ đọc theo manifest đầu vào cố định

Manifest chạy audit ghi `git_commit`, thời điểm, phạm vi quyền (demo nội bộ/localhost/phát hành), đường dẫn tương đối, SHA-256, snapshot ID, phiên bản check và trạng thái phụ thuộc. Đọc JSONL theo từng record, SQLite mở ở chế độ read-only/immutable trên bản ổn định, vector/index/manifest chỉ đọc. Không gọi importer/build tạo output vào thư mục dữ liệu nhóm. Nếu phải chạy validator có ghi report hoặc fixture, đặt đầu ra ở thư mục tạm riêng và không trỏ control active của nhóm. So hash đầu vào trước/sau; mismatch khiến kết quả liên quan UNVERIFIED và yêu cầu chạy lại. Chọn pin input thay vì đọc các đường dẫn active đang thay đổi để tránh trộn phiên bản.

### 2. Ưu tiên tái sử dụng, chỉ thêm lớp tổng hợp thiếu

Catalog: `pipeline/ai_library/importer.py`, `classroom_demo.py`, `expanded_catalog.py` (logic trùng/NFC ở lô tương ứng), `classroom_snapshot.py`, `reader_snapshot.py`; test `pipeline/tests/test_importer_quarantine.py`, `test_classroom_demo.py`, `test_content_review.py`. E5/index: `book_embeddings.py`, `e5_encoder.py`, `c11_bundle.py::load_c11_bundle`, `book_index.py::load_book_index`, test `test_c11_bundle.py`, `test_book_index.py`. Reader: `pipeline/scripts/p3_reader_check.py`, `verify_p4_week3.py --component reader`, `api/src/services/catalog.py::open_catalog`, `api/tests/test_catalog_reader.py`. Lưu ý `verify_p4_week3.py` hiện nhắm bộ C38 cũ và Reader, chưa phải validator r8. Ở lượt chạy này Python không khởi động được; lớp Node chỉ sàng lọc tĩnh và tổng hợp đọc SQLite/vector, không thay thế Pydantic/importer hoặc chứng minh kết quả valid/quarantined của importer. Khi runtime sẵn có, chạy validator Python trên fixture/bản sao cô lập và đối chiếu riêng kết quả. Các phép import/build có tác dụng phụ phải chạy trên bản sao tạm.

### 3. Đối chiếu tập ID và provenance theo tầng

Tính tập ID catalog P3, tập Search P3/r8, tập đã duyệt theo content type, tập vector/mapping/FAISS và SQLite. Báo chênh lệch 294/289/286/3 theo tập tham chiếu rõ ràng; năm QC blocked v4 không đồng nhất ba pending r8. So `review.json` với source URL/ID và trạng thái ở r8. Đối với 119/63/64, xác định snapshot/baseline ngay trước review P4 bằng commit, file/handoff và khóa so sánh; nếu không tìm được, giữ số liệu PR ở mức báo cáo bàn giao và ghi UNVERIFIED cho phép tái hiện. Near-duplicate tên/tác giả/work_id là danh sách cho người duyệt, không tự gộp.

### 4. Hai mức kiểm chứng embedding

Mức cấu trúc: tính lại năm dòng từ r8 catalog/taxonomy, hash per-book khớp mapping, catalog SHA-256 khớp bundle, nguồn bundle khớp index và snapshot; so vector shape/dtype/finite/nonzero/L2, `ntotal`, row order và ID. Mức inference: cần log build hoặc re-encode có model/tokenizer revision đúng và so kết quả theo tolerance đã ghi; chỉ thực hiện nếu được phép ở phase triển khai. Hash file chỉ gắn catalog với bundle, hash mapping gắn text với ID, vector row thay đổi đồng thời với summary là bằng chứng hỗ trợ nhưng **không chứng minh** encoder nào đã chạy. Kiểm 480 token bằng tokenizer revision thật nếu sẵn có; không suy PASS từ word count. Không rebuild dữ liệu nguồn/index để làm audit.

### 5. Reader theo bốn tầng

Tầng (a) JSONL/registry/rights: chapter IDs, order_no liên tục, paragraph IDs, NFC và các nguồn approved hợp lệ theo phạm vi; (b) SQLite: FK, row counts, text hash, offset code point và text slice; (c) Reader API: mở đúng book/chapter/snapshot, xử lý ID mất/sai snapshot; (d) frontend: hành vi đọc thật và highlight khi có bằng chứng browser. P3 `data/raw/p3_reader/` và P4 `data/raw/p4_w03_reader2/` là hai provenance riêng. Snapshot `p4-c42-reader2-20261122-r1` không thay cho Search r8. `acceptance_scope` trong manifest C42 vẫn nhắc C29 một tác phẩm trong khi counts là hai: báo WARNING tài liệu, kiểm chứng dữ liệu độc lập trước khi phân loại nặng hơn.

### 6. Report và tiêu chí quyết định

Đầu ra đề xuất: `audit_run.json` (input pin, phạm vi, SHA và tool versions), `checks.jsonl` (một dòng/check/record), `exceptions.jsonl` (FAIL/WARNING/UNVERIFIED theo ID), `summary.md` (số liệu, phân nhóm, xác nhận P3/P1/P4). Mỗi dòng có `check_id`, `category`, `status`, `severity`, `record_id`/`book_id`, `snapshot_id`, `expected`, `observed`, `evidence` (path + key/line/hash/test command), `recommended_action`; thêm `phase`, `source_requirement`, `assignee` khi có. Không điền record PASS giả.

PASS chỉ khi check chạy và đạt; WARNING cho ngoại lệ/điểm nghi vấn cần theo dõi; FAIL khi điều kiện bắt buộc bị vi phạm có bằng chứng; UNVERIFIED khi thiếu runtime/khả năng đọc/lineage. File được manifest khai báo mà thiếu và payload NPY đã nhận diện nhưng hỏng là FAIL; định dạng chưa hỗ trợ hoặc runtime không sẵn có là UNVERIFIED. Severity tách `blocking_snapshot`, `blocking_content_scope`, `non_blocking`, `human_review`, `environment_dependent`. Hash/index/ID sai có thể chặn snapshot Search; source fulltext sai chỉ chặn nội dung Reader liên quan; pending cần xét theo phạm vi và quyết định duyệt, không tự chặn mọi endpoint. Phase 1 có thể được review độc lập; C45 Done đòi đủ đầu vào và review Phase 2.

## Risks / Trade-offs

- [Mốc so sánh P4 chưa rõ] → Ghi rõ baseline từng phép diff, không bác bỏ số 63/64 bằng diff từ P3 v4.
- [Hash/catalog khớp nhưng vector do model khác tạo] → Tách structural PASS khỏi inference UNVERIFIED; yêu cầu log/model cache khi review.
- [Review AI hoặc approval demo bị hiểu là quyền công khai] → Ghi reviewer, căn cứ, phạm vi lãnh thổ và trạng thái nguồn riêng; P3/P4 xác nhận con người trước phát hành ngoài phạm vi.
- [Snapshot Search r8 không chứa Reader, snapshot Reader không chứa Search] → Không cộng count giữa snapshot hay kết luận Reader production chỉ từ staging.
- [Validator đang build/ghi dữ liệu] → Chạy phép đọc hoặc bản sao tạm; giữ SHA đầu vào bất biến.
- [Model runtime/tokenizer/CI/browser không có ở máy audit] → UNVERIFIED rõ ràng, chỉ viện dẫn báo cáo cũ như tài liệu bàn giao.

## Migration Plan

Không có migration dữ liệu. Sau duyệt OpenSpec: triển khai audit Phase 1 trên r8 cố định; kiểm report và exceptions với P1/P3; giữ snapshot hiện hành. Khi C41/P4 xác nhận nguồn/Reader, chạy Phase 2 cho baseline hai sách rồi từng batch mới. Mọi sửa dữ liệu, re-embedding hoặc phát hành là công việc riêng sau review, không thuộc audit chỉ đọc.

## Phase 1 decision follow-up: pending candidates (22/11/2026)

P1/P2/P3/P4 đã thống nhất giữ `B_753970d9-0b2f-43b9-90aa-36f52e68d4c2`, `B_e5fdd2af-666c-4cb8-bd9e-0e02ef3dfedf`, `B_ec9d7595-0257-43d5-83cf-15d83d8640b9` và sáu nguồn pending trong catalog gốc, không cho ba sách hiện trong kết quả Semantic Search hoặc Recommendation demo trước khi duyệt. C45 ghi quyết định và bằng chứng; P1/P2 thực hiện thay đổi chức năng theo phần việc của mình. Không thay dữ liệu, approval, vector, mapping, FAISS, snapshot r8 hoặc active pointer trong lượt audit.

Ba tầng bằng chứng tách biệt: (1) cả ba book_id có trong mapping/index r8; (2) mã Search demo nhận pending và candidate filter hiện chỉ xét author/genre/fulltext, nên tập ứng viên theo mã có thể bao gồm chúng; (3) chưa chạy được API Search thực để chứng minh response. `/books/{id}/similar` và `/recommend` tại HEAD này còn là placeholder trả rỗng/503; `RecommendationRanker` là lõi nội bộ chưa nối endpoint. `load_preference_source` hiện dùng `load_c11_books` chỉ nhận nguồn approved, vì vậy không thể giả định lõi này đang phục vụ được bundle r8 có pending.

Phương án đề xuất cho P1/P2: tại thời điểm nạp dữ liệu demo, xác định tập ID đủ điều kiện bằng **cả metadata và summary đều approved** từ đúng SQLite/catalog đã gắn hash với snapshot, có thể dùng helper chung trong `api/src/services/eligibility.py`; giữ nguyên 289 ID/vector nội bộ và 294 metadata P3. P1 áp điều kiện vào candidate set trước xếp hạng và trước cắt k, không chỉ bỏ item sau khi đã cắt k. P2 áp cùng quy tắc vào tập ứng viên của `RecommendationRanker` và mọi luồng Similar khi tích hợp; không để endpoint placeholder được hiểu là đã xử lý. Với seed là sách pending, P2 cần xác định rõ hành vi lỗi hoặc `no_candidates` theo API contract hiện có trước khi bật endpoint. Bộ lọc phải đọc theo từng snapshot, fail closed khi thiếu dữ liệu quyền, không dùng allowlist ba ID cố định toàn hệ thống và không lẫn quyền demo với phát hành public. `/books` và `/books/{id}` là Catalog, vẫn giữ khả năng xem bản ghi pending theo quyết định giữ catalog; không dùng việc hiển thị catalog để suy quyền phục vụ gợi ý.

Lọc runtime giữ nguyên r8/hash và dễ rollback nhưng phụ thuộc mọi đường phục vụ đều dùng cùng chính sách; bộ 289 vector vẫn chứa pending. Phát hành snapshot mới chỉ gồm 286 sách sẽ thay mapping/index/SQLite/manifest và cần quy trình build, hash, nghiệm thu P4/P1/P2 mới; chưa có căn cứ để thực hiện trong C45. Nghiệm thu chức năng đòi test Search, Similar và Recommendation với ba ID pending, seed/filter/k/empty/approved control ở service lẫn API, đồng thời xác minh Catalog vẫn đọc được pending, trạng thái quyền, vector/index và hash cũ không đổi.

## Open Questions

- P4 cung cấp baseline tức thời và build log/revision nào cho đợt chỉnh 63 summary/64 nguồn? Nếu chưa có, report giữ so sánh đó UNVERIFIED, không cản việc thực hiện các check còn lại.
- P4 xác nhận bằng chứng API/frontend Reader thật và điều kiện mở rộng C41 theo phạm vi quyền nào? Nếu chưa có, tầng tương ứng của Phase 2 giữ UNVERIFIED.
