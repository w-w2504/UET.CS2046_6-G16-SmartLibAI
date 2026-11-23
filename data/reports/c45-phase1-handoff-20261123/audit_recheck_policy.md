# C45 — quy tắc audit lại

Sau commit C45: kiểm file trong commit_manifest, checkout sạch có đủ dependency, tái lập báo cáo vào thư mục mới và chạy test C45. Không chạy lại E5/FAISS nặng nếu đầu vào/model không đổi.

Khi C41 đủ 20 toàn văn: mở C45 Phase 2 cho provenance/quyền của tác phẩm và phiên bản, chapter/paragraph, manifest/hash, offsets và Reader API. Không tự mở lại lịch sử Phase 1 không liên quan.

Trước demo/bàn giao cuối kỳ: kiểm snapshot thực sự phục vụ Search, Recommendation, Reader; eligibility, quyền nguồn, integrity và hiệu lực exception register.

Mở sớm đúng check bị ảnh hưởng nếu catalog/snapshot, metadata/summary/URL, rights_status, eligibility thay đổi; pending lọt API; có lỗi/bằng chứng mâu thuẫn mới; hoặc chuyển từ demo nội bộ sang phát hành công khai. Đổi ngày chạy audit không tự mở lại ngoại lệ.

Mọi lần chạy ghi phiên bản/hash đầu vào và xuất thư mục mới. Không sửa báo cáo lịch sử; không tính ngoại lệ được chấp nhận là PASS. Không tự động chạy theo lịch hoặc kích hoạt Phase 2 từ tài liệu này.
