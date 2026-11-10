# P4 — Tuần 3: Index nghiệm thu, trình đọc ổn định và dựng trên máy sạch

- Mốc dự kiến: 21–27/11/2026.
- Nguồn: [02_Cong_viec](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=96043016), đọc 10/11/2026.
- Trạng thái tài liệu: danh mục kế hoạch ban đầu; chưa đánh giá việc triển khai hay nghiệm thu.
- Quy trình và ranh giới: [README P4](../README.md).

## Task P4 phụ trách chính

| Mã | Ngày dự kiến | Công việc | Hỗ trợ | Phụ thuộc | Hàng nguồn |
| --- | --- | --- | --- | --- | --- |
| C38 | 21/11 | Tạo bộ FAISS cuối cho Search và Recommendation | P3 | C35,C37,C24 | 43 |
| C42 | 22/11 | Kiểm tra trình đọc mở đúng sách và chương | P3 | C25,C29,C41 | 47 |
| C46 | 23/11 | Chạy thử toàn bộ hệ thống trên máy sạch | P2 | C38,C42 | 51 |

### C38 — Tạo bộ FAISS cuối cho Search và Recommendation

- Cách thực hiện theo Sheet: P3 giao vector của toàn bộ sách hợp lệ; P4 kiểm tra, xây FAISS và lưu dữ liệu cần để mở lại đúng phiên bản.
- Bàn giao: Bộ FAISS dự kiến dùng khi nghiệm thu.
- Bên sử dụng: P1/P2.
- Khi chưa có đầu vào: P4 test build trên snapshot v2, P3 cập nhật vector theo từng batch.
- Đặc tả chi tiết sẽ lưu tại `C38.md`, dùng [mẫu task](../templates/task-spec.md).

### C42 — Kiểm tra trình đọc mở đúng sách và chương

- Cách thực hiện theo Sheet: P4 kiểm tra đổi chương, lưu phiên bản sách, vị trí đoạn và hiển thị lỗi; thử bằng vài sách có thật.
- Bàn giao: Trình đọc đủ ổn định để phục vụ demo.
- Bên sử dụng: P2 W4 citations.
- Khi chưa có đầu vào: Có thể test 2 sách trước.
- Đặc tả chi tiết sẽ lưu tại `C42.md`, dùng [mẫu task](../templates/task-spec.md).

### C46 — Chạy thử toàn bộ hệ thống trên máy sạch

- Cách thực hiện theo Sheet: P4 thử dựng backend, frontend và kho dữ liệu từ đầu; kiểm tra cấu hình và bảo vệ khóa Gemini trên máy chủ.
- Bàn giao: Hướng dẫn chạy thử, nhật ký lỗi và cách khắc phục.
- Bên sử dụng: Cả nhóm demo.
- Khi chưa có đầu vào: Chạy staging, không chờ QA.
- Đặc tả chi tiết sẽ lưu tại `C46.md`, dùng [mẫu task](../templates/task-spec.md).

## Việc P4 hỗ trợ

| Mã | Người chính | Phần việc được hỗ trợ | Phụ thuộc |
| --- | --- | --- | --- |
| C40 | P2 | Đo chất lượng gợi ý và ghi kết quả | C31,C33,C38 |
| C41 | P3 | Chuẩn bị 20 tác phẩm có toàn văn được phép dùng | C06,C10 |
| C47 | P1 | Thử hành trình tìm kiếm từ đầu đến cuối | C26,C43,C46 |
| C50 | P3 | Sắp xếp dữ liệu chương để có thể làm RAG sau này | C41,C42 |

## Việc chung cần phối hợp

- C49 (24/11): Cả nhóm sửa lỗi theo mức độ quan trọng; phụ thuộc C43,C44,C45,C47,C48.
- C51 (26/11): Quyết định tuần cuối có làm RAG hay không; phụ thuộc C39,C40,C42,C46,C49.

## Hồ sơ thực hiện và nghiệm thu

- Change local đặt dạng `p4-w03-<task-or-scope>` trong `openspec/changes/`; nội dung liên kết mã task ở trên.
- Chi tiết mỗi task lưu trong thư mục tuần này. Chưa có tệp task không đồng nghĩa task đã hoặc chưa được triển khai; cần đối chiếu code và đầu vào khi bắt đầu.
- Báo cáo tuần: `acceptance.md`, tạo theo [mẫu nghiệm thu](../templates/weekly-acceptance.md) và chỉ điền kết quả đã kiểm chứng.
