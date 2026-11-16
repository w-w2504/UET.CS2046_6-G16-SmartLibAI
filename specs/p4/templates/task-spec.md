# <Cxx> — <Tên task>

Trạng thái đặc tả: Nháp / Đã thống nhất / Đang điều chỉnh. Chỉ giữ giá trị thực tế.

## 1. Nguồn và trách nhiệm

- Tuần: W<n>, thư mục `specs/p4/week-<nn>/`.
- Phụ trách chính: P4. Người hỗ trợ / bên nhận: <theo Sheet>.
- Nguồn: <URL tab, range chứa task>; đọc ngày <ngày thực tế>.
- Tài liệu gốc: `documents/SPEC.md`; phiên bản/ngày và commit hoặc hash nội dung đã đối chiếu: <thực tế; dùng hash nếu bản đang sửa chưa commit>.
- SPEC liên quan: <mục/yêu cầu/FR/N/E2E áp dụng cho task>.
- OpenSpec change: `openspec/changes/<change-name>/` (local).
- Trạng thái đầu vào và phân công: <đã xác minh / đang chờ>.

## 2. Mục tiêu và phạm vi

<Mô tả hành vi phải có theo SPEC gốc, phạm vi được giao và phần phụ thuộc người khác. Ghi rõ khác biệt nếu Sheet/task/code lệch SPEC; không tự thay đổi yêu cầu.>

## 3. Đầu vào và phụ thuộc

| Đầu vào / mã việc | Bên cung cấp | Hợp đồng hoặc phiên bản | Trạng thái thực tế |
| --- | --- | --- | --- |
| <đầu vào> | <P1/P2/P3> | <schema/ID/model/hash nếu đã có> | <đã có/đang chờ> |

Chưa có đầu vào: <fixture/mock sẽ dùng và giới hạn có thể kiểm chứng>.

## 4. Hành vi và hợp đồng chi tiết

- Luồng thành công: <đầu vào → xử lý → đầu ra>.
- Schema/API/hàm/tệp: <tên, kiểu, mặc định, ràng buộc, lỗi và ví dụ>.
- ID, snapshot, mapping và offset: <nếu liên quan>.
- Vector/model/chuẩn hóa: <nếu liên quan; P3 sinh vector, P4 kiểm tra và index>.
- Xử lý sai đầu vào, thiếu dữ liệu, timeout và lỗi: <hành vi quan sát được>.
- Phạm vi quyền sử dụng dữ liệu và bí mật: <nếu liên quan>.
- Điểm chưa thống nhất: <ghi rõ, không điền giả>.

## 5. Sản phẩm bàn giao

| Sản phẩm | Vị trí hoặc hợp đồng | Người sử dụng |
| --- | --- | --- |
| <sản phẩm> | <đường dẫn/hàm/API> | <bên nhận> |

## 6. Tiêu chí chấp nhận

| Mã | Điều khoản / yêu cầu SPEC | Điều kiện / thao tác | Kết quả phải có | Cách kiểm chứng |
| --- | --- | --- | --- | --- |
| <Cxx-AC01> | <mục/FR/N/E2E> | <Given/When> | <Then> | <test/lệnh/kiểm tra> |

Bao gồm trường hợp thành công, sai dữ liệu và nhánh lỗi liên quan. Không chỉ kiểm tra tệp tồn tại khi yêu cầu là đọc/xác minh được nội dung.

## 7. Kế hoạch kiểm thử và bằng chứng

- Môi trường, dữ liệu, model/config và snapshot cần cố định: <thực tế>.
- Các kiểm thử dự kiến: <lệnh/test case>.
- Phân biệt mock và thật: <những gì chưa chứng minh được bằng mock>.
- Bằng chứng sau thực hiện: <commit/PR/test report/log/ảnh đã loại bí mật>.

Kết quả thực tế được ghi tại `acceptance.md` của tuần. Chưa chạy thì ghi “Chưa chạy”.

## 8. Quyết định và thay đổi

Xung đột hoặc lựa chọn chưa được chốt phải được hỏi lại người dùng trước khi thực hiện phần phụ thuộc. Đề xuất của người triển khai chưa phải quyết định được duyệt.

| Ngày | Vấn đề / phương án | Quyết định được người dùng xác nhận | Căn cứ / ảnh hưởng |
| --- | --- | --- | --- |
| <ngày> | <xung đột hoặc lựa chọn> | <quyết định thực tế hoặc đang chờ> | <tham chiếu> |
