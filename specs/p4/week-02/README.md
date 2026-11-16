# P4 — Tuần 2: Cập nhật index, API danh mục/chương và đọc sách thật

- Mốc dự kiến: 14–20/11/2026.
- Nguồn: [02_Cong_viec](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=96043016), đọc 10/11/2026.
- Trạng thái tài liệu: danh mục kế hoạch ban đầu; chưa đánh giá việc triển khai hay nghiệm thu.
- Quy trình và ranh giới: [README P4](../README.md).

## Task P4 phụ trách chính

| Mã | Ngày dự kiến | Công việc | Hỗ trợ | Phụ thuộc | Hàng nguồn |
| --- | --- | --- | --- | --- | --- |
| C21 | 14/11 | Cập nhật FAISS cho lô khoảng 80 sách | P3 | C10,C14,C20,C11 | 26 |
| C25 | 15/11 | Làm API lấy danh sách, chi tiết và chương sách | P3 | C10,C18 | 30 |
| C29 | 16/11 | Cho người dùng đọc sách thật | P3 | C18,C25 | 34 |
| C35 | 18/11 | P4 cập nhật FAISS cho danh mục mở rộng | P1, P2 | C21,C34,C24 | 40 |

### C21 — Cập nhật FAISS cho lô khoảng 80 sách

- Cách thực hiện theo Sheet: P3 sinh vector cho sách mới; P4 nhận vector, kiểm tra rồi tạo lại FAISS và tệp thông tin đi kèm.
- Bàn giao: Bộ dữ liệu tìm kiếm/gợi ý bản 1 dùng được.
- Bên sử dụng: P1/P2 chạy Search/Rec; P3 kiểm dữ liệu.
- Khi chưa có đầu vào: P4 thử với vector 20 sách trước; nhận batch >=80 từ P3 khi có.
- Đặc tả chi tiết sẽ lưu tại `C21.md`, dùng [mẫu task](../templates/task-spec.md).

### C25 — Làm API lấy danh sách, chi tiết và chương sách

- Cách thực hiện theo Sheet: Viết phần máy chủ trả danh sách sách, sách được chọn, danh sách chương và nội dung chương.
- Bàn giao: Các API đọc thông tin sách và chương chạy được.
- Bên sử dụng: P3 UI + P2 Detail.
- Khi chưa có đầu vào: Fixture chapter có thể độc lập.
- Đặc tả chi tiết sẽ lưu tại `C25.md`, dùng [mẫu task](../templates/task-spec.md).

### C29 — Cho người dùng đọc sách thật

- Cách thực hiện theo Sheet: Nối trình đọc với API; hiển thị mục lục, nội dung từng chương, xử lý khi tải chương lỗi.
- Bàn giao: Trang đọc sách sử dụng được với sách mẫu có toàn văn.
- Bên sử dụng: W4 QA UI.
- Khi chưa có đầu vào: UI dùng chương mẫu.
- Đặc tả chi tiết sẽ lưu tại `C29.md`, dùng [mẫu task](../templates/task-spec.md).

### C35 — P4 cập nhật FAISS cho danh mục mở rộng

- Cách thực hiện theo Sheet: P3 sinh vector mới rồi bàn giao; P4 kiểm tra và dựng lại kho FAISS; nếu lỗi vẫn giữ bộ cũ hoạt động.
- Bàn giao: Bộ FAISS bản 2 và bảng kiểm tra tính đúng.
- Bên sử dụng: P1/P2.
- Khi chưa có đầu vào: P4 chuẩn bị validator/loader khi P3 còn encode; tiếp tục phục vụ snapshot v1.
- Đặc tả chi tiết sẽ lưu tại `C35.md`, dùng [mẫu task](../templates/task-spec.md).

## Việc P4 hỗ trợ

| Mã | Người chính | Phần việc được hỗ trợ | Phụ thuộc |
| --- | --- | --- | --- |
| C24 | P3 | Kiểm tra chất lượng vector và tạo vector cho sách mới | C11,C20 |
| C31 | P2 | Tạo bộ tình huống để đánh giá gợi ý | C20 |

## Việc chung cần phối hợp

- C36 (19/11): Demo cả tìm kiếm, gợi ý và đọc sách; phụ thuộc C22,C23,C26,C27,C28,C29,C35.

## Hồ sơ thực hiện và nghiệm thu

- Change local đặt dạng `p4-w02-<task-or-scope>` trong `openspec/changes/`; nội dung liên kết mã task ở trên.
- Chi tiết mỗi task lưu trong thư mục tuần này. Chưa có tệp task không đồng nghĩa task đã hoặc chưa được triển khai; cần đối chiếu code và đầu vào khi bắt đầu.
- Báo cáo tuần: `acceptance.md`, tạo theo [mẫu nghiệm thu](../templates/weekly-acceptance.md) và chỉ điền kết quả đã kiểm chứng.
