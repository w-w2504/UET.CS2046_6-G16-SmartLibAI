# P4 — Nghiệm thu tuần 2

Cập nhật 17/11/2026. Nguồn phân công đọc lại ngày 15/11; thiết kế C25/C29 đối chiếu SPEC tại develop bc25506. Bản SPEC làm việc đã có quyết định được duyệt về Search theo book_id và Recommendation khử trùng work_id, SHA-256 `20cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea`. Người dùng xác nhận chưa có vector/corpus mở rộng/toàn văn bên ngoài repo; tiếp tục mã/fixture và ghi rõ phụ thuộc đang chờ.

| Task | Phần triển khai/kiểm chứng | Trạng thái dữ liệu thật |
| --- | --- | --- |
| C21 | Đã viết yêu cầu; chưa hoàn thành adapter bundle C11 | Chờ vector P3 và corpus80 |
| C25 | Đã triển khai API SQLite; 60 kiểm thử API đạt ngày 17/11 trên fixture | Chờ snapshot phục vụ đủ điều kiện công khai |
| C29 | Đã chuẩn bị sáu tình huống kiểm thử Reader qua backend thật; chưa chạy browser checker | Chờ toàn văn/nguồn được duyệt |
| C35 | Đã viết yêu cầu; chưa hoàn thành rebuild an toàn | Chờ vector/corpus150–200 |

## Kiểm chứng kỹ thuật ngày 17/11

- Từ `api`: `../.venv/Scripts/python.exe -B -m pytest tests/test_catalog_reader.py tests/test_health.py -q -p no:cacheprovider --basetemp <thư mục tạm mới> --tb=short -x`: **60 passed**, một cảnh báo Starlette/httpx; 12,52 giây. Dùng SQLite/manifest/chương tự viết và collator kiểm thử; chưa xác nhận PyICU thực hoặc nguồn công khai.
- Từ `web`: `npm run build`: **đạt**, Vite 5.4.21, 1595 module; 21,74 giây. Build không thay thế kiểm thử trình duyệt C29.
- `web/tests/check_reader_api.py` đã có mã kiểm thử nhưng chưa chạy; không ghi nhận sáu tình huống này là PASS.
- Chưa có PR cho phần tuần 2 ở lượt lưu commit này. Chưa nghiệm thu dữ liệu thật, chất lượng AI, phát hành snapshot hoặc toàn bộ tuần 2.
