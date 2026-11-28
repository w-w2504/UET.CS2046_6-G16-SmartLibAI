# C30/C32 — Thông báo tiến độ đánh giá Semantic Search

Tài liệu ghi lại bộ truy vấn C30, baseline BM25 C32 và kết quả tạo pool để nhóm có thể kiểm tra và chạy lại bài đánh giá Semantic Search.

## Phần đã thực hiện

### Bộ truy vấn C30

- Đã chuẩn bị 50 truy vấn tiếng Việt: 20 truy vấn `dev` và 30 truy vấn `test`, đúng yêu cầu tại SPEC 15.1 và TEAM-04. Có 26 truy vấn mô tả nhu cầu, 14 truy vấn ngắn và 10 truy vấn có bộ lọc.
- 48 truy vấn dựa trên ấn bản có ref trong `data/raw/c24_classroom/curation.tsv`; hai truy vấn còn lại dùng sách mẫu `SLB_B0007` và `SLB_B0018`. Mỗi truy vấn có ba candidate ban đầu, tổng cộng 150 cặp query–book. Đây là gợi ý ban đầu, chưa phải pool top-20 cuối theo SPEC.
- Trong 150 candidate ban đầu có 50 gợi ý `proposed_relevance=0`, 50 gợi ý mức 1 và 50 gợi ý mức 2. Các mức này do heuristic metadata tạo ra, chưa được người chấm xác nhận.
- Catalog C20/C34 dùng ở lượt chuẩn bị ban đầu có 294 sách: 20 sách có trạng thái nguồn `approved` và 274 sách `pending`. Trong CSV, 48 anchor C24 vẫn `pending`; hai anchor sách mẫu là `approved`. Trên 150 dòng candidate ban đầu, trạng thái nguồn là 32 dòng `approved` và 118 dòng `pending`. Các trạng thái này được giữ nguyên; URL là căn cứ để kiểm tra nguồn, không phải xác nhận quyền phát hành.

### Baseline BM25 C32

