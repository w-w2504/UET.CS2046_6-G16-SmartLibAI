# C42 — Hai tác phẩm Reader đã kiểm nguồn cho localhost Việt Nam

Cha con nghĩa nặng (Hồ Biểu Chánh):10chương/880đoạn; Nửa chừng xuân (Khái Hưng):18mục/3421đoạn. Book/work/H/PID giữ nguyên P3, mỗi đoạn EPUB khớp JSONL. Giữ NOTICE/CC BY-SA, rawEPUB và parent source_manifest. review.json nêu phạm vi/quyền/URL/UTC/reviewerAI/hash; không giả người duyệt. P3 gốc vẫnpending.

Catalog có nguồn metadata/summary/fulltext được xét riêng. Với Nửa chừng xuân, nguồn tạp chí/bài nghiên cứu cũ vẫnpending, thêm nguồn biên tập dựa nguyên tác; mô tả mới chỉ giới thiệu phần mở đầu. Không dùng mô tả này thay vector289: Reader và Search là snapshot riêng.

Từ root repo, dùng Python đã cài API/pipeline/PyICU:

```powershell
$env:PYTHONPATH = "$PWD/pipeline;$PWD/api"
.\.venv\Scripts\python.exe -B -m ai_library.reader_snapshot --batch data/raw/p4_w03_reader2 --output-dir data/demo/p4-reader2-rebuild/snapshots/p4-c42-reader2-20261122 --snapshot p4-c42-reader2-20261122 --cldr-version 49.0
```

CLDR49.0 đã đọc thực từ ICU79.1 của môi trường build; máy khác phải dùng phiên bản CLDR đã xác minh của chính ICU đó. Không tự cấp lại ID hoặc sửa snapshot cũ. Gói hiện tại chỉ phục vụ localhost Việt Nam, không RAG/QA, không thay tiêu chí20toànvăn hoặc nghiệmthu toàn hệthống.
