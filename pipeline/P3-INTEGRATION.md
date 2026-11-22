# SmartLibAI P3 — chạy classroom demo từ một Git checkout

## Dữ liệu đã có trong Git scope

Sau khi thay đổi P3 được commit và push, thành viên clone/pull repository sẽ có đủ
catalog, vectors, FAISS, SQLite snapshot v4, baseline v1 và Reader. Không tải ZIP dữ liệu
riêng. Lượt chuẩn bị này chưa stage/commit/push; cần hoàn tất bước Git đó trước khi
người khác clone được các file mới. Python dependencies và model E5 vẫn cần chuẩn bị.

| Thành phần | Đường dẫn từ repo root | Số lượng |
| --- | --- | --- |
| Catalog đầy đủ | `data/raw/p3_v4/catalog.jsonl` | 294 metadata |
| Catalog Search | `data/raw/p3_v4/search/catalog.jsonl` | 289 sách đạt QC |
| QC, taxonomy, integration manifest | `data/raw/p3_v4/` | Hồ sơ, schema 2 |
| E5 bundle | `data/demo/smartlibai-fasttrack/smartlibai-demo-v4/bundle/` | 289 x 384 float32, L2 |
| FAISS component | `data/demo/smartlibai-fasttrack/smartlibai-demo-v4/index/` | 289 vectors/mapping |
| Snapshot API v4 | `data/demo/smartlibai-fasttrack/smartlibai-demo-v4/snapshot/smartlibai-demo-v4/` | 289 sách |
| Snapshot API v1 | `data/demo/smartlibai-demo-v1/snapshot/smartlibai-demo-v1/` | 95 sách |
| Reader JSONL và ID | `data/raw/p3_reader/` | 28 mục đọc, 4301 đoạn |
| EPUB gốc | `data/raw/p3_reader/raw/` | 2 EPUB bảo toàn bytes |
| Ghi công và điều kiện nguồn | `data/raw/p3_reader/NOTICE.md` | URL/version/license notes |

Năm sách chưa đủ căn cứ nội dung giữ ngoài Search; không viết summary mới cho đủ số.
Catalog 294 dùng cho import metadata staging. `/api/v1/books` với snapshot v4 trả
289; v1 vẫn trả 95. Không sửa ID, nội dung sách, vector hay source rights.

Model `intfloat/multilingual-e5-small`, revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98`, 384 chiều, mean attention-mask pooling,
L2. Query dùng prefix `query: `, passage dùng `passage: `.
Không chạy lại pipeline embedding sách. Bundle v4 kế thừa vector v3 đã có.

## Môi trường Windows PowerShell

Từ repository root, dùng Python 3.11+ (môi trường kiểm thử hiện tại dùng 3.13):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements-p3-demo.txt
.\.venv\Scripts\python.exe -c 'import sys; print(sys.executable)'
```

Có thể dùng Python đã cài dependencies và truyền `-Python` cho launcher. Nếu exe không
khởi chạy được, đó là vấn đề môi trường Python, không phải dữ liệu. PyICU chỉ cần cho
một số kiểm thử collation khác, không bắt buộc cho verifier P3 này.

## Chuẩn bị model E5 một lần

Kiểm tra dữ liệu/vector/FAISS không cần model. Search ngữ nghĩa thật cần E5 đúng revision.
Dùng cache hiện có hoặc tải model một lần (không tính lại embedding sách):

```powershell
.\.venv\Scripts\python.exe -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id="intfloat/multilingual-e5-small", revision="fd1525a9fd15316a2d503bf26ab031a61d056e98", cache_dir="models/hub", allow_patterns=["*.json", "*.safetensors", "sentencepiece.bpe.model"])'
```

Với lệnh trên, `MODEL_ROOT` là `./models` vì encoder dùng thư mục `MODEL_ROOT/hub`.
Launcher cũng hỗ trợ cache mặc định `$env:USERPROFILE/.cache/huggingface`.
Model cache/weights không đưa Git. Chỉ model và dependencies cần tải riêng; không có
artifact sách/Reader nào cần tải ngoài repo.

## Chạy backend và frontend

```powershell
.\pipeline\start-p3-demo.ps1 -CheckOnly
.\pipeline\start-p3-demo.ps1 -Python ./.venv/Scripts/python.exe -ModelRoot ./models -Warmup
```