- Baseline nội bộ được triển khai trong `pipeline/ai_library/bm25_search.py`, với công cụ chạy tại `pipeline/ai_library/search_eval.py`; đây không phải API phục vụ người dùng.
- BM25 dùng biểu diễn sách năm dòng theo SPEC 10.4: title, authors, tên hiển thị genres, tên hiển thị topics và summary. Mã sắp xếp taxonomy theo code; giữ dòng rỗng; chuẩn hóa NFC và khoảng trắng từng dòng. Tokenizer dùng NFC + casefold, tách theo dãy chữ/số Unicode, giữ dấu tiếng Việt và không loại stopword.
- Cấu hình là `k1=1.5`, `b=0.75`, `IDF=ln(1+(N-df+0.5)/(df+0.5))`. Bộ lọc authors/genres dùng OR trong từng danh sách và AND giữa các bộ lọc; lọc được áp dụng trước khi lấy top-20. Kết quả xếp theo điểm giảm dần, hòa điểm theo `book_id` tăng dần. Mỗi ấn bản được giữ riêng, không gộp theo `work_id`.
- Baseline đã chạy cho 50 truy vấn và tạo 1.000 dòng top-20 trong `search_eval_bm25_top20.csv`. Lượt chạy dùng catalog `data/raw/c20_c34/catalog.jsonl` gồm 294 sách cùng taxonomy hiện có; CSV kết quả ghi `source_corpus_id` và SHA-256 của catalog/taxonomy để truy vết.
- Snapshot E5 `p4-w03-c38-reviewed-r8-20261122` gồm 289 sách và 289 vector. Helper eligibility của Search xác nhận 286 sách có cả metadata và summary `approved` trong đúng snapshot. Cả hai chế độ xếp hạng của công cụ C30 dùng encoder `intfloat/multilingual-e5-small` đúng revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`.
- Output BM25 cũ dùng corpus `catalog-c20-c34-e37d367e9cae` gồm 294 sách, chưa áp dụng eligibility của r8. Công cụ tạo pool chạy lại BM25 trên r8 và lưu kết quả cùng E5 vào một thư mục riêng.
- Các `proposed_relevance` được giữ lại khi candidate gợi ý xuất hiện trong top-20 BM25. Chúng là gợi ý heuristic từ metadata, không phải nhãn người chấm và chưa được dùng để tính metric.

### Pool E5/BM25 trên snapshot r8

- [Pool dùng để chấm](c30_pool_r8_faiss_check/pool.csv) có 1.530 cặp `(query_id, book_id)` duy nhất, gồm 611 cặp `dev` và 919 cặp `test`. Công cụ gộp các sách trong top-20 của E5 và BM25 cho từng truy vấn. Cả hai dùng cùng snapshot, bộ lọc và tập 286 sách đủ điều kiện.
- Đã đối chiếu trên Ubuntu qua WSL 2. [Manifest](c30_pool_r8_faiss_check/manifest.json) ghi `faiss_comparison.status=matched`: NumPy và FAISS khớp thứ tự top-20 trên cả 50 truy vấn.
- Nhóm giữ nguyên `DEV-018`, `TEST-014` và `TEST-017` cùng split của các câu này. Ba sách làm căn cứ đang `pending` trong r8 đã bị loại khỏi xếp hạng.

### Trạng thái C30

- **C30 — Done theo phạm vi bàn giao nội bộ.** Lượt bàn giao gồm công cụ, pool 1.530 cặp và manifest ghi NumPy khớp thứ tự top-20 với FAISS trên 50/50 truy vấn.
- Nhóm đã chấm đủ 611 cặp `dev` và 919 cặp `test`. Đã đối chiếu toàn bộ nhãn với pool theo `(split, query_id, book_id)` và xác nhận mỗi cặp có đúng một nhãn `0–2`. Nhãn được gộp vào CSV nội bộ với các cột `split`, `query_id`, `book_id` và `relevance_label` để C39 có thể đọc.
- Lượt bàn giao nội bộ bỏ qua chấm chéo độc lập theo quyết định của người phụ trách C30. Trạng thái này chỉ ghi nhận phần bàn giao nội bộ.

## Phần tiếp theo

C39 sẽ dùng tập `dev` để chọn `search_threshold`, rồi dùng tập `test` để đo nDCG@10 và Precision@5 theo SPEC 15.1–15.2. Hiện chưa chọn ngưỡng hoặc tính các chỉ số này.

## Chạy baseline BM25

Từ thư mục `pipeline` trong PowerShell:

```powershell
python -m ai_library.search_eval --overwrite
```

`--overwrite` cần thiết khi muốn tạo lại output mặc định đã tồn tại. Công cụ không gọi API, không tạo snapshot và không thay đổi trạng thái quyền dữ liệu.

## Tạo pool C30 trên r8

Chạy từ thư mục gốc repo. Cài dependency trong `pipeline/requirements-p3-demo.txt` và chuẩn bị cache E5 đúng revision như hướng dẫn P3. Tham số `--model-root` nhận thư mục chứa `hub`. Ví dụ PowerShell bên dưới dùng môi trường `api/.venv`.

```powershell
.\api\.venv\Scripts\python.exe -B pipeline/scripts/build_c30_pool.py --check-inputs
.\api\.venv\Scripts\python.exe -B pipeline/scripts/build_c30_pool.py --model-root .\models --output-dir data/evaluation/search/c30_pool_r8_draft
```

FAISS là chế độ mặc định theo SPEC 10.4. Khi máy không nạp được FAISS, có thể tạo bản nháp đánh giá nội bộ bằng NumPy. Công cụ đối chiếu hash và từng dòng của hai mapping trước khi dùng vector từ `bundle/vectors.npy`. Điểm E5 là tích vô hướng `float32` của vector đã chuẩn hóa L2. Thứ tự cộng trong NumPy và FAISS có thể khác nhau, nên cần đối chiếu top-20 trước khi dùng kết quả làm bằng chứng nghiệm thu.

```powershell
.\api\.venv\Scripts\python.exe -B pipeline/scripts/build_c30_pool.py --check-inputs --ranker numpy
.\api\.venv\Scripts\python.exe -B pipeline/scripts/build_c30_pool.py --ranker numpy --compare-faiss --model-root .\models --output-dir data/evaluation/search/c30_pool_r8_numpy_draft
```

`--compare-faiss` so thứ tự top-20 cho cả 50 truy vấn bằng cùng vector query nếu nạp được FAISS. Manifest ghi danh sách truy vấn có khác biệt và thứ tự của cả hai phương pháp xếp hạng E5. Nếu FAISS bị chặn, bản nháp vẫn được tạo, với trạng thái `unavailable` và lý do. Bỏ `--compare-faiss` để chạy NumPy mà không thử nạp FAISS.

Để chạy lại lượt đối chiếu r8, dùng môi trường Python 3.12 trên Ubuntu qua WSL 2 và chọn thư mục đầu ra mới:

```bash
python -B pipeline/scripts/build_c30_pool.py --ranker numpy --compare-faiss --model-root ./models --output-dir data/evaluation/search/c30_pool_r8_faiss_rerun
```

`--check-inputs` không nạp model. Lệnh tạo pool yêu cầu thư mục đích chưa tồn tại. `pool.csv` có một dòng cho mỗi cặp truy vấn và ấn bản, với hạng và điểm riêng của E5 và BM25. `manifest.json` ghi phương thức xếp hạng E5, hash đầu vào và CSV, revision E5, phiên bản thư viện và số ứng viên theo truy vấn.

### Chấm nhãn và review chéo

1. Dùng pool và manifest đã đối chiếu làm mốc. Ghi nhãn trong tệp riêng theo khóa `(query_id, book_id)` để giữ hash của bản gốc.
2. Người chấm đọc truy vấn, bộ lọc và metadata hoặc nguồn của từng ấn bản. Gán `0` nếu không phù hợp, `1` nếu phù hợp một phần, `2` nếu phù hợp rõ. Ẩn hạng, điểm và `proposed_relevance` khi chấm. Ghi người chấm, ngày và căn cứ cho trường hợp cần giải thích.
3. Sau khi chốt pool, với mỗi truy vấn có `n` cặp, rút ngẫu nhiên `ceil(0.20 × n)` cặp không lặp. Sắp xếp theo `(query_id, book_id)` trước khi lấy mẫu và lưu seed cùng danh sách đã rút. Quy tắc này bao phủ ít nhất 20% toàn pool và có mẫu cho từng truy vấn. Người thứ hai chấm riêng trên bản đã ẩn cả nhãn của người thứ nhất. Sau đó mới so nhãn, ghi bất đồng, lý do và quyết định cuối.
