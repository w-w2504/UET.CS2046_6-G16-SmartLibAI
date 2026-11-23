# Spec Delta

## Purpose

Cho phép P3 kiểm định chất lượng và quyền nguồn của một bộ dữ liệu đã cố định, bàn giao báo cáo ngoại lệ theo ID có thể tái lập và nêu rõ mọi giới hạn bằng chứng trước khi dùng bộ đó cho Search, Reader hoặc nghiệm thu.

## ADDED Requirements

### Requirement: Đầu vào audit được định danh và không biến đổi
Quy trình audit SHALL nhận đường dẫn catalog, taxonomy, registry nếu có, artefact Search/Reader nếu có, phạm vi quyền sử dụng và snapshot ID được chỉ định; SHALL ghi phiên bản/hash đầu vào và không sửa đầu vào, trạng thái duyệt, active pointer hoặc snapshot.

#### Scenario: Bộ r8 được chỉ định
- **WHEN** kiểm r8 với catalog, bundle, index và snapshot hiện hữu
- **THEN** báo cáo ghi đường dẫn, snapshot ID, hash/phiên bản của từng đầu vào đã đọc và phạm vi `classroom_demo`
- **AND** các file nguồn và active pointer giữ nguyên.

#### Scenario: Artefact đã khai báo bị thiếu hoặc hỏng
- **WHEN** file bắt buộc đã khai báo trong manifest thực sự thiếu hoặc file đã nhận diện bị hỏng theo kiểm tra cấu trúc
- **THEN** check tương ứng FAIL kèm đường dẫn, tiêu chí vi phạm và bằng chứng; không tạo artefact thay thế.

#### Scenario: Chưa thể đọc artefact
- **WHEN** runtime không sẵn có, không đủ quyền đọc, hoặc định dạng chưa được bộ đọc hỗ trợ
- **THEN** check phụ thuộc được ghi UNVERIFIED kèm lý do; không suy diễn PASS hoặc FAIL về nội dung chưa đọc được.

### Requirement: Nguồn được kiểm theo nội dung và phạm vi quyền
Audit SHALL kiểm căn cứ nguồn và trạng thái duyệt riêng cho metadata, summary, cover khi có cover, fulltext khi có toàn văn; SHALL lưu ngoại lệ theo book_id/source_id và phân biệt `approved`, `pending`, `rejected` trong từng dataset và phạm vi sử dụng.

#### Scenario: Nguồn đã duyệt cho demo
- **WHEN** nguồn có URL/ghi chú và trạng thái approved cùng bằng chứng duyệt cần thiết cho phạm vi audit
- **THEN** check cấu trúc/duyệt được đánh giá theo bằng chứng; không tự kết luận có quyền phát hành công khai.

#### Scenario: Ba sách r8 còn pending
- **WHEN** catalog Search r8 chứa nguồn pending
- **THEN** báo cáo nêu đúng book_id, content_type và tác động tới phạm vi demo/phát hành đang xét
- **AND** pending không tự trở thành rejected, không tự loại sách khỏi mọi chức năng, không tự thay quyết định người duyệt.

#### Scenario: Kiểm khả năng phục vụ nguồn pending
- **WHEN** snapshot demo cho phép pending trong tập ứng viên Search còn SPEC v0.1 UC-S yêu cầu chọn sách đã duyệt
- **THEN** báo cáo ghi rõ sự khác nhau giữa ngoại lệ demo và tiêu chí nghiệm thu, kiểm khả năng xuất hiện của ba ID pending, ghi quyết định P1/P2/P3/P4 giữ catalog nhưng loại pending khỏi kết quả Semantic Search và Recommendation demo
- **AND** không tuyên bố kiểm quyền theo SPEC đã PASS chỉ vì loader chấp nhận snapshot demo.

#### Scenario: Quyết định đã có nhưng chưa triển khai

