# Design

## Context

Xem proposal.md. C42 có 2 sách/28 mục/4.301 đoạn trong batch P4; C29 có 1 sách/1 chương/39 đoạn, registry khác hình dạng nhưng snapshot adapter đã chấp nhận từng kiểu riêng. Search r8 đã duyệt metadata/summary cho demo nội bộ, không tự xét quyền toàn văn hoặc Reader.

## Goals / Non-Goals

**Goals:** Tạo bộ C41 riêng, tái dùng chính xác bản ghi được duyệt và ID nguồn; kiểm từng bản toàn văn, trích chương/đoạn và bàn giao được cho P4.

**Non-Goals:** Không thay API/active snapshot, Search, Recommendation, RAG hoặc nguồn C29/C42/r8 đã đóng băng.

## Decisions

1. Dataset C41 chứa bản sao có hash kiểm được của 2 sách C42, thêm sách đủ điều kiện theo batch. Không sửa đầu vào đóng băng. Mỗi bản ghi Search r8 được chọn nguyên nội dung metadata/summary và source ID; quyết định áp dụng phạm vi Reader ghi riêng, không sửa r8.
2. Chuyển mapping registry C29 sang dạng lồng `chapters`/`paragraphs` của C42, giữ nguyên H_/P_ ID. Không ghép hai hình dạng mapping thô vì adapter yêu cầu cả hai ánh xạ đồng nhất khi cùng hiện diện.
3. Trích xuất nguồn bằng script kiểm hash, spine/TOC, đoạn đầu/cuối và nội dung từng chương; ghi danh sách ngoại lệ. Chỉ nhận bản số hóa khi quyền của chính bản đó và phần biên tập đã được xác minh. EPUB *Số đỏ* ấn bản 2003 hiện không đủ căn cứ; không nhập vào tập approved.
4. Snapshot thử nghiệm mới chỉ được dựng bằng `reader_snapshot` từ batch đã có tất cả metadata/summary/fulltext approved; giữ snapshot C42 và active pointer. Nếu manifest producer ghi phạm vi C29 một tác phẩm, báo cáo rõ giới hạn hoặc điều chỉnh mô tả trước khi bàn giao snapshot C41.

## Risks / Trade-offs

- [Nguồn có bản 2003 hoặc thiếu cuối truyện] → Giữ ngoài corpus approved, tìm ấn bản khác và ghi ngoại lệ.
- [Approval r8 chỉ cho Search demo nội bộ] → Dùng nội dung đã duyệt nhưng ghi quyết định phạm vi Reader riêng; không suy quyền từ trạng thái Search.
- [Registry lẫn hai định dạng] → Chuyển có kiểm tra ID và hash, không cấp lại ID cũ.
- [Script kiểm cũ cố định 2/28/4301] → Giữ kiểm hồi quy baseline; thêm kiểm C41 theo số lượng thực.

## Migration Plan

Batch 1 đã chốt bốn tác phẩm; *Số đỏ* chưa được nhận. Batch 2 thêm tám tác phẩm và lưu cả batch mới riêng lẫn bộ tích hợp 12 tác phẩm; Batch 3 còn tám tác phẩm, chưa triển khai. Nguồn mới không có catalog tương ứng dùng ID UUIDv5 ổn định và source ID riêng sau đối chiếu catalog; không sửa catalog gốc. Quyền metadata/summary/fulltext xét riêng theo giấy phép rõ ràng của đúng ấn bản/bản dịch; Codex ghi kiểm tra tự động, không giả chữ ký P3/P4. Điều kiện ghi công/giấy phép/thay đổi được đưa vào NOTICE và mục đọc đầu của mỗi tác phẩm mới. PDF dùng trang vật lý làm mục đọc có định vị, không giả gọi trang thành chương nguyên tác; EPUB giữ spine và dòng thơ. P3 tự kiểm SQLite/ASGI/HTTP trên snapshot riêng; P4 chỉ cần phối hợp nếu có lỗi Reader production. C45 Phase 2 dùng manifest và review sau khi corpus đủ điều kiện. Không đổi active pointer.
