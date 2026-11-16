# Hướng dẫn tài liệu P4

Áp dụng cho tài liệu dưới `specs/p4/`.

## Phối hợp 4 agent

Người dùng xác nhận ngày 10/11/2026: dùng 4 agent gồm điều phối, backend/FAISS, frontend/reader và kiểm chứng.

Cập nhật ngày 17/11/2026: review, nhận xét và kiểm tra code chỉ dùng một agent chính. Mô hình bốn vai trò là lựa chọn cho triển khai có các phần độc lập, không phải yêu cầu phải khởi chạy agent phụ trong mọi lượt làm việc.

- Điều phối đọc SPEC và hồ sơ tuần/task, giao việc, quản lý phụ thuộc và phạm vi tệp, tích hợp kết quả, cập nhật hồ sơ OpenSpec và báo cáo với người dùng. Chỉ điều phối thực hiện thao tác Git ghi lịch sử/push trong phạm vi đã được người dùng yêu cầu.
- Backend/FAISS phụ trách phần pipeline, index/mapping và API thuộc P4 được giao; frontend/reader phụ trách trình đọc và tích hợp API thuộc P4 được giao. Vai trò AI không thay đổi phân công P1/P2/P3/P4 trong Sheet.
- Kiểm chứng review độc lập so với SPEC, chạy kiểm tra phù hợp sau khi phần cần kiểm tra ổn định, xác minh bằng chứng và báo lỗi/giới hạn. Mặc định không sửa mã triển khai; nếu cần sửa test hoặc tài liệu bằng chứng, điều phối phải giao phạm vi tệp riêng.
- Trước khi giao việc, điều phối ghi vào hồ sơ change local: mã task, điều khoản SPEC, đầu vào/phụ thuộc, đầu ra, tiêu chí kiểm chứng, agent phụ trách và danh sách tệp được sửa. Mỗi tệp chỉ có một agent được giao sửa tại một thời điểm; tệp chung do điều phối tích hợp hoặc bàn giao tuần tự.
- Chỉ chạy song song công việc độc lập. Hợp đồng dữ liệu/API chung phải bám SPEC và quyết định đã được xác nhận trước khi triển khai phần phụ thuộc. Agent phát hiện xung đột/lựa chọn chưa chốt phải báo điều phối để hỏi người dùng; không tự chọn phương án.
- Agent bàn giao phải nêu tệp đã đổi, kết quả thực tế và lệnh kiểm tra, bằng chứng, phần chưa chạy và vấn đề còn mở. Điều phối kiểm tra tích hợp trước khi đánh dấu hoàn thành; báo cáo của agent không tự thay thế bằng chứng nghiệm thu.
- Dùng tối đa 4 agent đồng thời kể cả điều phối trong phiên hiện tại. Chỉ khởi chạy agent khi có việc được giao; không tạo task mới chỉ để đủ số agent. Agent phụ không tự tạo thêm agent.
- Quy tắc này hướng dẫn phối hợp, không tự kích hoạt khả năng đa agent ở một phiên khác. Nếu phiên sau không hỗ trợ đủ agent, báo người dùng để thống nhất cách thực hiện.

## Quy tắc tài liệu và nghiệm thu

- Khi có xung đột, yêu cầu chưa rõ hoặc phải lựa chọn phương án mà người dùng chưa chốt, bắt buộc hỏi lại người dùng. Trình bày vấn đề, các phương án và ảnh hưởng; có thể đề xuất nhưng không tự quyết định, không mặc định phương án đề xuất là được duyệt. Chờ câu trả lời rõ ràng trước khi thực hiện phần phụ thuộc; không coi im lặng là đồng ý. Ghi lại quyết định đã được người dùng xác nhận. Có thể tiếp tục công việc độc lập không cần quyết định đó.
- `documents/SPEC.md` là tài liệu gốc của toàn dự án. Bắt buộc đối chiếu khi phân tích, đặc tả, chia task, thiết kế, triển khai, kiểm thử, nghiệm thu và bàn giao; Sheet dùng để phân công/lập lịch, tài liệu OpenSpec và P4 phải bám SPEC.
- Mỗi task và báo cáo nghiệm thu phải truy vết được tới mục/yêu cầu SPEC liên quan (FR, N, E2E nếu áp dụng), phiên bản SPEC, đầu vào, lệnh và kết quả kiểm tra thực. Task con chỉ nghiệm thu phần yêu cầu được giao, không thay cho nghiệm thu toàn hệ thống.
- Khi Sheet, task, OpenSpec hoặc code mâu thuẫn với SPEC, ghi rõ điểm lệch và lấy SPEC làm căn cứ; nếu cần đổi yêu cầu thì trình người dùng thống nhất và cập nhật SPEC trước khi triển khai phần thay đổi. Không tự sửa SPEC để hợp thức hóa code hoặc giảm tiêu chí nghiệm thu.
- Người dùng phụ trách P4 theo Google Sheet được dẫn trong README. Giữ ranh giới P3 sinh vector → P4 xây FAISS/mapping/truy xuất; các nhiệm vụ API/trình đọc/triển khai theo phân công.
- Mỗi tuần dùng thư mục `week-01` đến `week-04`; đặc tả chi tiết từng task là `Cxx.md`, báo cáo tuần là `acceptance.md`.
- Đọc README tuần, nguồn phân công và `documents/SPEC.md` trước khi viết yêu cầu. Ghi mã task, ngày đọc nguồn, đầu vào, phụ thuộc, phạm vi, đầu ra và tiêu chí kiểm chứng.
- Công việc thực hiện theo OpenSpec; lưu proposal/design/delta specs/tasks/tiến độ trong `openspec/` local. Không chuyển cấu trúc delta spec bắt buộc của OpenSpec sang thư mục này.
- Tài liệu task là yêu cầu dự kiến, không phải bằng chứng hoàn thành. Báo cáo phải tách trạng thái đã triển khai, đã kiểm thử, đạt, chưa đạt và chưa chạy.
- Không tự điền số đo, nguồn được duyệt, tài nguyên tài khoản, hash, commit hoặc kết quả thử nghiệm khi chưa có bằng chứng.
- Mọi kết quả mock/fixture phải có nhãn rõ. Lượt gọi provider thật, dữ liệu thật và chỉ tiêu chất lượng AI được báo riêng.
- Quyết định ngày 15/11/2026: thư mục tuần chỉ giữ mục lục, đặc tả task và nghiệm thu; không lưu bộ mẫu, log, ảnh hoặc manifest kiểm thử dưới P4. Output chi tiết của test dùng thư mục tạm ngoài P4. Báo cáo ghi SPEC, phiên bản, đầu vào, lệnh, kết quả, giới hạn và PR; không dẫn tới tệp kiểm chứng. Coreach chỉ đính kèm trực tiếp PR, không log/ảnh/manifest. Giữ truy vết kiểm chứng theo SPEC 16.2, không tự coi thu gọn tài liệu là miễn kiểm thử.
- Nếu SPEC, Sheet và hiện trạng code khác nhau, ghi rõ khác biệt; không âm thầm đổi phân công, giảm phạm vi hoặc tuyên bố đã nghiệm thu.
- Không sửa Google Sheet khi chưa được yêu cầu.
