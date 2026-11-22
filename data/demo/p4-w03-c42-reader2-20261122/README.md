# C42 — Reader2: bản bàn giao localhost tại Việt Nam

Hai tác phẩm/28chương/4301đoạn; snapshot p4-c42-reader2-20261122-r1. Nguồn và quyền chi tiết ở data/raw/p4_w03_reader2/README.md, NOTICE.md và review.json. Giữ nguyên bản P3 pending, không dùng approvalfixture. Không RAG/QA/phát hành toàn cầu.

Tất cả dữ liệu cần thiết nằm trong Git; không cần ZIP riêng, không phải chạy lại encoder. Kiểm nhận từ root:
`python -B pipeline/scripts/verify_p4_week3.py --component reader`

Terminal API từ root repo, PowerShell (chỉ cấu hình môi trường riêng):

```powershell
$r = (Resolve-Path 'data/demo/p4-w03-c42-reader2-20261122').Path
$env:PYTHONPATH = "$PWD/api;$PWD/pipeline"
$env:SNAPSHOT_ROOT = "$r/snapshots"
$env:CONTROL_ROOT = "$r/control-local"
New-Item -ItemType Directory -Force $env:CONTROL_ROOT | Out-Null
$activeJson = @{active_snapshot_id='p4-c42-reader2-20261122-r1'} | ConvertTo-Json
[IO.File]::WriteAllText("$env:CONTROL_ROOT/active.json", $activeJson, [Text.UTF8Encoding]::new($false))
Remove-Item Env:SMARTLIBAI_DEMO_SNAPSHOT -ErrorAction SilentlyContinue
Remove-Item Env:CLASSROOM_DEMO_SNAPSHOT -ErrorAction SilentlyContinue
$env:GEMINI_API_KEY = ''
.\.venv\Scripts\python.exe -B -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Terminal khác: cd web, npm run dev. Mở /explore, bật chỉcótoànvăn, chọn sách→Đọc. Link trực tiếp /read/SLB_B0001?snapshot_id=p4-c42-reader2-20261122-r1 hoặc /read/B_a00f6ca8-6bad-4214-b8fd-20871232352b?snapshot_id=p4-c42-reader2-20261122-r1. Dùng đúng cổng Vite in ra. Không dùng reader_fixture. Control tạo riêng không đưa Git; không ghi active của bộ khác.

Snapshot đã có SQLite, không cần build lại. Nếu tái tạo, dùng batch/registry đã đóng băng và CLI reader_snapshot với snapshotID/đích mới; giữ đúng ICU/CLDR đã xác minh cho lần build. Snapshot này đóng băng khóa sort từ ICU79.1/CLDR49.0; không tự viết lại khóa của bản cũ.
