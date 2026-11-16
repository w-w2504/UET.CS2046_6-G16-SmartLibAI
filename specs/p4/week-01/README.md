# P4 — Tuần 1: FAISS chạy thử, index sách đầu tiên và trình đọc cơ bản

- Mốc dự kiến: 07–13/11/2026.
- Nguồn: [02_Cong_viec](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=96043016), đọc 10/11/2026.
- Trạng thái ngày 10/11/2026: đã có mã và kiểm chứng fixture cho C05/C14/C18; xem [báo cáo nghiệm thu](acceptance.md). C14 chưa tích hợp vector P3 thật; API đọc thật giữ ở C25 tuần 2.
- Quy trình và ranh giới: [README P4](../README.md).

## Task P4 phụ trách chính

| Mã | Ngày dự kiến | Công việc | Hỗ trợ | Phụ thuộc | Hàng nguồn |
| --- | --- | --- | --- | --- | --- |
| C05 | 07/11 | Kiểm tra FAISS có thể lưu và tìm vector | P3, P1 | C01 | 10 |
| C14 | 10/11 | Tạo kho tìm kiếm FAISS từ vector do P3 giao | P3 | C11 | 19 |
| C18 | 11/11 | Tạo trang đọc sách cơ bản | P3 | C02,C04 | 23 |

### C05 — Kiểm tra FAISS có thể lưu và tìm vector

- Cách thực hiện theo Sheet: Cài thư viện; tạo vài vector giả có 384 con số; thử lưu rồi tìm vector gần nhất; chưa cần dữ liệu sách thật.
- Bàn giao: Đoạn chương trình FAISS chạy thử được.
- Bên sử dụng: P3/P1/P2.
- Khi chưa có đầu vào: P4 test vector mock 384d, không đợi P3 chạy E5.
- Đặc tả chi tiết: [C05.md](C05.md); lệnh chạy và bằng chứng trong báo cáo nghiệm thu.

### C14 — Tạo kho tìm kiếm FAISS từ vector do P3 giao

- Cách thực hiện theo Sheet: P4 nhận vector + mã sách từ P3; kiểm tra số chiều và mã; đưa vào FAISS; lưu bảng nối vị trí vector với mã sách.
- Bàn giao: P4 giao P1/P2 kho FAISS, bảng mã sách và hàm đọc kho.
- Bên sử dụng: P1/P2.
- Khi chưa có đầu vào: Trước C11 dùng vector giả 384d; khi P3 giao batch thật thì thay data.
- Đặc tả chi tiết: [C14.md](C14.md); có cấu trúc vector theo SPEC, interface hàm và đề xuất tệp nguồn chưa chốt.

### C18 — Tạo trang đọc sách cơ bản

- Cách thực hiện theo Sheet: Làm khung hiển thị chương, mục lục và nút chương trước/sau bằng một số chương mẫu; chưa làm hỏi đáp AI.
- Bàn giao: Giao diện đọc sách cơ bản.
- Bên sử dụng: Week 4 QA UI.
- Khi chưa có đầu vào: Không xây chunk retrieval tuần 1.
- Đặc tả chi tiết: [C18.md](C18.md); ghi rõ mismatch response và trách nhiệm C18/C25.

## Việc P4 hỗ trợ

| Mã | Người chính | Phần việc được hỗ trợ | Phụ thuộc |
| --- | --- | --- | --- |
| C02 | P3 | Thống nhất thông tin cần lưu về sách | C01 |
| C03 | P1 | Thống nhất cách trang web gửi và nhận dữ liệu | C01 |
| C07 | P3 | Chuẩn bị 20 cuốn sách mẫu sạch và đúng định dạng | C02,C06 |
| C08 | P1 | Viết phần biến câu tìm kiếm thành vector | C03,C02 |
| C10 | P3 | Viết chương trình nhập và kiểm tra dữ liệu sách | C02,C07 |
| C11 | P3 | Dùng E5 biến 20 cuốn sách mẫu thành vector | C02,C07 |
| C16 | P1 | Cho trang web gọi được chức năng tìm kiếm | C03,C12,C14 |

## Việc chung cần phối hợp

- C01 (07/11): Thống nhất mục tiêu và thứ tự ưu tiên; phụ thuộc Có thể bắt đầu ngay.
- C06 (08/11): Chia đều việc tìm và kiểm tra nguồn sách; phụ thuộc C02.
- C19 (12/11): Cùng kiểm tra kết quả cuối tuần 1; phụ thuộc C07,C11,C12,C13,C14.

## Hồ sơ thực hiện và nghiệm thu

- Change local đặt dạng `p4-w01-<task-or-scope>` trong `openspec/changes/`; nội dung liên kết mã task ở trên.
- Chi tiết mỗi task lưu trong thư mục tuần này. Chưa có tệp task không đồng nghĩa task đã hoặc chưa được triển khai; cần đối chiếu code và đầu vào khi bắt đầu.
- Báo cáo tuần: [acceptance.md](acceptance.md), chỉ ghi kết quả đã kiểm chứng. Hoàn thành phần fixture không thay cho nghiệm thu tích hợp thật.
