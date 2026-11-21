# SmartLibAI Demo v1

Gói lớp học chứa catalog con, vector E5 và chỉ mục FAISS để trình diễn Semantic Search và thử nghiệm Recommendation. Tóm tắt do AI biên soạn dựa trên các URL đối chiếu trong catalog. Quyết định duyệt của lô 20 sách mẫu giữ nguyên. Các nguồn của phần mở rộng vẫn mang trạng thái `pending`.

## Gói bàn giao

| Thành phần | Đường dẫn trong gói |
| --- | --- |
| Catalog con và nguồn theo sách | `batch/catalog.jsonl` |
| Danh sách sách có embedding | `batch/embedding_candidates.jsonl` |
| QC toàn bộ 294 bản ghi, kể cả các sách chưa được chọn | `batch/quality_by_book_id.jsonl`, `batch/quality_summary.json` |
| Bundle C11 | `bundle/vectors.npy`, `bundle/mapping.jsonl`, `bundle/manifest.json` |
| Thành phần FAISS của P4 | `index/books.faiss`, `index/mapping.jsonl`, `index/index_manifest.json` |
| Snapshot Search | `snapshot/smartlibai-demo-v1/` gồm SQLite, FAISS, mapping và manifest |
| Kiểm thử API và snapshot | `verification.json` |
| Taxonomy và bảng tóm tắt có nguồn | `taxonomy.json`, `curation.tsv` |
| Thay đổi mã dành cho repo của nhóm | `smartlibai-demo-v1.patch` |

Giải nén `SmartLibAI-demo-v1.zip` vào `data/demo/smartlibai-demo-v1/`. Giữ nguyên tên thư mục snapshot. Các manifest liên kết SHA-256 của catalog con, taxonomy và artifact. Phạm vi trong manifest là `classroom_demo`, với quyền chưa xác minh được kê theo từng nguồn.

## P1 chạy Search trên localhost

Dùng bản mã có cấu hình `SMARTLIBAI_DEMO_SNAPSHOT`. Nếu nhóm đang dùng bản gốc tại `a4d26fb`, chạy `git apply --check <đường-dẫn-patch>` rồi `git apply <đường-dẫn-patch>` trên nhánh làm việc riêng để nhận mã demo. Từ thư mục gốc repo, dùng PowerShell với môi trường Python đã cài các phụ thuộc dự án và cache E5 đúng revision.

```powershell
$env:PYTHONPATH = 'api;pipeline'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:MODEL_ROOT = "$env:USERPROFILE\.cache\huggingface"
$env:SMARTLIBAI_DEMO_SNAPSHOT = (Resolve-Path 'data/demo/smartlibai-demo-v1/snapshot/smartlibai-demo-v1').Path
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

`CLASSROOM_DEMO_SNAPSHOT` vẫn dùng được khi biến mới chưa được thiết lập. Khi cả hai được thiết lập, biến mới được ưu tiên.

Nếu giải nén gói sang vị trí khác, dùng đường dẫn thư mục snapshot thực tế. `MODEL_ROOT` là thư mục chứa `hub`. Đợi Uvicorn báo hoàn tất startup để E5 được nạp trước lượt tìm đầu. Trong terminal web riêng, chạy `npm run dev` từ `web/` và mở trang `/search`. Demo HTTP sử dụng cùng contract `POST /api/v1/search` và bộ lọc `GET /api/v1/facets`. Dùng terminal sạch cho phiên chạy thông thường.

## P2 dùng lõi Recommendation

Nạp bundle và batch cùng phiên bản bằng `load_c11_bundle(..., classroom_demo=True)` và `load_demo_books(...)`. Nạp index với `load_book_index(..., classroom_demo=True)`. Từ các sách cùng ID trong batch, tạo `BookMetadata` và truyền `NumpyBookScorer(index.book_ids, index.get_vector)` vào `RecommendationRanker`. Dùng SHA-256 của bundle manifest làm `dataset_id`. Lõi C13 đã được thử với seed thật. Endpoint `/recommend` của nhánh hiện tại vẫn cần nối C13 ở lớp HTTP.

## P4 tái tạo một phiên bản

Chạy từ repo root với `PYTHONPATH=pipeline`. Mỗi lượt chọn đường dẫn mới dưới kho nội bộ. Dùng cùng `snapshot_id` cho index và tên thư mục snapshot.

```powershell
$env:PYTHONPATH = 'pipeline'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$py = '.\.venv\Scripts\python.exe'
$out = 'data/demo/smartlibai-demo-v1-rebuild'
& $py -m ai_library.classroom_batch --classroom-demo --count 95 --output-dir "$out/batch"
& $py -m ai_library.book_embeddings --classroom-demo --batch "$out/batch" --output-dir "$out/bundle"
& $py -m ai_library.c11_bundle --classroom-demo --data-kind classroom_demo --batch "$out/batch" --bundle "$out/bundle" --output-dir "$out/index" --snapshot smartlibai-demo-v1
& $py -m ai_library.classroom_snapshot --classroom-demo --batch "$out/batch" --bundle "$out/bundle" --index "$out/index" --output-dir "$out/snapshot/smartlibai-demo-v1" --threshold 0.75
```

Nếu repo có cấu hình `SNAPSHOT_ROOT` riêng, giữ các thư mục demo bên ngoài cây đó. Các API đọc nội dung và RAG tiếp tục cần snapshot phục vụ đúng hợp đồng của chúng.

## Phạm vi nghiệm thu

Mốc 80 đạt trên corpus sách thật dùng trong lớp. Bộ 95 kiểm thử thêm độ ổn định của pipeline và minh họa truy vấn. Các truy vấn kiểm tra được chọn có mục tiêu. Với sách ngoài corpus, Search có thể trả sách gần nghĩa và vẫn báo `ok`. Nếu thiếu PyICU, danh sách tác giả của demo dùng thứ tự Unicode dự phòng. Trước khi phát hành công khai, cần có quyết định quyền thực tế cho nguồn sẽ dùng, rồi tạo snapshot mới theo luồng phục vụ đã duyệt.


### Dựng lại snapshot từ gói bàn giao

Từ repo root, dùng catalog, taxonomy và bundle có sẵn trong gói để dựng lại index và SQLite mà không cần chạy encoder cho 95 sách lần nữa. Chọn thư mục đầu ra mới.

```powershell
$env:PYTHONPATH = 'pipeline'
$py = '.\.venv\Scripts\python.exe'
$demo = 'data/demo/smartlibai-demo-v1'
$out = 'data/demo/smartlibai-demo-v1-from-bundle'
& $py -m ai_library.c11_bundle --classroom-demo --data-kind classroom_demo --batch "$demo/batch" --taxonomy "$demo/taxonomy.json" --bundle "$demo/bundle" --output-dir "$out/index" --snapshot smartlibai-demo-v1
& $py -m ai_library.classroom_snapshot --classroom-demo --batch "$demo/batch" --taxonomy "$demo/taxonomy.json" --bundle "$demo/bundle" --index "$out/index" --output-dir "$out/snapshot/smartlibai-demo-v1" --threshold 0.75
```

Các module, cờ CLI và giá trị `data_kind=classroom_demo` giữ tên nội bộ để tương thích với P2/P4.