- **WHEN** P1/P2/P3/P4 đã chốt loại sách pending khỏi kết quả nhưng snapshot và mã runtime chưa được sửa
- **THEN** báo cáo phân biệt ba mức nằm trong index, được chọn làm ứng viên và xuất hiện trong API response; giữ bằng chứng API chưa chạy ở UNVERIFIED
- **AND** nêu owner, phương án lọc theo quyền của đúng snapshot và regression tests trước khi nghiệm thu; không tự đổi approval hoặc suy rằng quyết định đã có hiệu lực.

#### Scenario: Nguồn fulltext Reader riêng
- **WHEN** cùng tác phẩm xuất hiện ở lô P3 pending và lô C42 được duyệt cho localhost Việt Nam
- **THEN** báo cáo giữ hai provenance, review scope và snapshot tách biệt; không lấy approval của lô này để sửa lô kia.

### Requirement: Danh mục và quan hệ được đối chiếu
Audit SHALL kiểm schema BookImport/ChapterImport/SourceImport phù hợp đầu vào, trường bắt buộc, taxonomy, Unicode NFC, ID và registry, bản ghi trùng/nghi trùng, quan hệ book_id/work_id/chapter_id và khóa ngoại; SHALL báo trường hợp lỗi theo ID và phân biệt nghi trùng cần con người quyết định.

#### Scenario: Sách hợp lệ và các tập con
- **WHEN** đối chiếu catalog P3 và Search r8
- **THEN** báo cáo ghi tổng số và chênh lệch ID giữa các tập, lý do loại trừ có bằng chứng; không áp dụng số approved của Search cho toàn catalog.

#### Scenario: ID mồ côi hoặc nhãn lạ
- **WHEN** chapter trỏ tới book_id thiếu, ID tái sử dụng sai thực thể, hoặc mã genre/topic không có trong taxonomy đã chốt
- **THEN** check tương ứng FAIL kèm ID, expected/observed và đường dẫn record; bản nghi trùng chỉ WARNING cho đến khi con người xác nhận.

### Requirement: Văn bản và lineage embedding được kiểm có điều kiện
Audit SHALL đối chiếu mô tả/biểu diễn sách năm dòng, NFC, giới hạn 480 token gồm prefix và special tokens, model/revision và content_hash của mapping theo SPEC §10.4 khi có tokenizer/bằng chứng phù hợp; SHALL phân biệt hash tệp với bằng chứng text đã dùng để mã hóa từng vector.

#### Scenario: Mô tả r8 đã thay đổi
- **WHEN** một mô tả/nguồn được sửa trong r8 và mapping, build log hoặc lineage cho phép nối book_id → text/hash → vector của cùng lượt build
- **THEN** đối chiếu đúng phiên bản text với vector và ghi PASS/FAIL theo kết quả có bằng chứng.

#### Scenario: Không có lineage hoặc tokenizer đúng revision
- **WHEN** manifest chỉ gắn hash catalog hoặc không có chứng cứ per-record/encoder phù hợp
- **THEN** check tương ứng UNVERIFIED với bằng chứng còn thiếu; không kết luận vector sai hoặc token hợp lệ chỉ từ việc file có hash.

### Requirement: Snapshot và index được đối soát
Audit SHALL kiểm hash/size của file đã khai báo, snapshot ID, cùng tập book_id có vector giữa catalog, SQLite, mapping, ma trận float32 hữu hạn 384 chiều chuẩn hóa L2 và FAISS, số lượng/row order, foreign-key integrity; SHALL ghi rõ tập catalog ngoài Search và quyền pending.

#### Scenario: Artefact đồng bộ
- **WHEN** file và cấu trúc đọc được, count/dimension/hash/mapping/ID đều khớp theo snapshot đã chọn
- **THEN** từng check đã chạy có thể PASS với đường dẫn và kết quả đo; không mặc định PASS cho kiểm tra chưa chạy.

