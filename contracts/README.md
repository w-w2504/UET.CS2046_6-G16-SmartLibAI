# Hợp đồng API SmartLibAI

FastAPI và Pydantic định nghĩa schema cho 10 endpoint. Các route hiện có vẫn là khung nghiệp vụ. Việc tra snapshot, kiểm tra nhãn và tác giả theo catalog, đối chiếu seed/exclude theo tác phẩm và đếm token đúng model thuộc service tương ứng.

| Endpoint | Đầu vào đáng chú ý |
| --- | --- |
| GET /books | offset mặc định 0, limit 1–20 mặc định 20, filters ở query |
| GET /books/{id}, /facets | snapshot_id tùy chọn |
| GET /books/{id}/similar | k 1–10 mặc định 5, filters ở query |
| GET /books/{id}/chapters | snapshot_id tùy chọn |
| GET /chapters/{id} | snapshot_id và chunk_id tùy chọn |
| POST /search | q 1–500 ký tự, k 1–20 mặc định 10 |
| POST /recommend | 1–3 seed, tối đa 300 ID loại trừ duy nhất, k 1–10 mặc định 5 |
| POST /qa | book_id, question 1–1000 ký tự |
| GET /health | Không query hoặc body |

Chỉ authors và genres được lặp ở query. Endpoint dữ liệu nhận snapshot_id tùy chọn. Reader đặt text và paragraphs bên trong chapter, phù hợp cấu trúc client hiện dùng.

## Seed chưa đủ quyền trong Recommendation/Similar

Ngày 22/11/2026, Vân/P02 xác nhận hành vi cho sách tồn tại nhưng chưa có đủ nguồn `metadata` và `summary` với `rights_status=approved` trong snapshot của request: `POST /recommend` trả **422 invalid_input**, field `seed_book_ids`; `GET /books/{id}/similar` trả **422 invalid_input**, field `id`. Không tự thay seed bằng ấn bản khác. Đây là xác nhận của P02, không phải biên bản phê duyệt toàn nhóm. Chi tiết eligibility và triển khai tại [C17](../documents/C17.md).

Seed không tồn tại giữ quy ước hiện có: POST trả 422 `invalid_input`, Similar trả 404 `resource_not_found`. Exclude được kiểm tồn tại và xung đột work; không áp dụng điều kiện quyền của seed cho exclude.

## Sinh và kiểm tra

Từ thư mục gốc, dùng Python có các gói trong api/requirements-contract.txt và đặt PYTHONPATH=api. Cần Node.js có ICU tiếng Việt để tạo fixture facets theo vi-VN, phân biệt dấu, không phân biệt hoa/thường và giữ dấu câu.

```text
python api/scripts/build_contract_fixtures.py
python api/scripts/export_openapi.py
python api/scripts/export_openapi.py --check
python -m pytest api/tests
npm ci --prefix web
npm run contract:types --prefix web
npm run build --prefix web
node web/scripts/check-demo.mjs
```

OpenAPI xuất từ FastAPI. Bản contracts/openapi.json bổ sung ví dụ nội bộ từ manifest, trong khi Swagger của dịch vụ dùng schema FastAPI và không kèm dữ liệu mock nội bộ. Type web sinh từ artifact, với alias giữ các tên import hiện có.

Manifest ghi scenario_id, operation, đầu vào, HTTP status, header, payload và nguồn. Với đường dẫn chứa {id}, trường id trong query của manifest dùng để điền path khi replay. Fixture P3 chỉ dùng thử nghiệm nội bộ và giữ sách ở trạng thái chỉ metadata. Fixture Reader/QA dùng văn bản P4 hiện có và snapshot riêng. Các phản hồi mock không được dùng để đánh giá chất lượng Search/RAG hoặc phát hành như dữ liệu thật.

Ba phản hồi QA dùng trong frontend được sinh từ cùng manifest. Chế độ demo chỉ phát lại các phản hồi đó cho sách và snapshot Reader mẫu khi chọn ca QA tương ứng. CI kiểm tra tệp sinh cùng OpenAPI và type. Dữ liệu demo C02 có thể hiển thị nguồn nội bộ ngay trong chế độ phát triển; fixture BookDetail cho contract công khai chỉ mang các nguồn đủ điều kiện.

Hồi quy Reader dùng Playwright với Microsoft Edge, hai Vite server dev/preview và thư mục bằng chứng riêng. Khi thư mục dự án có chapters.jsonl local, chạy hồi quy trên bản sao chỉ gồm catalog và taxonomy đã quản lý trong Git. Đường dẫn và tùy chọn chạy được mô tả trong web/tests/check_reader_browser.py.
