# P4 — Tuần 4: Truy xuất đoạn, tích hợp API QA, kiểm thử RAG và triển khai cuối

- Mốc dự kiến: 28/11–04/12/2026.
- Nguồn: [02_Cong_viec](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=96043016), đọc 10/11/2026.
- Trạng thái tài liệu: danh mục kế hoạch ban đầu; chưa đánh giá việc triển khai hay nghiệm thu.
- Quy trình và ranh giới: [README P4](../README.md).

## Task P4 phụ trách chính

| Mã | Ngày dự kiến | Công việc | Hỗ trợ | Phụ thuộc | Hàng nguồn |
| --- | --- | --- | --- | --- | --- |
| C54 | 28/11 | P4 tạo kho FAISS cho từng sách để tìm đoạn liên quan | P3 | C05,C53,C52 | 59 |
| C58 | 29/11 | P4 nối các phần lại thành API hỏi đáp | P1, P3 | C54,C55,C57 | 63 |
| C62 | 01/12 | Kiểm tra các tình huống lỗi và độ an toàn RAG | P2 | C58,C59,C60 | 67 |
| C65 | 02/12 | Đưa bản cuối lên môi trường chạy demo | P1 | C46,C58,C64 | 70 |

### C54 — P4 tạo kho FAISS cho từng sách để tìm đoạn liên quan

- Cách thực hiện theo Sheet: Nhận vector đoạn từ P3; dựng chỉ mục FAISS riêng từng sách; nhận câu hỏi để tìm các đoạn liên quan đúng cuốn.
- Bàn giao: Phần tìm đoạn sách liên quan đã kiểm thử.
- Bên sử dụng: P1 context builder.
- Khi chưa có đầu vào: Build index ngay trên batch chunk/vector sách mẫu của P3.
- Đặc tả chi tiết sẽ lưu tại `C54.md`, dùng [mẫu task](../templates/task-spec.md).

### C58 — P4 nối các phần lại thành API hỏi đáp

- Cách thực hiện theo Sheet: Kết hợp tìm đoạn của P4 với phần Gemini của P1; kiểm tra đúng sách, thời gian chờ và lỗi khi thiếu dữ liệu.
- Bàn giao: API hỏi đáp hoạt động thử được.
- Bên sử dụng: P2 QA UI.
- Khi chưa có đầu vào: Dùng mock LLM khi quota chưa có.
- Đặc tả chi tiết sẽ lưu tại `C58.md`, dùng [mẫu task](../templates/task-spec.md).

### C62 — Kiểm tra các tình huống lỗi và độ an toàn RAG

- Cách thực hiện theo Sheet: P4 thử đổi sách, sai mã đoạn, hết thời gian, Gemini lỗi; bảo đảm tìm kiếm và gợi ý vẫn chạy.
- Bàn giao: Danh sách bài thử RAG và minh chứng.
- Bên sử dụng: Final release.
- Khi chưa có đầu vào: Use mock provider if rate limited.
- Đặc tả chi tiết sẽ lưu tại `C62.md`, dùng [mẫu task](../templates/task-spec.md).

### C65 — Đưa bản cuối lên môi trường chạy demo

- Cách thực hiện theo Sheet: P4 dựng lại hệ thống, cấu hình máy chủ, thử mở API, kiểm tra trường hợp dữ liệu mới bị lỗi.
- Bàn giao: Bản chạy demo cuối cùng và nhật ký triển khai.
- Bên sử dụng: Cả nhóm demo.
- Khi chưa có đầu vào: Không public API key.
- Đặc tả chi tiết sẽ lưu tại `C65.md`, dùng [mẫu task](../templates/task-spec.md).

## Việc P4 hỗ trợ

| Mã | Người chính | Phần việc được hỗ trợ | Phụ thuộc |
| --- | --- | --- | --- |
| C53 | P3 | P3 chia sách thành đoạn nhỏ và tạo vector cho từng đoạn | C41,C50,C52 |
| C55 | P1 | P1 viết phần gửi câu hỏi và đoạn sách cho Gemini | C52 |
| C56 | P2 | P2 làm khung hỏi đáp trong trang đọc sách | C42,C52 |
| C57 | P1 | P1 kiểm tra Gemini có trả lời và dẫn nguồn hợp lệ không | C55,C54 |
| C59 | P2 | P2 nối giao diện hỏi đáp với API thật | C56,C58 |
| C60 | P3 | Xử lý lần lượt từng sách cho RAG | C53,C54,C41 |
| C64 | P3 | Kiểm tra dữ liệu, phiên bản và nguồn trước khi nộp | C38,C60 |

## Việc chung cần phối hợp

- C52 (28/11): Họp mở đầu tuần cuối và chia việc theo thực tế; phụ thuộc C51.
- C66 (03/12): Cả nhóm tự nghiệm thu và ghi rõ phần chưa hoàn thành; phụ thuộc C61,C62,C63,C64,C65.

## Hồ sơ thực hiện và nghiệm thu

- Change local đặt dạng `p4-w04-<task-or-scope>` trong `openspec/changes/`; nội dung liên kết mã task ở trên.
- Chi tiết mỗi task lưu trong thư mục tuần này. Chưa có tệp task không đồng nghĩa task đã hoặc chưa được triển khai; cần đối chiếu code và đầu vào khi bắt đầu.
- Báo cáo tuần: `acceptance.md`, tạo theo [mẫu nghiệm thu](../templates/weekly-acceptance.md) và chỉ điền kết quả đã kiểm chứng.
- C54/C58/C62 thuộc nhánh RAG sau quyết định GO tại C51/C52. Chưa có quyết định thì ghi đang chờ; không tự nhận là đã được duyệt.
- C65 là triển khai bản cuối. Nếu NO-GO RAG, cần xác nhận lại phụ thuộc C58 trong Sheet; vẫn báo các yêu cầu RAG chưa đạt SPEC.
