# Spec Delta

## Purpose

Cho phép chuẩn bị và kiểm định một corpus toàn văn gồm các tác phẩm độc lập, có bản nguồn và quyết định quyền truy vết được, để P4 có thể tích hợp Reader theo đúng phạm vi thử nghiệm.

## ADDED Requirements

### Requirement: Kế thừa đúng bản ghi đã được xét
Corpus C41 SHALL giữ ID và nội dung của bản ghi đã duyệt khi tái sử dụng Search r8, C29 hoặc C42; SHALL giữ riêng phạm vi xét duyệt của metadata, summary và fulltext.

#### Scenario: Bản ghi r8 trùng bản C41
- **WHEN** ID, tác phẩm, tác giả, nội dung và nguồn khớp bản r8 đã duyệt
- **THEN** C41 dùng đúng bản metadata/summary đó, lưu dấu vết tới manifest/review r8 và ghi phạm vi Reader được xem xét riêng.

#### Scenario: Bản P3 khác bản r8
- **WHEN** nội dung hoặc URL nguồn P3 khác bản r8
- **THEN** C41 không nâng trạng thái của bản P3 cũ; C41 ghi khác biệt và dùng bản r8 nếu phù hợp Reader.

### Requirement: Quyết định duyệt toàn văn có căn cứ
Mỗi tác phẩm nhận vào corpus SHALL có bản nguồn định danh, hash, tác giả, ấn bản, nguồn số hóa, căn cứ quyền, ghi công và phạm vi duyệt Reader; phần dịch, biên tập và ảnh SHALL được xét riêng khi có.

#### Scenario: Nguồn đủ điều kiện
- **WHEN** toàn văn đã được đối chiếu đầy đủ với nguồn truy xuất được và quyết định quyền áp dụng cho Reader demo localhost tại Việt Nam
- **THEN** nguồn fulltext được ghi approved, `fulltext_approved=true` cùng URL, revision/hash, thời điểm và người hoặc quy trình xét duyệt thực tế.

#### Scenario: Ấn bản hiện đại chưa xét quyền
- **WHEN** bản số hóa chứa phần biên tập hoặc ấn bản chưa xác minh quyền
- **THEN** tác phẩm không được tính trong tập approved và không được nạp vào snapshot thử nghiệm.

### Requirement: Toàn vẹn văn bản và định danh
Corpus SHALL có `work_id` duy nhất cho mỗi tác phẩm độc lập, ID sách/chương/đoạn ổn định, liên kết catalog hợp lệ và nội dung chương/đoạn chuẩn NFC đúng thứ tự.

#### Scenario: Batch hợp lệ
- **WHEN** chương/đoạn được trích xuất từ nguồn đã xét
- **THEN** chương và đoạn đánh số liên tiếp, không rỗng; offsets trên chuỗi nối bằng hai dấu xuống dòng khớp từng đoạn và mọi ID không xung đột baseline.

#### Scenario: Thiếu nội dung hoặc mapping
- **WHEN** bản nguồn thiếu chương, đoạn, liên kết registry hoặc một quyết định nguồn bắt buộc
- **THEN** validator ghi lỗi/cách ly và tác phẩm không được tính là hoàn thành.

### Requirement: Bàn giao độc lập theo batch
C41 SHALL lưu dataset và báo cáo ở vị trí riêng, bảo toàn byte của C42/C29/r8 và ghi số tác phẩm đạt, lỗi, ngoại lệ theo từng batch.

#### Scenario: Batch được kiểm thử
- **WHEN** một batch hoàn thành đối chiếu nguồn, schema, registry và snapshot thử nghiệm
- **THEN** báo cáo phân biệt tác phẩm đã chuẩn hóa, đã duyệt nguồn, đạt validator và đã được P4 tích hợp.

#### Scenario: Chưa đủ hai mươi tác phẩm
- **WHEN** chưa có đủ 20 tác phẩm độc lập đạt mọi điều kiện
- **THEN** C41 vẫn đang thực hiện và báo cáo số thực tế cùng blocker, không tự đánh dấu Done.
