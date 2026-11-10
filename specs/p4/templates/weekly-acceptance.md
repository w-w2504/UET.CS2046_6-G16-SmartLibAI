# P4 — Báo cáo nghiệm thu tuần <nn>

Trạng thái: Chưa nghiệm thu. Chỉ cập nhật theo bằng chứng thực tế.

## 1. Phạm vi và phiên bản

- Tuần / khoảng thời gian: <Wn, theo kế hoạch>.
- Ngày kiểm thử và người thực hiện / review: <thực tế; chưa có thì ghi chưa có>.
- Task chính, task hỗ trợ và việc chung đã tham gia: <mã Cxx>.
- Nguồn phân công và ngày đối chiếu: <URL/range/ngày>.
- Tài liệu gốc: `documents/SPEC.md`; phiên bản/ngày và commit hoặc hash nội dung đã đối chiếu: <thực tế>.
- Đặc tả task: <liên kết Cxx.md>.
- Change OpenSpec: <tên; hồ sơ local>.
- Commit/PR: <phiên bản được kiểm thử, không điền giả>.
- Môi trường / dependency / model revision / snapshot / config / hash: <thực tế>.

## 2. Kết quả từng task

| Task | Phạm vi đã triển khai | Đã kiểm thử gì | Kết luận | Bằng chứng |
| --- | --- | --- | --- | --- |
| <Cxx> | <thực tế> | <thực tế hoặc chưa chạy> | Chưa kiểm chứng | <link hoặc chưa có> |

Kết luận dùng Đạt / Chưa đạt / Chưa chạy / Chờ đầu vào / Tạm hoãn theo quyết định đã có. Không suy ra “Đạt” chỉ từ checkbox hoặc việc tạo tài liệu.

## 3. Bài kiểm tra và kết quả

| Yêu cầu SPEC | Task / test / tiêu chí | Input và điều kiện | Expected theo SPEC | Actual | Pass/Fail/Chưa chạy | Loại dữ liệu | Bằng chứng |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <mục/FR/N/E2E> | <Cxx / Cxx-AC01> | <input> | <expected> | Chưa chạy | Chưa chạy | <mock/thật> | Chưa có |

Ghi lệnh chạy, exit code, thời gian và lỗi quan trọng nếu đã quan sát. Kết quả fixture/mock provider không thay cho đo chất lượng trên dữ liệu thật.

## 4. Bàn giao và tích hợp

| Sản phẩm | Bên nhận | Version / đường dẫn | Tình trạng tiếp nhận |
| --- | --- | --- | --- |
| <FAISS/mapping/API/trình đọc> | <P1/P2/P3> | <thực tế> | <đã kiểm tra/chưa xác nhận> |

## 5. Lỗi, phụ thuộc và phần chưa đạt

- <Lỗi hoặc đầu vào còn thiếu, ảnh hưởng và hướng xử lý>.
- <Khác biệt với SPEC/Sheet và quyết định đã có nếu có>.
- <Các xung đột/lựa chọn đã hỏi người dùng, quyết định được xác nhận hoặc còn đang chờ; không coi đề xuất là quyết định>.
- <Tiêu chí chưa kiểm thử hoặc chưa đủ dữ liệu>.
- Với tuần 4: <quyết định GO/NO-GO RAG, nguồn quyết định và phần SPEC còn thiếu>.

## 6. Kết luận nghiệm thu

<Kết luận dựa trên các yêu cầu SPEC được đối chiếu: chưa đủ bằng chứng / đạt các task liệt kê / còn các tiêu chí chưa đạt. Phân biệt nghiệm thu phần P4, tuần và toàn hệ thống; không tuyên bố đạt đầy đủ SPEC khi vẫn còn yêu cầu bắt buộc chưa đạt.>

## 7. Bằng chứng đính kèm

<Đường dẫn tương đối trong repo hoặc link commit/PR/log/ảnh đã loại bí mật. Không chỉ trỏ sang OpenSpec local.>
