# C38 — Bàn giao Search demo r8

Bộ này đóng băng 289 sách Search từ bản P3 `a0666cc` sau khi đối chiếu nguồn và mô tả. Có 286 sách đủ căn cứ cho demo nội bộ và 3 sách giữ `pending`. Lượt r8 xử lý 122 sách, duyệt 119, sửa mô tả cho 63 sách và thay nguồn cho 64 sách. `review.json` ghi căn cứ đối chiếu, nguồn thay và lý do giữ pending theo ID.

- `search/` chứa catalog và taxonomy ghép đúng phiên bản với bundle.
- `bundle/` chứa 289 vector E5 đã chuẩn hóa L2, chiều 384, và manifest liên kết SHA-256 của đầu vào.
- `index/` chứa FAISS và mapping để P2 nạp khi chạy Recommendation ở chế độ classroom demo.
- `snapshot/p4-w03-c38-reviewed-r8-20261122/` chứa SQLite, FAISS, mapping và manifest để P1 chạy Search local.
- `handoff_manifest.json` ghi SHA-256 của các tệp dữ liệu và kết quả kiểm chỉ mục.

Để chạy Search, dùng cấu hình local của repo và đặt `SMARTLIBAI_DEMO_SNAPSHOT` trỏ tới đúng thư mục snapshot trên. `MODEL_ROOT` trỏ tới cache chứa revision E5 ghi trong manifest. Bản bàn giao giữ nguyên vector r8, nên nhận checkout có thể nạp index ngay. Ngưỡng Search 0.75 dùng cho demo.

Phạm vi `approved` gồm dữ kiện thư mục và mô tả tự biên soạn cho demo nội bộ theo SPEC 3.1–3.2. Snapshot được cấu hình `classroom_demo`. Các trường người duyệt nội bộ được bỏ khỏi gói chia sẻ. Phát hành công khai, Reader và RAG có điều kiện nghiệm thu riêng theo SPEC.

Ba sách còn pending là *Bài học lịch sử*, *Giải pháp công nghệ IoTs sử dụng kỹ thuật xử lý dữ liệu lớn và trí tuệ nhân tạo cho đô thị thông minh* và *Mối tình Rômêô Juliét*. Xem `review.json` để tìm căn cứ và điểm cần xác minh.
