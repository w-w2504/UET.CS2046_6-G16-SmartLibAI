# Catalog mở rộng C20 và C34

Lô nội bộ gồm 294 sách tiếng Việt, trong đó có 20 sách mẫu và 274 sách mới từ 9 nguồn thư mục. Hai mươi dòng đầu được lấy nguyên từ catalog mẫu. Lô bao phủ cả 8 thể loại trong taxonomy của dự án.

| Nguồn chính | Sách mới |
| --- | ---: |
| Wikisource tiếng Việt, thư mục Hồ Biểu Chánh | 45 |
| Đông Tác, thư mục Nguyễn Hiến Lê | 48 |
| Tạp chí Cỏ Thơm, thư mục Tự Lực Văn Đoàn | 44 |
| Thư viện Trường Đại học Công nghệ Thông tin, ĐHQG-HCM | 20 |
| Danh mục lịch sử và văn hóa của Bảo tàng Bà Rịa – Vũng Tàu | 51 |
| Danh mục học liệu Khoa Tâm lý học, ĐH KHXH&NV, ĐHQG-HCM | 33 |
| Thư mục sách mới của Thư viện Hà Nội | 19 |
| Open Library, kết quả tìm ấn bản tiếng Việt | 13 |
| Nhà xuất bản Trẻ | 1 |
| **Tổng** | **274** |

Từ 303 mục đã thu thập, bộ dựng loại 8 mục trùng nhan đề và tác giả, 1 mục trùng nhan đề, cùng 20 mục có ghi chú loại trong `bibliography.json`. Nhóm 20 mục gồm các mục thiếu tác giả cụ thể, có lỗi ghi tên, có thể trùng tác phẩm hoặc có vai trò tác giả và thể loại cần đối chiếu. Nhan đề và tác giả được chuẩn hóa để phát hiện trùng ngay cả khi dấu hoặc thứ tự đồng tác giả khác nhau.

## Nguồn và quyền

`bibliography.json` lưu URL cùng vị trí tra cứu cho từng mục, nhãn taxonomy và dữ kiện dùng để tạo mô tả. Phần lớn căn cứ là danh mục của thư viện, nhà xuất bản hoặc thư mục tác giả. Một số URL trỏ đến một danh mục chung, nơi vị trí tra cứu nhận diện từng mục.

Toàn bộ 274 sách mới có căn cứ thư mục và cả hai nguồn `metadata` và `summary` đều ở trạng thái `pending`. Trong đó, 16 mô tả diễn đạt lại nội dung từ nguồn và có nhãn `AI-generated` trong `source_note`. 258 bản còn lại dùng mô tả thư mục tự động dựa trên nhan đề, tác giả và dữ kiện được công bố. Các mô tả thư mục này phù hợp để kiểm thử luồng catalog nội bộ. Chất lượng dữ liệu cho tìm kiếm ngữ nghĩa cần được đánh giá sau khi hoàn thiện tóm tắt và phê duyệt quyền theo phạm vi sử dụng của dự án.

C10 đã nhập đủ 294 sách vào SQLite tạm, với 0 dòng cách ly. Kiểm tra toàn vẹn và khóa ngoại đều đạt. C11 nạp được 20 sách mẫu đã duyệt và từ chối lô mở rộng vì trạng thái `pending`. Lô ở giai đoạn metadata, với `has_fulltext=0` và chưa có embedding.

Ba mô-đun kiểm thử importer, SQLite và duyệt nội dung có 14 test đạt. Lượt kiểm thử SQLite dùng collation dự phòng. Các mô-đun kiểm thử cần FAISS chưa chạy vì thư viện FAISS cục bộ phụ thuộc Python 3.13, còn lượt kiểm thử này dùng Python 3.12.

## Tái tạo và kiểm tra

Từ thư mục `pipeline`, dùng môi trường Python của dự án để kiểm tra dữ liệu đã sinh và tính nhất quán của registry.

```powershell
python -m ai_library.expanded_catalog
```

Khi bổ sung mục đã đối chiếu từ một danh mục nguồn, thêm bản ghi vào `bibliography.json` với cặp `provider` và `ref` ổn định. Sau đó chạy bộ dựng để cấp UUID v4 cho mục mới và dùng lại ID đã có. Registry lưu quan hệ `book_id` → `work_id` và ID nguồn theo loại nội dung và URL. Giữ các ID đã cấp trong registry kể cả khi mục tương ứng được rút khỏi catalog.

```powershell
python -m ai_library.expanded_catalog --write
$db = Join-Path $env:TEMP ("smartlib-c20-c34-" + [guid]::NewGuid() + ".sqlite")
python -m ai_library.cli import --batch ../data/raw/c20_c34 --metadata-only --sqlite $db --snapshot c20-c34
```
