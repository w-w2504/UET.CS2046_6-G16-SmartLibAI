# C41 — nghiệm thu kỹ thuật corpus Reader 20/20

Ngày: 24/11/2026<br>
Snapshot kiểm thử riêng: `c41-reader20-batch3-20261123`<br>
Branch/HEAD: `feature/data-embedding` / `3c723b2fa1fcfaa3956e60eb9863557f30f46262`

## Kết quả nghiệm thu

Dataset tích hợp chứa 20 tác phẩm và snapshot SQLite có 20 books, 20 works, 1.020 reading items, 13.292 paragraphs. `PRAGMA integrity_check` trả `ok`; `PRAGMA foreign_key_check` không có lỗi.

Reader ASGI và HTTP TCP/Uvicorn đã được chạy với SQLite thật. ASGI kiểm tra 20 chi tiết sách, 20 TOC, 1.020 chi tiết mục đọc và 13.292 offsets; ID/chunk không hợp lệ trả 404. HTTP đối chiếu toàn bộ text, IDs, thứ tự và offsets với SQLite; tất cả khớp. Server thử nghiệm đã dừng sau kiểm tra.

Pytest Reader/source-policy đạt 62/62; Node tests Batch 1–2 đạt 8/8; OpenSpec strict và `git diff --check` đạt. P3 xác nhận kiểm tra 231/231 hash được bảo vệ không lệch, và regression Batch 2 → Batch 3 không thiếu hoặc thay đổi 702 chapters / 12.035 paragraphs (bỏ qua trường `snapshot_id`). Kết quả này được ghi nhận theo bằng chứng/kết quả chạy trực tiếp do P3 cung cấp; không chạy lại các bài test đã đạt.

## Phạm vi

Đây là **nghiệm thu kỹ thuật của bộ dữ liệu và Reader API trong snapshot thử nghiệm**, không phải xác nhận nghiệm thu của P4, không phải phát hành công khai, và không kích hoạt snapshot. Active snapshot không bị thay đổi. Search, Recommendation và RAG không thuộc kiểm thử này.

C42 được kiểm hồi quy thành công trong Batch 2; chưa có phép so sánh C42 trực tiếp với snapshot Batch 3. Browser E2E chưa chạy và cần được thực hiện trước demo. Hai giới hạn này không phủ định các kết quả SQLite/ASGI/HTTP đã đạt, nhưng phải được giữ trong hồ sơ bàn giao.

## Trạng thái

**C41 dataset/API: kỹ thuật đạt 20/20.** Còn việc P4 xem xét và tích hợp theo quy trình C42, browser E2E trước demo, cùng bàn giao provenance để C45 Phase 2. Không đánh dấu P4 đã nghiệm thu.
