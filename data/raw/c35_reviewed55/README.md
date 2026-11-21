# C35 — 55 sách được biên tập và kiểm chứng độc lập

Ngày21/11/2026, người dùng giao hai agent: `curator55` viết mô tả mới và `reviewer55` kiểm thông tin/căn cứ, trả sửa khi không chính xác. Đã xác nhận **55/55 sách**, theo đúng hash mô tả ghi trong `review.json`. Tất cả sách thuộc199 bản chưa được chọn trong lô95 cũ; không thêm ID sách hoặc tác phẩm mới.

## Nội dung và phạm vi phê duyệt

- `catalog.jsonl`:55 bản ghi với mô tả tiếng Việt mới, ID giữ nguyên, nguồn metadata và summary được xét riêng.
- `curation.tsv`:55 mô tả mới và URL căn cứ; `curation_combined130.tsv` ghép75 dòng cũ với55 dòng mới, không sửa75 mô tả trước đó.
- `review.json`: kết quả kiểm từng sách, nguồn/locator, hash mô tả, thời điểm, điều kiện phê duyệt và các sửa metadata. Đây là kiểm chứng bởi AI theo ủy quyền người dùng, không được mô tả là con người đã đọc/duyệt từng nguồn.
- `id_registry.json`: giữ lịch sử ID nền và đăng ký thêm ID nguồn theo URL dùng trong lô; `taxonomy.json` là bản taxonomy tại thời điểm biên tập.

User đã cho phép chuyển nguồn đủ điều kiện sang `approved`.55 nguồn metadata và55 nguồn summary đã đạt kiểm chứng, được ghi `approved` **chỉ cho demo/nội bộ SmartLib-AI**. `rights_note` nêu rõ giới hạn; `reviewed_by` ghi đúng vai trò AI dưới ủy quyền; `reviewed_at` là thời điểm kiểm thực. Không tự phê duyệt toàn văn, ảnh hoặc quyền phát hành công khai. Các nguồn của75 sách curation cũ không được nâng nhãn trong đợt này.

Một số mô tả văn học dùng tình huống phần mở đầu của tác phẩm và đã ghi rõ phạm vi, không được hiểu là đã kiểm toàn bộ cốt truyện. Tóm tắt mới do AI diễn đạt, không sao chép toàn văn. Các URL/locator được hai agent đọc để đối chiếu; việc nguồn có văn bản trên web không đồng nghĩa hệ thống đã nhập toàn văn cho Reader/RAG.

## Các lỗi đã được xử lý

- Một mô tả *Hai vợ* diễn giải chưa đúng cuộc đối thoại: sửa theo nguồn rồi reviewer kiểm lại hash mới.
- *Sơ đồ khác biệt văn hóa*: sửa phụ đề “kinh doanh toàn cầu” thành “giao tiếp toàn cầu” theo NXB Kim Đồng, giữ `book_id`/`work_id`.
- *Cơ sở văn hóa Việt Nam*: bổ sung bốn đồng tác giả bên cạnh chủ biên Trần Quốc Vượng theo biểu ghi thư viện, không nhầm chủ biên với toàn bộ danh sách tác giả.
- Loại nguồn *Nắng thu* trùng nhan đề nhưng khác tác phẩm; phân biệt tập *Anh phải sống* của hai tác giả với truyện mang tên tập. Không xác nhận nguồn sai để đủ số lượng.

Các sửa trên được áp dụng vào lô này và bản ghép150. Catalog294 nguồn và75 dòng curation trước đó giữ nguyên để bảo toàn phiên bản đã bàn giao.

## Sử dụng

Lô55 được importer metadata-only và loader C11 thông thường kiểm nhận. Để chuẩn bị C35 với150 sách, dùng bản ghép `data/raw/c35_reviewed150/`; bản đó gồm20 mẫu,75 sách cũ và55 sách mới. Cần tạo bundle/index mới từ đúng catalog đã đổi; bundle95 trước đây không khớp hash hoặc đủ số lượng của150 sách.

Lượt này hoàn thành biên tập/kiểm chứng dữ liệu đầu vào. Chưa tuyên bố đã tạo embedding/FAISS150, đánh giá chất lượng AI, nhập toàn văn hoặc phát hành public.
