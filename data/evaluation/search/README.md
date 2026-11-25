# C30/C32 — Thông báo tiến độ đánh giá Semantic Search

Thông báo này cập nhật tiến độ chuẩn bị bộ truy vấn và candidate pool, triển khai baseline BM25 nội bộ, cùng các bước còn lại của đánh giá Search theo SPEC. C30 chưa hoàn tất vì pool cuối, nhãn của người chấm và review độc lập chưa có đủ bằng chứng.

## Phần đã thực hiện

### Bộ truy vấn C30

- Đã chuẩn bị 50 truy vấn tiếng Việt: 20 truy vấn `dev` và 30 truy vấn `test`, đúng yêu cầu tại SPEC 15.1 và TEAM-04. Có 26 truy vấn mô tả nhu cầu, 14 truy vấn ngắn và 10 truy vấn có bộ lọc.
- 48 truy vấn dựa trên ấn bản có ref trong `data/raw/c24_classroom/curation.tsv`; hai truy vấn còn lại dùng sách mẫu `SLB_B0007` và `SLB_B0018`. Mỗi truy vấn có ba candidate ban đầu, tổng cộng 150 cặp query–book. Đây là gợi ý ban đầu, chưa phải pool top-20 cuối theo SPEC.
- Trong 150 candidate ban đầu có 50 gợi ý `proposed_relevance=0`, 50 gợi ý mức 1 và 50 gợi ý mức 2. Các mức này do heuristic metadata tạo ra, chưa được người chấm xác nhận.
- Catalog hiện có 294 sách: 20 sách có trạng thái nguồn `approved` và 274 sách `pending`. Trong CSV, 48 anchor C24 vẫn `pending`; hai anchor sách mẫu là `approved`. Trên 150 dòng candidate ban đầu, trạng thái nguồn là 32 dòng `approved` và 118 dòng `pending`. Các trạng thái này được giữ nguyên; URL là căn cứ để kiểm tra nguồn, không phải xác nhận quyền phát hành.

### Baseline BM25 C32

- Baseline nội bộ được triển khai trong `pipeline/ai_library/bm25_search.py`, với công cụ chạy tại `pipeline/ai_library/search_eval.py`; đây không phải API phục vụ người dùng.
- BM25 dùng biểu diễn sách năm dòng theo SPEC 10.4: title, authors, tên hiển thị genres, tên hiển thị topics và summary. Mã sắp xếp taxonomy theo code; giữ dòng rỗng; chuẩn hóa NFC và khoảng trắng từng dòng. Tokenizer dùng NFC + casefold, tách theo dãy chữ/số Unicode, giữ dấu tiếng Việt và không loại stopword.
- Cấu hình là `k1=1.5`, `b=0.75`, `IDF=ln(1+(N-df+0.5)/(df+0.5))`. Bộ lọc authors/genres dùng OR trong từng danh sách và AND giữa các bộ lọc; lọc được áp dụng trước khi lấy top-20. Kết quả xếp theo điểm giảm dần, hòa điểm theo `book_id` tăng dần. Mỗi ấn bản được giữ riêng, không gộp theo `work_id`.
- Baseline đã chạy cho 50 truy vấn và tạo 1.000 dòng top-20 trong `search_eval_bm25_top20.csv`. Lượt chạy dùng catalog `data/raw/c20_c34/catalog.jsonl` gồm 294 sách cùng taxonomy hiện có; CSV kết quả ghi `source_corpus_id` và SHA-256 của catalog/taxonomy để truy vết.
- Snapshot E5 `p4-w03-c38-reviewed-r8-20261122` hiện có trong nhánh, gồm 289 sách và 289 vector; manifest và SHA-256 của các tệp đã kiểm tra khớp. Helper eligibility dùng trong Search xác nhận 286 sách đủ cả metadata và summary `approved` trong đúng snapshot. Tuy nhiên, máy hiện tại chưa có trọng số model `intfloat/multilingual-e5-small` revision `fd1525a9fd15316a2d503bf26ab031a61d056e98`, PyTorch, Sentence Transformers hoặc FAISS; vì vậy chưa thể mã hóa query và chạy top-20 E5.
- Output BM25 hiện có vẫn dùng corpus `catalog-c20-c34-e37d367e9cae` gồm 294 sách; output không ghi `snapshot_id` và chưa áp dụng eligibility của snapshot r8. Vì thế đây vẫn là BM25-only provisional, không phải pool cuối cùng và không thể ghép với kết quả E5 để so sánh cùng snapshot. Chưa có kết quả semantic hoặc pool hợp nhất E5/BM25.
- Các `proposed_relevance` được giữ lại khi candidate gợi ý xuất hiện trong top-20 BM25. Chúng là gợi ý heuristic từ metadata, không phải nhãn người chấm và chưa được dùng để tính metric.

### Trạng thái chấm nhãn

- Chưa có nhãn chính thức: `relevance_label` đang trống và `label_status=pending_human_label`.
- Reviewer, annotator, ngày chấm/review và kết quả phân xử chưa được điền. Trong CSV, `review_status=await_final_pool`, `cross_review_required` để trống và `disagreement_status=not_reviewed`.
- Chưa tính metric, chưa chọn threshold và chưa điều chỉnh model bằng dữ liệu test. Công cụ đã tạo candidate BM25 cho cả hai split để chuẩn bị đánh giá; test vẫn phải được giữ riêng, đóng băng và không dùng để hiệu chỉnh theo SPEC 15.1–15.2.

## Phần tiếp theo

Khi trọng số E5 đúng revision sẵn sàng, cần chạy E5 và BM25 trên cùng snapshot r8, cùng 50 query, filters, tập sách eligible và luật hòa điểm. Pool cuối sẽ hợp `book_id` top-20 của từng phương pháp cho mỗi query, đồng thời ghi snapshot/corpus ID, hash, cấu hình và nguồn tạo pool. Sau đó mới chấm nhãn; `proposed_relevance` tiếp tục chỉ là gợi ý cho tới khi người chấm xác nhận. Test phải được giữ riêng, không dùng để chọn threshold hoặc chỉnh model. Hiện chưa có pool cuối, nhãn chính thức, review chéo hay metric để báo cáo.

## Phần cần review độc lập

Sau khi pool cuối được tạo, một thành viên P2/P3 sẽ được nhờ review độc lập các truy vấn, anchors, căn cứ, bộ lọc và candidate pool. Hiện chưa có thành viên nào được liên hệ hoặc phân công; chưa có xác nhận review.

Người chấm cần xác nhận từng cặp query–book theo nhãn 0 = không phù hợp, 1 = liên quan một phần, 2 = phù hợp rõ. Sau đó, một người thật khác sẽ review độc lập ít nhất 20% tổng số cặp trong pool cuối; bất đồng và cách phân xử cần được lưu lại. Chưa có bằng chứng chấm nhãn, review chéo hay xử lý bất đồng nên C30 chưa thể coi là hoàn tất.

## Chạy baseline BM25

Từ thư mục `pipeline` trong PowerShell:

```powershell
python -m ai_library.search_eval --overwrite
```

`--overwrite` cần thiết khi muốn tạo lại output mặc định đã tồn tại. Công cụ không gọi API, không tạo snapshot và không thay đổi trạng thái quyền dữ liệu.