`-CheckOnly` kiểm tra đúng snapshot và SHA-256 mà không mở cổng hoặc nạp Python/model.
`-Warmup` nạp E5, mã hóa một query và mở Uvicorn trong cùng process, tránh đưa request
đầu tiên vào lúc model còn đang nạp. Chờ thông báo model warmed và startup hoàn tất.
Kết quả sau warm-up không đại diện độ trễ khởi động lạnh. Không đổi API/deadline.
Nếu thiếu cache đúng revision, offline load sẽ dừng; chuẩn bị cache trước.

Launcher chọn snapshot dưới chính repository, không yêu cầu `-DataRoot` hay ZIP.
Tham số `-DataRoot` chỉ là tùy chọn cho kiểm thử. Biến môi trường được phục hồi khi dừng.
Cấu hình thủ công tương đương:

```powershell
$env:PYTHONPATH = 'api;pipeline'
$env:SMARTLIBAI_DEMO_SNAPSHOT = (Resolve-Path 'data/demo/smartlibai-fasttrack/smartlibai-demo-v4/snapshot/smartlibai-demo-v4').Path
$env:MODEL_ROOT = (Resolve-Path './models').Path
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Đổi SMARTLIBAI_DEMO_SNAPSHOT sang `data/demo/smartlibai-demo-v1/snapshot/smartlibai-demo-v1`
để dùng v1, không đổi tên hoặc ghi đè snapshot. Để chạy frontend, mở terminal khác:

```powershell
Set-Location web
npm ci
npm run dev
```

Mở `http://localhost:3000/search?snapshot_id=smartlibai-demo-v4` hoặc
`http://localhost:3000/explore?snapshot_id=smartlibai-demo-v4`.
`dev:demo` dùng fixture frontend riêng. Nếu Windows chặn script unsigned, dùng host
PowerShell được môi trường cho phép; không tự thay policy hệ thống.

## Import catalog đủ 294 metadata

```powershell
$env:PYTHONPATH = 'pipeline'
.\.venv\Scripts\python.exe -m ai_library.cli import --metadata-only --batch data/raw/p3_v4 --taxonomy data/raw/p3_v4/taxonomy.json --sqlite data/reports/catalog-294-local.sqlite --snapshot p3-catalog-v4-staging
```

Chọn tên SQLite mới nếu file đã có. Không gán catalog staging 294 thành snapshot Search.

## Verifier theo component

Manifest schema 2 chỉ ràng buộc file trong Git scope, không chứa ZIP/archive bắt buộc:

| Component | Nhóm manifest | File dữ liệu | Kiểm tra |
| --- | --- | ---: | --- |
| `search` | `search_v4` | 17 | Catalog, bundle, index, SQLite, mapping, hash và fixture query |
| `reader` | `reader_staging` | 7 | JSONL, registry, nguồn, taxonomy và hai catalog đối chiếu |
| `reader-sources` | `reader_provenance` | 4 | Hai EPUB gốc, source manifest và NOTICE |
| `baseline` | `regression_v1` | 4 | Snapshot v1 nguyên vẹn và API 95 sách |

