# Nguồn và ghi công dữ liệu Reader P3

## Tệp được bảo toàn

| Tác phẩm | Tác giả | EPUB gốc SHA-256 |
| --- | --- | --- |
| Cha con nghĩa nặng | Hồ Biểu Chánh | `ad37e7fc13e19a5286bab4d003d610fd3c2a401c020143c62d47ed36c398cf49` |
| Nửa chừng xuân | Khái Hưng | `16b9bb3230a25fa9b802c29c7be8a6376e4e41cbf2e61bb4610d9e2102cbfec4` |

EPUB lấy từ Tủ sách Văn Học Việt Nam, được giữ nguyên bytes. Mỗi bản chỉ chứa
XHTML/XML/CSS và metadata EPUB, không có ảnh bìa, font hay nội dung đa phương tiện.
Phiên bản EPUB lần lượt là 2026-11-06T12:42:08Z và 2026-11-06T12:42:13Z.

Nguồn phân phối EPUB và lời ghi nguồn:

- <https://van-hoc.pages.dev/ho-bieu-chanh/cha-con-nghia-nang/>
- <https://van-hoc.pages.dev/khai-hung/nua-chung-xuan/>

Hai trang ghi văn bản từ Wikisource tiếng Việt và mô tả nguyên tác là phạm vi công
cộng. Đây là ghi nhận công bố của nguồn; không phải tuyên bố quyền mới của SmartLibAI.

## Nguồn Wikisource và người đóng góp

- Hồ Biểu Chánh, *Cha con nghĩa nặng*, bản 1929:
  <https://vi.wikisource.org/w/index.php?title=Cha_con_nghĩa_nặng&oldid=156330>
  và lịch sử <https://vi.wikisource.org/w/index.php?title=Cha_con_nghĩa_nặng&action=history>.
- Khái Hưng, *Nửa chừng xuân*, bản được nguồn ghi là 1934:
  <https://vi.wikisource.org/w/index.php?title=Nửa_chừng_xuân&oldid=106616>
  và lịch sử <https://vi.wikisource.org/w/index.php?title=Nửa_chừng_xuân&action=history>.

Ghi công tác giả, cộng đồng Wikisource tiếng Việt và Tủ sách Văn Học Việt Nam.
Các trang Wikisource có thẻ PVCC-Việt Nam và thông tin giấy phép ở chân trang.
Không suy từ một thẻ phạm vi công cộng tại Việt Nam thành kết luận về mọi quốc gia
hoặc mọi thành phần của một ấn bản. Bằng chứng và URL từng chương nằm trong
`source_manifest.json`; không dùng giấy phép code của repo để cấp lại quyền nguyên tác.

Đối với phần biên tập của Wikisource thuộc CC BY-SA 4.0, giữ ghi công, liên kết nguồn,
liên kết giấy phép và thông tin sửa đổi; phần chuyển thể thuộc giấy phép này tiếp tục
theo CC BY-SA 4.0. Giấy phép: <https://creativecommons.org/licenses/by-sa/4.0/>;
điều khoản đầy đủ: <https://creativecommons.org/licenses/by-sa/4.0/legalcode>;
điều khoản tái sử dụng Wikimedia:
<https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en#7._Licensing_of_Content>.
Không có yêu cầu gắn thêm hạn chế đối với phần đã thuộc phạm vi công cộng.

## Thay đổi định dạng do P3

`chapters.jsonl` là văn bản trích xuất từ hai EPUB trên, chuẩn hóa Unicode NFC,
tách 28 mục đọc và 4.301 đoạn, giữ liên kết chapter/book cùng ID ổn định trong registry.
Đây là chuyển đổi định dạng cho classroom demo; không sửa lại nội dung để tạo dữ liệu mới.
Các checksum chương và EPUB trong source manifest cho phép truy xuất bản đã dùng.

Việc chuẩn bị các tệp cho Git theo yêu cầu dự án không thay đổi quyết định phục vụ:
hai nguồn fulltext vẫn `pending`, hai sách vẫn `fulltext_approved=false`.
Không có phê duyệt production hoặc reviewer mới được tạo ở lượt này. Reader staging
dùng SQLite fixture riêng; P4 vẫn phụ trách nối dữ liệu vào snapshot phục vụ chính thức.
