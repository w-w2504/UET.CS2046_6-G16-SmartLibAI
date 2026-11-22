# P4 — Tuần 3: FAISS, Reader và môi trường sạch

Cập nhật 22/11/2026, mốc tuần 21–27/11. OpenSpec giữ local; thư mục tuần chỉ chứa task và nghiệm thu.

| Task | Ngày | Phụ thuộc | Trạng thái kiểm chứng |
| --- | --- | --- | --- |
| [C38](C38.md) | 21/11 | C35, C37, C24 | Đạt kỹ thuật ứng viên FAISS 289 sách; còn giới hạn nguồn pending và chất lượng AI |
| [C42](C42.md) | 22/11 | C25, C29, C41 | Đạt Reader hai tác phẩm thật trong phạm vi localhost Việt Nam |
| [C46](C46.md) | 23/11 | C38, C42 | Đã cài WSL; cần khởi động lại Windows rồi tiếp tục Docker trên D và kiểm môi trường sạch |

Cả ba task do P4 phụ trách; P3 hỗ trợ C38/C42, P2 hỗ trợ C46. Bên nhận C38 là P1/P2, C42 phục vụ luồng dẫn chứng P2 tuần 4, C46 phục vụ cả nhóm. Đầu ra C38/C42 được đóng băng trong Git, có hướng dẫn và bộ kiểm nhận không tải model. Chưa có xác nhận P1/P2 đã tích hợp.

Xem [nghiệm thu](acceptance.md) để phân biệt phần đã kiểm, chưa kiểm và giới hạn. Hai toàn văn P3 gốc vẫn pending; bản nhập Reader riêng có rà nguồn/quyền và không thay đổi bản P3. Bộ Search 289 vẫn là ứng viên demo localhost.

P4 hỗ trợ C40/P2, C41/P3, C47/P1 và C50/P3 theo Sheet; không tự nhận toàn bộ task của lead khác. C49 là sửa lỗi chung; C51/C52 quyết định RAG. Hai tác phẩm không thay mục tiêu 20 toàn văn C41, Reader không thay QA/RAG. Căn cứ quy trình chung tại [README P4](../README.md).

SPEC SHA256 `20cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea`; Sheet `02_Cong_viec!A40:O52` đọc trực tiếp 22/11/2026. Nền P4 `36ad1d4`, develop `6e873a6`, bàn giao P3 `a0666cc`. [PR #17](https://github.com/w-w2504/UET.CS2046_6-G16-SmartLibAI/pull/17).
