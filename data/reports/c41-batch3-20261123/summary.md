# C41 Batch 3 — nghiệm thu kỹ thuật 20/20

Ngày ghi nhận: 24/11/2026<br>
Branch: `feature/data-embedding`<br>
Snapshot thử nghiệm: `c41-reader20-batch3-20261123`

## Kết quả

Batch 3 bổ sung 8 tác phẩm vào bộ tích hợp Batch 1–2, nâng corpus Reader lên 20 tác phẩm độc lập. SQLite snapshot thử nghiệm có 20 books, 20 works, 1.020 mục đọc và 13.292 đoạn.

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| SQLite integrity | PASS | `asgi.json`: `integrity_check=ok`, foreign key violations = 0 |
| Import/build snapshot | PASS | `build.json`, manifest trong thư mục snapshot |
| Reader ASGI với SQLite thật | PASS | `asgi.json`: 20 book details, 20 chapter lists, 1.020 chapter details, 13.292 offsets; ID/chunk không tồn tại trả 404 |
| Reader HTTP TCP/Uvicorn | PASS | `http.json`: kiểm toàn bộ 20 sách/1.020 mục/13.292 đoạn; text, IDs, thứ tự và offsets khớp SQLite; nguồn được duyệt; server đã dừng |
| Regression dữ liệu Batch 2 → Batch 3 | PASS | 231/231 protected hashes PASS theo kiểm tra P3; 702 chapters và 12.035 paragraphs cũ còn nguyên, ngoại trừ `snapshot_id`; 0 thiếu/thay đổi |
| Regression Batch 1–2 Node | PASS | 8/8 theo lần chạy cuối trong Codex |
| Reader/source-policy pytest | PASS | 62/62 theo kết quả chạy trực tiếp của P3 trong `.venv` Python 3.13.14 |
| OpenSpec strict | PASS | Theo kết quả chạy trực tiếp của P3 |
| `git diff --check` | PASS | Theo kết quả chạy trực tiếp của P3 |
| Regression C42 đối chiếu trực tiếp với snapshot 20 tác phẩm | NOT_RUN | C42 đã đạt hồi quy với Batch 2; chưa có đối chiếu trực tiếp trong Batch 3 |
| Browser E2E | NOT_RUN | Cần kiểm tra UI Reader trước demo; không chặn nghiệm thu dữ liệu/API |

## Phạm vi và giới hạn

ASGI và HTTP đều dùng Reader thật cùng SQLite snapshot riêng. Snapshot này không được đặt làm active snapshot. Báo cáo health HTTP có `catalog_ready=false` và `snapshot_id=null`; kết quả nghiệm thu ở đây chỉ xác nhận các endpoint Reader được gọi tường minh với snapshot ID, không xác nhận Search, Recommendation, RAG hoặc health readiness.

Quyền và provenance được ghi theo từng nguồn trong dataset/manifest Batch 3; mỗi điều kiện giấy phép cần tiếp tục được giữ khi sao chép hoặc phân phối. Nghiệm thu này là kỹ thuật cho demo Reader nội bộ, không phải nghiệm thu của P4 và không cấp phép phát hành công khai.

## Kết luận

**C41 đạt nghiệm thu kỹ thuật dữ liệu và Reader API ở mức 20/20 tác phẩm** theo các bằng chứng nêu trên. Browser E2E vẫn cần thực hiện trước demo. P4 chưa được ghi nhận là đã nghiệm thu hoặc tích hợp snapshot này vào Reader production. C41 toàn cục chưa được đánh dấu hoàn tất ở đây; việc bàn giao P4 và C45 Phase 2 vẫn còn.