Chỉ đọc component được chọn. EPUB là dữ liệu nguồn được lưu Git; Reader JSONL runtime
không cần mở EPUB. `--component all` kiểm tra cả bốn nhóm; Reader API được bật riêng bằng
`--api-smoke`. Thư mục root chỉ định phải chứa dữ liệu, không fallback về máy tác giả.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OMP_NUM_THREADS = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Chỉ bật khi sandbox Windows chặn socket kỹ thuật của ASGI TestClient:
$env:SMARTLIB_TEST_NO_SOCKETS = '1'
.\.venv\Scripts\python.exe pipeline/scripts/verify_p3_integration.py --component search --output data/reports/search-data-new.json
.\.venv\Scripts\python.exe pipeline/scripts/verify_p3_integration.py --component search --api-smoke --semantic-smoke --model-root ./models --output data/reports/search-api-new.json
.\.venv\Scripts\python.exe pipeline/scripts/p3_reader_check.py --output data/reports/reader-api-new.json
.\.venv\Scripts\python.exe pipeline/scripts/verify_p3_integration.py --component reader-sources --output data/reports/reader-sources-new.json
.\.venv\Scripts\python.exe pipeline/scripts/verify_p3_integration.py --component baseline --output data/reports/baseline-new.json
```

Output phải là đường dẫn mới; verifier không ghi đè. Search kiểm tra import 294, 20 bản
mẫu, 289 vector/mapping/L2, SQLite integrity/FK, hashes, top-5 so dot product cho từng
vector. API smoke kiểm tra 289 Book Detail và năm ID ngoài Search trả 404; semantic
smoke kiểm tra 17 query/genre filter theo fixture sau khi E5 warm-up.

## Mô phỏng checkout trước commit

Khi đang chuẩn bị P3 và index Git thật chưa staged:

```powershell
.\.venv\Scripts\python.exe pipeline/scripts/check_p3_checkout.py --model-root ./models --output-dir data/reports/p3-clean-checkout-new
```

Script chọn đúng tracked tree và tập file P3 dự kiến commit đang hiện với Git, từ chối
untracked ngoài scope hoặc file bắt buộc còn bị ignore. Nó sao chép tập đó vào thư mục
mới ngoài repo, xác minh danh sách file và mọi hash trước/sau kiểm thử. Các tiến trình
Python isolated bị chặn đọc code/dữ liệu repo gốc; chỉ dùng dependencies đã cài và cache
model được khai báo. Không sao chép cache, ZIP, backup hoặc artifact ignored.
Đây là mô phỏng filesystem của nội dung commit dự kiến, không phải clone Git thực sự.
Script không stage, commit, sửa refs hoặc tạo PR. Sau commit, verifier thông thường
vẫn dùng được; công cụ mô phỏng này dành cho bước pre-commit có diff index rỗng.

`result.json`, `inventory.json`, `stage-paths.txt`, `stage-plan.ps1` và report từng
component được ghi ở output-dir mới. `stage-plan.ps1` chỉ là lệnh đề xuất, chưa thực thi.

`.gitattributes` đặt `-text` cho các input/artifact có checksum, gồm 20 bản gốc. Vì vậy
Git không đổi LF/CRLF khi clone trên Windows có core.autocrlf=true; không sửa hash để
che chuyển đổi dòng. Tất cả bytes sách và artifacts hiện có được bảo toàn.

## P4 nhập Reader

| Tác phẩm | book_id | Mục đọc | Đoạn |
| --- | --- | ---: | ---: |
| Cha con nghĩa nặng | `SLB_B0001` | 10 chương | 880 |
| Nửa chừng xuân | `B_a00f6ca8-6bad-4214-b8fd-20871232352b` | Mở đầu + 17 chương | 3421 |
| Tổng | | 28 | 4301 |

book_id/work_id/title/author khớp catalog 294 và Search 289. Dùng nguyên chapter_id và
paragraph_id từ registry. Ghép đoạn bằng hai LF; offset Unicode code point nửa mở
`[char_start,char_end)`. Không tạo lại ID hoặc đọc EPUB qua network khi import.

Schema/API Reader đã có trên nhánh hiện tại. P4 nối JSONL vào quy trình build snapshot,
ghi các bảng chapters/paragraphs cùng snapshot/book/source keys, cập nhật counts/hashes,
kiểm tra danh sách chương/nội dung/offset. C10 thường validate chương, chỉ metadata-only
mới ghi SQLite; không coi CLI đó là builder Reader production hoàn chỉnh.

Hai nguồn fulltext vẫn pending, fulltext_approved=false. Staging script dùng SQLite tạm
với nhãn approval fixture để thử contract, không ghi approval về nguồn thật. Git tracking
không bật production Reader. Chưa tuyên bố frontend Reader hoàn thiện.
NOTICE.md ghi tác giả, nguồn/phien bản, ghi công cộng đồng Wikisource, điều kiện giấy phép
và thao tác chuyển đổi của P3; không cấp lại giấy phép nguyên tác theo license code.

## File giữ local và kết quả kiểm thử

ZIP r2, ZIP gốc, report/backup, expanded-catalog SQLite, Reader cũ, v1 bundle/index lịch sử
và artifact trung gian tiếp tục ignored. Không cần gửi chúng cho thành viên để chạy demo.
Index component và snapshot giữ cấu trúc hiện có; FAISS/mapping trùng bytes là hai view
contract cần kiểm chứng, không tạo thêm bản sao mới. Git dùng chung blob cho nội dung
trùng hệt; không đưa thêm ZIP chứa lại chúng vào scope commit.

Kết quả mới nằm ở output-dir của check_p3_checkout và báo cáo single-repo trong
`data/reports/`; không tự nhận các kết quả cũ (164 regression, frontend build) là của
lượt mới. Không chạy lại embedding hoặc full regression khi chỉ đổi công cụ và tracking.
Thông tin remote phải lấy từ fetch/ls-remote mới, không dùng cached ref để kết luận.
