# P4 — Tuần3: Index nghiệm thu, Reader ổn định và môi trường sạch

- Mốc21–27/11/2026. Đọc lại Sheet trực tiếp22/11, `02_Cong_viec!A40:O52`.
- Đã kiểm bàn giao P3 mới; chưa đánh dấu Done task tuần3. Xem [nghiệm thu](acceptance.md).
- OpenSpec giữ local; thư mục tuần chỉ có task, mục lục và nghiệm thu.

| Mã | Ngày | P4 phụ trách | Hỗ trợ | Phụ thuộc | Hàng Sheet |
| --- | --- | --- | --- | --- | --- |
| [C38](C38.md) | 21/11 | Bộ FAISS cuối dự kiến nghiệm thu | P3 | C35,C37,C24 | 43 |
| [C42](C42.md) | 22/11 | Reader mở đúng sách/chương | P3 | C25,C29,C41 | 47 |
| [C46](C46.md) | 23/11 | Dựng hệ thống ở môi trường sạch | P2 | C38,C42 | 51 |

Bên nhận C38 là P1/P2; C42 là P2 cho luồng dẫn chứng tuần4; C46 là cả nhóm demo. Chỉ tiến hành phần có đầu vào đủđiềukiện và ghi rõ giới hạn. Hai toànvăn P3 vẫnpending, chưa tựbật Reader vì đãtrackingGit.

P4 hỗ trợ C40/P2 (đo gợi ý), C41/P3 (20toànvăn), C47/P1 (hành trìnhSearch), C50/P3 (chuẩn bị chương/đoạn). Không tự nhận toàn bộ công việc lead khác. C49 sửa lỗi chung24/11; C51 quyết định RAG26/11. Chưa có quyết định GO thì không tự triển khai RAG.

Quy trình và căn cứ chung tại [README P4](../README.md). SPEC là tài liệu gốc; Sheet phân công/lịch. Quy môpublic/RAG/nghiệmthu toàn hệthống không được thay bằng gói demo hoặc fixture.

SPEC gốc SHA256 `20cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea`; Sheet `02_Cong_viec!A40:O52` đọc trực tiếp22/11/2026. Nền P4 `36ad1d4`, develop `6e873a6`, bàn giao P3 `a0666cc`.
