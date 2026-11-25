# Proposal

## Why

Reader C42 mới có hai tác phẩm; C41 cần bộ ít nhất 20 tác phẩm độc lập, có nguồn và quyết định quyền theo đúng phạm vi demo Reader. Search r8 đã xét metadata/summary của phần lớn catalog; C41 cần kế thừa đúng bản ghi đã xét thay vì duyệt lại hoặc sao chép trạng thái pending của bản cũ.

## What Changes

- Chuẩn bị bộ dữ liệu Reader riêng, giữ nguyên ID, văn bản và provenance của hai tác phẩm C42; tiếp nhận C29 khi ánh xạ registry không xung đột.
- Đối chiếu từng metadata/summary với bản r8 đã duyệt; ghi rõ quyết định áp dụng cho Reader và chỉ xét mới phần thực sự thay đổi.
- Kiểm nguồn toàn văn cụ thể, ấn bản, phạm vi sử dụng, sự đầy đủ, hash, ghi công và quyền của bản số hóa; chỉ nhận bản đủ căn cứ.
- Trích xuất chương/đoạn theo schema hiện có, kiểm ID, thứ tự, Unicode, offsets và snapshot thử nghiệm độc lập theo Batch 1/2/3.
- Bàn giao kết quả cùng ngoại lệ cho P4 tích hợp C42 và C45 kiểm toán Phase 2.

## Capabilities

### New Capabilities

- `reader-fulltext-corpus`: Chuẩn bị, xét nguồn và kiểm định bộ dữ liệu toàn văn có thể nạp vào Reader theo từng batch.

### Modified Capabilities

Không có; không thay đổi yêu cầu của `book-embeddings` hoặc API Reader.

## Impact

Đầu vào là `data/raw/p4_w03_reader2/`, `data/raw/c29_fulltext1/`, Search r8 và nguồn toàn văn được kiểm riêng. Đầu ra ở thư mục C41 riêng, kèm script/test và snapshot thử nghiệm nếu đủ điều kiện. Không sửa Search r8, C42 đã phát hành, C45, active snapshot, Search/Recommendation, RAG hoặc API contract. Batch 1 đã chốt bốn tác phẩm gồm hai baseline C42, *Sống chết mặc bay* và *Con nhà nghèo*. *Số đỏ* ngoài phạm vi nhận vì chưa đủ căn cứ ấn bản. Theo yêu cầu P3 ngày 23/11/2026, Batch 2 bổ sung tám tác phẩm đa dạng thể loại vào dataset riêng; Batch 3 còn tám tác phẩm, chưa triển khai. Chỉ nhận tác phẩm đạt quyền và chất lượng, không ép đủ số lượng.
