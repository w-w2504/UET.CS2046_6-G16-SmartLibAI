# C35 — danh mục150 sách đã tạo bundle và FAISS bản2

Bản ghép21/11/2026 gồm20 sách mẫu +75 sách C24 cũ +55 sách vừa được biên tập và kiểm chứng độc lập. Được dựng bằng producer `classroom_batch` với130 dòng curation, rồi áp dụng55 catalog đã review; không sửa bộ95 cũ.

-150 sách/150 tác phẩm, không có ảnh hoặc toàn văn.
-150 nguồn `approved` cho demo/nội bộ:40 của20 mẫu và110 của55 sách mới.
-150 nguồn của75 sách C24 cũ vẫn `pending`; đợt này chưa kiểm lại để nâng nhãn.
- Giữ nguyên ID; sửa phụ đề hanoi:26 và bổ sung đồng tác giả museum:49 theo hồ sơ `../c35_reviewed55/review.json`.
- `quality_by_book_id.jsonl` phản ánh toàn corpus294; `embedding_candidates.jsonl` chỉ150 sách được chọn.55 sách mới có `reviewed_internal=true`; không coi nhãn đó là quyền công khai hoặc chất lượng AI đã đo.

## Tái tạo ở đích mới

Lô này cần opt-in demo vì75 sách còn pending. Từ root repo, với cache model đúng revision đã có và đích mới ngoài SNAPSHOT_ROOT:

```powershell
$env:PYTHONPATH = "$PWD\pipeline"
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -B -m ai_library.book_embeddings --classroom-demo --batch data/raw/c35_reviewed150 --output-dir data/demo/c35-150-moi/bundle --cache-dir "$env:USERPROFILE/.cache/huggingface/hub"
.\.venv\Scripts\python.exe -B -m ai_library.c11_bundle --classroom-demo --data-kind classroom_demo --batch data/raw/c35_reviewed150 --taxonomy data/taxonomy.json --bundle data/demo/c35-150-moi/bundle --output-dir data/demo/c35-150-moi/index --snapshot c35-demo150-moi
```

Không dùng dữ liệu demo thay snapshot public/Reader và không đổi pending còn lại để loader strict chấp nhận. Catalog294 nguồn và75 curation gốc giữ nguyên; lô55 và lô150 có phiên bản riêng.

## Kết quả C35

Ngày21/11 đã tạo bundle150 thật và hai FAISS ở đích mới;150/150 round-trip/self-query,3query Việt khớp NumPy,64test adapter/index/refresh/demo đạt. Gói `c35-demo150-handoff-20261121.zip` đã đính kèm Coreach C35/PR17, SHA256 `7cbaf8f0ccc48c6956871027f861352ac062fc2f6f32edc8cb0f8f1cbb34cdf7`; có README cho P1/P2 dùng trực tiếp không encode lại. C35 Done trong phạm vi demo/nội bộ, chưa đo chất lượng AI hoặc xác nhận P1/P2 tích hợp.

Producer C11 cố định taxonomy tại `data/taxonomy.json`. Bản taxonomy trong batch có cùng nội dung JSON nhưng khác byte xuống dòng; dùng đúng tệp có hash manifest, không thay bằng bản JSON tương đương. ZIP có taxonomy đúng byte ở thư mục gốc. Khi dựng lại từ ZIP dùng `--taxonomy <thu-muc-giai-nen>/taxonomy.json`.
