# P4 — Nghiệm thu tuần 2

Cập nhật 18/11/2026. Đối chiếu SPEC gốc, các mục3.1–3.2,9.3–9.4,10.4,12.3–12.4,13.4–13.6,14.2/14.6 và16.2. SHA-256 SPEC: `20cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea`. Phân công Sheet đọc17/11. Nền tích hợp: develop `6b1e7c9`; merge vào feature/faiss-reader tại `2989158`, giữ lịch sử theo phương án người dùng duyệt. OpenSpec giữ local.

| Task | Kết quả kỹ thuật đã kiểm chứng | Phần chưa nghiệm thu |
| --- | --- | --- |
| C21 | Adapter bundle C11 kiểm hash nguồn/artefact, cấu hình E5, row/ID/content_hash và float32/384/L2; CLI chạy qua tiến trình riêng, round-trip FAISS và truy vết source_bundle | Đã kiểm bundle20 E5 thật tái tạo cục bộ; chưa có catalog/vector≥80, output vẫn là thành phần nội bộ |
| C25 | API list/detail/facets/mục lục/chương đọc SQLite, giữ schema C03, snapshot và ErrorResponse; health kiểm readiness ngoài event loop trong ngân sách2s | Chưa có snapshot công khai/toàn văn thật; collation ICU thật chưa kiểm chứng |
| C29 | 6/6 tình huống browser qua Vite→FastAPI→SQLite fixture đạt; không route mock hoặc reader_fixture | Chưa có sách thật và nguồn được duyệt; chưa nghiệm thu QA/citation |
| C35 | Rebuild đích mới, kiểm fixture20/80/150, từ chối serving/ghi đè, mô phỏng lỗi sau ghi FAISS vẫn giữ index cũ/active | Chưa có catalog/vector150–200; không thay nghiệm thu activation/rollback toàn hệ thống |

## Kiểm chứng ngày18/11

- Từ `api`, đặt PYTHONPATH trỏ pipeline; chạy Python trong .venv: `python -B -m pytest tests -q -p no:cacheprovider --basetemp <temp-moi> --tb=short -x`: **275 passed**,19,88s; một cảnh báo Starlette/httpx. Có61 test catalog-reader/health; các test dùng SQLite/manifest/chương tự viết và collator tiêm cho fixture.
- Từ `pipeline`: cùng lệnh pytest trên `tests`: **85 passed**,4,53s sau merge. Trong đó29 test adapter/refresh C21/C35, gồm CLI subprocess và dữ liệu tổng hợp20/80/150; không chạy E5 để sinh vector.
- Từ `api`: `python -B scripts/export_openapi.py --check`: **đạt**. Schema và encoder C08 giữ nguyên so với develop; không sửa contract để hợp thức hóa API.
- Từ `web`: `npm run build`: **đạt**,1596 module; `node scripts/check-demo.mjs`: **đạt**. Log storage unavailable là tình huống cố ý của checker.
- Từ repo: `python -B web/tests/check_reader_api.py --base-url http://127.0.0.1:3002 --api-python .venv/Scripts/python.exe`: **6/6 đạt**, Edge headless157.0.4341.60. Kiểm chuyển chương/ghim snapshot, Back-Forward,503/retry cục bộ,409/404, snapshot đã mất và mobile390.
- `python -B web/tests/check_reader_browser.py --base-url http://127.0.0.1:3002 --production-url http://127.0.0.1:4173 --output-dir <temp-moi>`: **12/12 đạt**.
- `python -B web/tests/check_pr3_integration.py --base-url http://127.0.0.1:3002 --demo-url http://127.0.0.1:3001 --production-url http://127.0.0.1:4173 --output-dir <temp-moi>`: **6/6 đạt**. Fixture/catalog demo không lọt production; transport Reader không fallback demo.
- Kiểm liên kết Markdown P4 và việc bỏ templates/evidence: **đạt**. Không lưu log/ảnh/manifest kiểm thử trong thư mục tuần. OpenSpec strict validation đạt.

## Bàn giao và giới hạn

- C21 commit `4d04f66`; C35 commit `e9cd2d5`; C25/C29 có các commit `9e9c2f7`/`c473777`, tích hợp develop tại `2989158`. Đã push và mở [PR #12](https://github.com/w-w2504/UET.CS2046_6-G16-SmartLibAI/pull/12) vào develop; PR mở, không có xung đột tại thời điểm xác minh và chưa merge.
- Ngày18/11 người dùng đã tái tạo bundle20 bằng mã C11 và adapter đã kiểm nhận/build/load đạt; C14 không còn chờ artifact20. P3/C20/C24 vẫn cần giao catalog≥80 và vector tương ứng; C34/C24 giao lô150–200. Không lấy fixture để đạt số lượng corpus thật.
- C29 cần sách mẫu có toàn văn/nguồn được duyệt và dữ liệu chương/đoạn đúng3.1/9.4. Lô metadata nội bộ3.2 không đủ phạm vi để phát hành Reader.
- CLI build/validate/activate serving snapshot còn thiếu triển khai; adapter này không thay thế pipeline phát hành và không tự mở rộng C21 sang toàn bộ SPEC14.6. Chưa nghiệm thu dữ liệu thật, PyICU thật, chất lượng AI, VM/P95, phát hành snapshot hoặc toàn bộ tuần2.

- Coreach ngày18/11: đã mở lại phiên Edge riêng; người dùng tự đăng nhập. Đã đăng và reload xác minh báo cáo C05/C14/C18/C21/C25/C29/C35, gắn trực tiếp PR#12 qua phần liên kết. Mô tả giữ Nội dung/Output/Phụ thuộc; deadline/người phụ trách/contributors/trạng thái không đổi. C05/C18 giữ done; các task còn chờ đầu vào thật giữ đang làm. Bước Coreach đã hoàn tất; không tạo Markdown Coreach hoặc evidence ở local.

- Bổ sung sau lượt fixture18/11: C14 đạt thành phần bằng20 E5 thật tái tạo cục bộ. Round-trip20/20, self-query20/20 và query tiếng Việt thật khớp phép tính độc lập. Kết quả không thay nghiệm thu quy mô80/150, dữ liệu toàn văn, chất lượng AI hoặc snapshot phục vụ.
