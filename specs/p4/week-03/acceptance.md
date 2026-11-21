# P4 — Nghiệm thu tuần 3

Cập nhật 22/11/2026. Tuần 3 chưa hoàn thành: C42 đạt phạm vi hai tác phẩm thật localhost Việt Nam; C38 đạt kỹ thuật ứng viên 289 sách; C46 chờ khởi động lại và kiểm Docker sạch.

| Task / SPEC | Đầu vào và phần đã đạt | Chưa đạt hoặc chưa kiểm |
| --- | --- | --- |
| C38 — 3.1–3.2, 9.3, 10.1–10.4, 14.2/14.6, N04/N06/N08 | P3 `a0666cc`: 32 tệp/4 nhóm khớp hash; bundle 289×384 float32/L2. Index mới nạp đúng 289 vector, 289 self-query top 1; ba query thật khớp NumPy toàn bộ thứ tự. API 289 sách/17 query, lõi C13 với 1/2/3 seed đạt. Bộ 150 cũ giữ hash/nạp được | Pending giữ nguyên, ngưỡng 0.75 chưa hiệu chỉnh; chưa thay C39/C40 đo AI hoặc chốt corpus/quyền public C37/C45. Chưa có xác nhận P1/P2 tích hợp |
| C42 — 3.1, 7.2, 9.2–9.4, 12.4, 13.4–13.6, N05/N07, E2E-09 | Batch riêng sau rà nguồn/quyền; P3 giữ pending. ICU 79.1/CLDR 49.0, giữ ID. API đủ 2 sách/28 chương/4.301 đoạn đúng text/hash/offset. Chín nhóm kiểm Edge đạt, gồm lỗi tiêm có nhãn | Chỉ localhost Việt Nam; chưa thay corpus 20 toàn văn C41 hoặc QA/citation tuần 4, chưa có xác nhận P2 tích hợp |
| C46 — 2.1, 14.3–14.6, N03/N06–N08 | WSL 3.0.5.0 cài thành công, Virtual Machine Platform cần reboot; temp D, vị trí distro D đã xác định | Chưa có distro/Docker daemon chạy, clean build/proxy smoke/restore; chưa có GCP/DNS và số đo máy tham chiếu |

## Kiểm chứng đã chạy

142 test sau tích hợp develop/P3 đạt, gồm catalog/Reader/ICU/classroom Search/health/C11/index/refresh/handoff. Sau adapter Reader, 73 test liên quan đạt. Một cảnh báo deprecation Starlette/httpx, không có test lỗi.

```powershell
.\.venv\Scripts\python.exe -B -m pytest api/tests/test_catalog_reader.py api/tests/test_catalog_icu.py api/tests/test_classroom_search.py api/tests/test_health.py pipeline/tests/test_c11_bundle.py pipeline/tests/test_book_index.py pipeline/tests/test_index_refresh.py pipeline/tests/test_p3_handoff.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B -m pytest api/tests/test_catalog_reader.py api/tests/test_catalog_icu.py pipeline/tests/test_content_review.py pipeline/tests/test_p3_handoff.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B pipeline/scripts/verify_p4_week3.py --component all
```

Bộ kiểm sản phẩm đạt cả ở repo và bản xuất Git `df4e5cb`: hash 13 tệp mỗi thành phần, nạp 289 vector và Reader hai tác phẩm. Đây là mô phỏng nhận checkout dùng venv Windows hiện có, chưa phải máy sạch C46. Các lượt Edge/API dùng FastAPI/SQLite thật; chỉ ca mất mạng/trì hoãn request được tiêm lỗi, không dùng response mẫu cho lượt bình thường.

## Bàn giao

C38 tại `data/demo/p4-w03-c38-289-20261122/` (`b944395`); C42 tại `data/raw/p4_w03_reader2/` (`7b8ff16`) và `data/demo/p4-w03-c42-reader2-20261122/` (`df4e5cb`). Mỗi sản phẩm có README, manifest/hash và được giữ trong Git để dùng ngay, không phải sinh lại bundle. Không chứa model cache/khóa/control local. Chưa có xác nhận bên nhận tích hợp.

Không tự merge PR. Coreach chỉ được ghi nhận sau khi lưu và tải lại kiểm trên web; không dùng báo cáo local thay kết quả cập nhật từ xa. Không thay SPEC, không tự giảm yêu cầu public/RAG hoặc tự khởi động lại máy.

SPEC SHA256 `20cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea`; Sheet `02_Cong_viec!A40:O52` đọc trực tiếp 22/11/2026. Nền P4 `36ad1d4`, develop `6e873a6`, bàn giao P3 `a0666cc`. [PR #17](https://github.com/w-w2504/UET.CS2046_6-G16-SmartLibAI/pull/17).
