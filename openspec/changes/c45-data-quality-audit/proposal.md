# Proposal

## Why

C45 (W3, P3; P1 hỗ trợ) cần bàn giao **Data audit + exceptions** trước khi dữ liệu Search r8 và Reader được dùng làm căn cứ nghiệm thu. PR #22 đã đưa vào một catalog Search 289 sách, 286 sách có nguồn được duyệt cho demo nội bộ và 3 sách còn pending; các sửa đổi mô tả/nguồn và bộ Reader riêng cần được đối chiếu bằng bằng chứng, không suy diễn từ báo cáo bàn giao.

## What Changes

- Bổ sung khả năng audit chỉ đọc, tái lập được, trên tập đầu vào được chốt phiên bản: kiểm source rights/provenance theo loại nội dung; schema, taxonomy, ID, trùng/lạc tham chiếu, Unicode, mô tả và giới hạn token theo SPEC v0.1 §3.1, §10.1, §10.4.
- Đối chiếu catalog, biểu diễn E5, vector, mapping, FAISS, SQLite, manifest/hash và snapshot theo SPEC §3 và §14.6; riêng lineage của 63 mô tả sửa trong r8 phải có bằng chứng liên kết text → vector hoặc ghi UNVERIFIED. Đây là kiểm tra bổ sung do PR #22.
- Kiểm toàn văn theo từng batch với chapter/paragraph ID, thứ tự, code-point offsets, liên kết catalog và nguồn fulltext riêng. Hai tác phẩm hiện có là baseline; việc mở rộng phụ thuộc C41 và xác nhận của P4 về Reader.
- Xuất báo cáo theo từng check và exception theo ID, với PASS/WARNING/FAIL/UNVERIFIED, mức độ ảnh hưởng, đường dẫn bằng chứng và hành động đề xuất. Phase 1 (catalog/Search r8) và Phase 2 (fulltext/Reader) có kết quả riêng; thiếu đầu vào Phase 2 không được coi toàn C45 hoàn thành.
- Ưu tiên chạy lại validator/importer/test có sẵn; chỉ bổ sung kiểm tra hoặc bộ tổng hợp báo cáo khi các công cụ hiện tại không cho đủ bằng chứng. Không thay đổi quyết định duyệt nguồn.

## Capabilities

### New Capabilities

- `data-quality-audit`: Quy trình kiểm định chỉ đọc, phân loại kết quả và xuất báo cáo ngoại lệ có bằng chứng cho catalog, Search và Reader.

### Modified Capabilities

Không có. `book-embeddings` vẫn giữ hợp đồng C11; C45 kiểm chứng và đối chiếu artefact mà không đổi thuật toán hoặc đặc tả encoder.

## Impact

Nguồn yêu cầu: SPEC/SRS v0.1 §3, §3.1, §10.1, §10.4, §11.1–11.3, §14.6 và §15; workbook `02_Tasks`, C45 (23/11/2026, phụ thuộc C37/C41). Repo baseline: HEAD `ae417fe` chứa merge PR #22 và commit C38 `86bc2b6`; P3 `data/raw/p3_v4/`, Search r8 `data/demo/p4-w03-c38-reviewed-r8-20261122/`, Reader `data/raw/p4_w03_reader2/` và `data/demo/p4-w03-c42-reader2-20261122/`. Có thể tác động tới script kiểm tra, test và báo cáo khi triển khai sau khi duyệt; không đổi API contract, schema Reader, frontend, dữ liệu nguồn, vector/index hoặc snapshot trong change planning này.

Ranh giới: 294 sách metadata P3 là tập khác với 289 sách Search; 286 approved + 3 pending chỉ phân hoạch 289 sách r8, không phải tổng catalog. Quyền demo nội bộ/localhost không tự suy ra quyền công khai; chưa có kết quả audit độc lập về tính khớp của mọi vector sau sửa mô tả. C41 đặt mục tiêu 20 tác phẩm nhưng hiện chỉ có baseline hai tác phẩm. C50/C53/C60 và phát hành production không thuộc C45.
