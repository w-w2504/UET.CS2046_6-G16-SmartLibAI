# Hướng dẫn tài liệu P4

Áp dụng cho tài liệu dưới `specs/p4/`.

- Khi có xung đột, yêu cầu chưa rõ hoặc phải lựa chọn phương án mà người dùng chưa chốt, bắt buộc hỏi lại người dùng. Trình bày vấn đề, các phương án và ảnh hưởng; có thể đề xuất nhưng không tự quyết định, không mặc định phương án đề xuất là được duyệt. Chờ câu trả lời rõ ràng trước khi thực hiện phần phụ thuộc; không coi im lặng là đồng ý. Ghi lại quyết định đã được người dùng xác nhận. Có thể tiếp tục công việc độc lập không cần quyết định đó.
- `documents/SPEC.md` là tài liệu gốc của toàn dự án. Bắt buộc đối chiếu khi phân tích, đặc tả, chia task, thiết kế, triển khai, kiểm thử, nghiệm thu và bàn giao; Sheet dùng để phân công/lập lịch, tài liệu OpenSpec và P4 phải bám SPEC.
- Mỗi task và báo cáo nghiệm thu phải truy vết được tới mục/yêu cầu SPEC liên quan (FR, N, E2E nếu áp dụng), phiên bản SPEC đã đối chiếu và bằng chứng kiểm tra. Task con chỉ nghiệm thu phần yêu cầu được giao, không thay cho nghiệm thu toàn hệ thống.
- Khi Sheet, task, OpenSpec hoặc code mâu thuẫn với SPEC, ghi rõ điểm lệch và lấy SPEC làm căn cứ; nếu cần đổi yêu cầu thì trình người dùng thống nhất và cập nhật SPEC trước khi triển khai phần thay đổi. Không tự sửa SPEC để hợp thức hóa code hoặc giảm tiêu chí nghiệm thu.
- Người dùng phụ trách P4 theo Google Sheet được dẫn trong README. Giữ ranh giới P3 sinh vector → P4 xây FAISS/mapping/truy xuất; các nhiệm vụ API/trình đọc/triển khai theo phân công.
- Mỗi tuần dùng thư mục `week-01` đến `week-04`; đặc tả chi tiết từng task là `Cxx.md`, báo cáo tuần là `acceptance.md`.
- Đọc README tuần, nguồn phân công và `documents/SPEC.md` trước khi viết yêu cầu. Ghi mã task, ngày đọc nguồn, đầu vào, phụ thuộc, phạm vi, đầu ra và tiêu chí kiểm chứng.
- Công việc thực hiện theo OpenSpec; lưu proposal/design/delta specs/tasks/tiến độ trong `openspec/` local. Không chuyển cấu trúc delta spec bắt buộc của OpenSpec sang thư mục này.
- Tài liệu task là yêu cầu dự kiến, không phải bằng chứng hoàn thành. Báo cáo phải tách trạng thái đã triển khai, đã kiểm thử, đạt, chưa đạt và chưa chạy.
- Không tự điền số đo, nguồn được duyệt, tài nguyên tài khoản, hash, commit hoặc kết quả thử nghiệm khi chưa có bằng chứng.
- Mọi kết quả mock/fixture phải có nhãn rõ. Lượt gọi provider thật, dữ liệu thật và chỉ tiêu chất lượng AI được báo riêng.
- Bằng chứng chia sẻ dùng đường dẫn tương đối trong repo hoặc link commit/PR/test/log đã loại bí mật. Không dùng một đường dẫn OpenSpec local làm bằng chứng duy nhất.
- Nếu SPEC, Sheet và hiện trạng code khác nhau, ghi rõ khác biệt; không âm thầm đổi phân công, giảm phạm vi hoặc tuyên bố đã nghiệm thu.
- Không sửa Google Sheet khi chưa được yêu cầu.
