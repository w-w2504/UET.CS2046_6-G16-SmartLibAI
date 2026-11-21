# C35 — danh mục150 sách chuẩn bị sinh bundle

Bản ghép21/11/2026 gồm20 sách mẫu +75 sách C24 cũ +55 sách vừa được biên tập và kiểm chứng độc lập. Được dựng bằng producer `classroom_batch` với130 dòng curation, rồi áp dụng55 catalog đã review; không sửa bộ95 cũ.

-150 sách/150 tác phẩm, không có ảnh hoặc toàn văn.
-150 nguồn `approved` cho demo/nội bộ:40 của20 mẫu và110 của55 sách mới.
-150 nguồn của75 sách C24 cũ vẫn `pending`; đợt này chưa kiểm lại để nâng nhãn.
- Giữ nguyên ID; sửa phụ đề hanoi:26 và bổ sung đồng tác giả museum:49 theo hồ sơ `../c35_reviewed55/review.json`.
- `quality_by_book_id.jsonl` phản ánh toàn corpus294; `embedding_candidates.jsonl` chỉ150 sách được chọn.55 sách mới có `reviewed_internal=true`; không coi nhãn đó là quyền công khai hoặc chất lượng AI đã đo.

## Chạy tiếp

Lô này cần opt-in demo vì75 sách còn pending. Từ root repo, với cache model đúng revision đã có và đích mới ngoài SNAPSHOT_ROOT:

```powershell
$env:PYTHONPATH = "$PWD\pipeline"
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -B -m ai_library.book_embeddings --classroom-demo --batch data/raw/c35_reviewed150 --output-dir data/demo/c35-150-moi/bundle --cache-dir "$env:USERPROFILE/.cache/huggingface/hub"
.\.venv\Scripts\python.exe -B -m ai_library.c11_bundle --classroom-demo --data-kind classroom_demo --batch data/raw/c35_reviewed150 --taxonomy data/raw/c35_reviewed150/taxonomy.json --bundle data/demo/c35-150-moi/bundle --output-dir data/demo/c35-150-moi/index --snapshot c35-demo150-moi
```

Đó là bước tiếp theo, chưa được tính là đã sinh vector/index150 ở đợt biên tập này. Không dùng dữ liệu demo thay snapshot public/Reader và không đổi pending còn lại để loader strict chấp nhận. Catalog294 nguồn và75 curation gốc giữ nguyên; lô55 và lô150 có phiên bản riêng.