#### Scenario: Hash hoặc row mapping lệch
- **WHEN** hash đã công bố không khớp byte file hoặc một row trỏ sai book_id
- **THEN** check FAIL ở phạm vi ảnh hưởng và được đánh dấu chặn phát hành snapshot liên quan; không thay active pointer.

### Requirement: Toàn văn và Reader có bằng chứng theo tầng
Audit SHALL kiểm chapter/paragraph/registry, order_no, text NFC, các lát cắt offset Unicode code point, nguồn fulltext và liên kết tới đúng book_id/snapshot cho mỗi batch có sẵn; SHALL báo riêng cấu trúc staging, import SQLite, phục vụ Reader API và kiểm thử frontend.

#### Scenario: Baseline hai tác phẩm
- **WHEN** kiểm C42 Reader baseline
- **THEN** báo cáo đối chiếu 2 work, 28 chương, 4.301 đoạn với dữ liệu đọc thực tế và manifest, nêu rõ những tầng nào đã kiểm độc lập
- **AND** Search/RAG không được suy ra đã sẵn sàng từ Reader staging.

#### Scenario: C41 chưa đủ đầu vào
- **WHEN** Phase 2 chưa có các tác phẩm mới hoặc chưa có xác nhận cần thiết từ P4
- **THEN** phần phụ thuộc ghi UNVERIFIED/chưa hoàn tất, Phase 1 vẫn có thể hoàn thành độc lập và toàn C45 chưa được đánh dấu Done.

### Requirement: Báo cáo kiểm tra và ngoại lệ có thể truy vết
Audit SHALL xuất mỗi kết quả với `check_id`, `category`, `status`, `severity`, `record_id` hoặc `book_id` nếu có, `snapshot_id`, `expected`, `observed`, `evidence`, `recommended_action`; SHALL ghi input version, check version/thời điểm, phạm vi, Phase và tổng hợp theo trạng thái.

#### Scenario: Kết quả bốn trạng thái
- **WHEN** check được chạy và đạt, cần theo dõi, vi phạm tiêu chí bắt buộc đã xác minh, hoặc thiếu bằng chứng
- **THEN** status lần lượt là PASS, WARNING, FAIL, UNVERIFIED với bằng chứng/giới hạn tương ứng; UNVERIFIED không được tính là PASS.

#### Scenario: Phân loại tác động
- **WHEN** có lỗi chặn snapshot, vấn đề cục bộ, ngoại lệ quyền cần người duyệt hoặc phụ thuộc runtime/C41
- **THEN** báo cáo phân biệt severity, phạm vi ảnh hưởng và hành động/owner cần xác nhận; không tự duyệt, tự sửa hoặc gọi tất cả lỗi là chặn mọi chức năng.

### Requirement: Nghiệm thu theo hai phase
C45 SHALL có kết luận Phase 1 cho Catalog/Search r8 và Phase 2 cho Fulltext/Reader theo các đầu vào và tiêu chí của từng phase; chỉ ghi hoàn thành toàn C45 khi cả hai có đủ bằng chứng, ngoại lệ được xử lý hoặc được chấp nhận có ghi nhận, và P3/P1 đã review.

#### Scenario: Phase 1 đủ bằng chứng nhưng Phase 2 đang chờ
- **WHEN** kiểm Catalog/Search và báo cáo ngoại lệ Phase 1 đã được review, còn C41/Reader thiếu đầu vào
- **THEN** ghi Phase 1 hoàn thành và Phase 2 đang chờ, không báo C45 Done hoặc đạt nghiệm thu toàn hệ thống.

#### Scenario: Phát hành có lỗi blocking
- **WHEN** check bắt buộc về index, liên kết, quyền theo phạm vi hoặc hash FAIL
- **THEN** báo cáo nêu rõ snapshot/phần chức năng bị chặn, giữ nguyên snapshot đang phục vụ và chuyển cho người có thẩm quyền quyết định khắc phục.
