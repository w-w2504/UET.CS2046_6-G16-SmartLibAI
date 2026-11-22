# C29 — Sống chết mặc bay, một toàn văn thật

Nguyên tác tiếng Việt của **Phạm Duy Tốn**, đăng *Nam Phong* số18, tháng12/1918. Bản chép lấy từ [Wikisource revision203701](https://vi.wikisource.org/wiki/S%E1%BB%91ng_ch%E1%BA%BFt_m%E1%BA%B7c_bay?oldid=203701); [trang tác gia revision203702](https://vi.wikisource.org/wiki/T%C3%A1c_gia:Ph%E1%BA%A1m_Duy_T%E1%BB%91n?oldid=203702) xác nhận tên tác giả/tác phẩm và năm mất1924. Trang nguồn gắn nhãn **public domain** cho nguyên tác đã phát hành1918 và tác giả mất hơn100năm.

- `catalog.jsonl`: một ấn bản, metadata và mô tả mới tự biên soạn từ truyện; nguồn metadata/summary/fulltext approved riêng, có thời điểm và vai trò AI kiểm chứng thực. Không ghi con người đã tự đọc/duyệt khi chưa có xác nhận đó.
- `chapters.jsonl`: một chương “Toàn văn”,39 đoạn,5.843ký tự sau chuẩn hóa NFC và ghép hai LF; không tạo chương giả để có nút Trước/Sau.
- `id_registry.json`: UUIDv4 có tiền tố cho book/work/chapter/source/paragraph; quan hệ book→work, chapter→book và paragraph key `chapter_id:sha256:N` với N là số lần xuất hiện của đoạn trong chương. Khi tái dựng phải dùng lại registry này.
- `raw/story.html`, `raw/author.html`: bản nguồn đóng băng, chỉ lưu để đối chiếu; không nhập HTML vào kho phục vụ. Raw trang Wikisource giữ ghi công/URL/giấy phép CC BY-SA cho phần biên tập trang. Nguyên tác public domain được tách riêng; không nhập chú thích biên tập hiện đại, ảnh, bản dịch hoặc menu.
- `review.json`: hash raw/text, revision, thời điểm, phạm vi quyền và cách lấy trọn phần truyện. Đã đối chiếu toàn bộ token từ câu mở đến câu kết, bỏ chỉ số chú thích và dấu trang trí; không bỏ câu truyện.

Không sửa catalog294 hoặc bộ150 demo. Đây là đầu vào **một tác phẩm thật để nghiệm thu C29**, chưa phải corpus20tác phẩm/RAG hay nghiệm thu toàn hệ thống.

## Dựng snapshot Reader riêng

Với `.venv` đã cài requirements của pipeline/API và ICU thật, từ repo root:

```powershell
$env:PYTHONPATH = "$PWD/pipeline;$PWD/api"
.\.venv\Scripts\python.exe -B -m ai_library.reader_snapshot --batch data/raw/c29_fulltext1 --output-dir data/demo/c29-reader-rebuild/snapshots/c29-songchet-20261121 --snapshot c29-songchet-20261121 --cldr-version 49.0
```

`49.0` là CLDR đọc thực từ ICU79.1 của môi trường đã kiểm. Nếu build bằng ICU khác, xác minh và truyền phiên bản CLDR tương ứng, không chép số này để giả môi trường. Snapshot chỉ có catalog/Reader; không sinh vector/chunk hoặc tự sửa active. Mã producer từ chối đích tồn tại, nguồn chưa approved, registry thiếu và dữ liệu không qua validator API.

Gói bàn giao C29 có sẵn snapshot, control riêng và hướng dẫn chạy API/web; bên nhận có thể dùng trực tiếp mà không build lại.
