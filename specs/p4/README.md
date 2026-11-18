# P4 — FAISS, trình đọc và triển khai

Người dùng workspace này phụ trách P4. Tài liệu này ghi quy ước và phân công; trạng thái triển khai, kiểm chứng và đầu vào thật được ghi riêng trong nghiệm thu từng tuần.

Khi có xung đột, yêu cầu chưa rõ hoặc cần chọn phương án mà người dùng chưa chốt, phải hỏi lại và chờ người dùng quyết định trước khi làm phần phụ thuộc. Có thể phân tích, đề xuất và tiếp tục phần độc lập; không tự lựa chọn hay coi im lặng là đồng ý. Quyết định được xác nhận phải được ghi vào hồ sơ task/OpenSpec.

## Nguồn và phạm vi

- [Kế hoạch của nhóm](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=1627151559), đọc ngày 10/11/2026.
- Phân công: tab `01_Ai_lam_gi`, hàng 9. Danh sách task chuẩn: `02_Cong_viec!A5:O71`; các tab tuần là bản trình bày lại.
- [documents/SPEC.md](../../documents/SPEC.md) là tài liệu gốc của toàn dự án, làm căn cứ cho mọi bước phân tích, chia task, thiết kế, triển khai, kiểm thử, nghiệm thu và bàn giao. Sheet quy định phân công/lịch; đặc tả P4 và OpenSpec cụ thể hóa yêu cầu của SPEC.
- P3 làm sạch dữ liệu, chạy E5 và giao vector. P4 nhận vector, kiểm tra, tạo FAISS/mapping, cung cấp hàm đọc cho P1/P2, làm API/trình đọc và triển khai.
- RAG: P3 chia chunk và sinh vector; P4 dựng index/truy xuất, tích hợp API QA; P1 gọi Gemini/kiểm chứng đầu ra; P2 làm khung QA và mở dẫn chứng.

Kế hoạch có 4 tuần, từ 07/11 đến 04/12/2026; SPEC hiện ghi ràng buộc 6 tuần. Dùng 4 tuần để tổ chức phần P4 theo bảng phân công, ghi rõ khác biệt khi lập kế hoạch; không tự sửa phạm vi nghiệm thu trong SPEC.

## Công việc theo tuần

| Tuần | Thời gian dự kiến | P4 phụ trách chính | Trọng tâm |
| --- | --- | --- | --- |
| [Tuần 1](week-01/README.md) | 07–13/11/2026 | C05, C14, C18 | FAISS chạy thử, index sách đầu tiên và trình đọc cơ bản |
| [Tuần 2](week-02/README.md) | 14–20/11/2026 | C21, C25, C29, C35 | Cập nhật index, API danh mục/chương và đọc sách thật |
| [Tuần 3](week-03/README.md) | 21–27/11/2026 | C38, C42, C46 | Index nghiệm thu, trình đọc ổn định và dựng trên máy sạch |
| [Tuần 4](week-04/README.md) | 28/11–04/12/2026 | C54, C58, C62, C65 | Truy xuất đoạn, tích hợp API QA, kiểm thử RAG và triển khai cuối |

Có 14 task chính của P4. Task hỗ trợ và việc chung được liệt kê trong từng tuần; không mặc nhiên nhận toàn bộ phần việc của P1/P2/P3. Ngày là mốc phối hợp dự kiến, không suy ra quá hạn hay hoàn thành từ ngày hiện tại.

## Nơi lưu tài liệu

```text
openspec/                         # Hồ sơ thực hiện, chỉ ở local
  WORKFLOW.md
  config.yaml
  references/                     # Bản chụp phân công để truy vết
  changes/p4-w<nn>-<task-or-scope>/
    proposal.md
    specs/                        # Delta spec của OpenSpec
    design.md
    tasks.md
  changes/archive/
  specs/                          # Spec chính nội bộ của OpenSpec

specs/p4/                         # Tài liệu P4 bàn giao cùng mã nguồn
  README.md
  AGENTS.md
  week-01/                        # Tương tự cho week-02, week-03, week-04
    README.md                     # Danh sách và phụ thuộc công việc tuần
    C05.md                        # Tạo khi bắt đầu đặc tả chi tiết task C05
    C14.md
    C18.md
    acceptance.md                 # Báo cáo nghiệm thu tuần
```

Các tệp task và `acceptance.md` ở cây trên minh họa quy ước đặt tên; chúng được tạo khi bắt đầu tuần/task hoặc có lượt nghiệm thu. Bộ khung ban đầu không phải hồ sơ nghiệm thu đã chạy.

`openspec/` được loại khỏi Git bằng `.git/info/exclude` của máy này. `specs/p4/` không bị ignore. Người khác đọc báo cáo P4 phải hiểu được yêu cầu, kết quả và giới hạn mà không cần truy cập hồ sơ OpenSpec local.

## Quy trình cho mỗi tuần

1. Đọc lại SPEC gốc và nguồn phân công. Ghi phiên bản SPEC đã đối chiếu, ánh xạ task sang mục/yêu cầu liên quan (FR/N/E2E nếu áp dụng), chọn task của tuần và xác minh đầu vào đang có hay đang chờ. Nếu nguồn khác mâu thuẫn với SPEC, nêu rõ điểm lệch; thay đổi yêu cầu cần được thống nhất và cập nhật SPEC trước khi triển khai phần thay đổi.
2. Dùng `$openspec-explore` nếu cần phân tích; `$openspec-propose` tạo change theo tuần hoặc nhóm task có cùng phạm vi. Ghi mã Cxx vào tên/nội dung để truy vết.
3. Viết đặc tả chi tiết từng task tại `week-<nn>/Cxx.md`: căn cứ SPEC, đầu vào/phụ thuộc, phạm vi, output và tiêu chí kiểm chứng. Liên kết task với change local; giữ delta spec theo cấu trúc OpenSpec.
4. Thực hiện `$openspec-apply-change` khi người dùng yêu cầu triển khai. Theo dõi các bước và tiến độ trong `openspec/changes/.../tasks.md`; phát hiện thay đổi thiết kế thì cập nhật hồ sơ.
5. Kiểm thử theo yêu cầu và tiêu chí SPEC liên quan. Giữ input, expected, actual, pass/fail và phiên bản theo SPEC 16.2; output chi tiết của test ở thư mục tạm ngoài P4. Phân biệt fixture/mock với dữ liệu và lượt gọi thật.
6. Viết `week-<nn>/acceptance.md` có căn cứ SPEC, đầu vào, lệnh, kết quả thực, giới hạn và PR. Không dẫn tới log, ảnh hoặc manifest kiểm thử trong báo cáo tuần. Nghiệm thu task/tuần không thay cho nghiệm thu toàn hệ thống.
7. Đồng bộ spec nội bộ bằng `$openspec-sync-specs` khi cần và archive change đã hoàn tất bằng `$openspec-archive-change`. Giữ tài liệu P4 đủ độc lập để bàn giao.

Một change có thể bao phủ nhiều Cxx cùng tuần; task lớn có thể cần nhiều change. Báo cáo tuần phải chỉ rõ ánh xạ. Không gộp các tuần chỉ để làm mất dấu tiến độ.

## Phối hợp 4 agent

Người dùng xác nhận mô hình này ngày 10/11/2026 cho công việc P4:

Cập nhật 17/11/2026: review, nhận xét và kiểm tra code dùng một agent chính. Chỉ cân nhắc các vai trò dưới đây khi triển khai có công việc độc lập phù hợp; không mặc định khởi chạy nhiều agent.

| Agent | Trách nhiệm |
| --- | --- |
| Điều phối | Đối chiếu SPEC, chia task OpenSpec, giao phạm vi tệp, quản lý phụ thuộc, tích hợp và trao đổi với người dùng |
| Backend/FAISS | Kiểm tra vector, index/mapping, API thuộc P4 theo task được giao |
| Frontend/reader | Trình đọc và tích hợp API thuộc P4 theo task được giao |
| Kiểm chứng | Review độc lập, kiểm thử phù hợp, xác minh bằng chứng và giới hạn nghiệm thu |

Điều phối ghi phân công, đầu vào, đầu ra, tiêu chí kiểm chứng và quyền sửa tệp vào hồ sơ change local trước khi giao việc. Các phần độc lập được làm song song; mỗi tệp chỉ có một agent được giao sửa tại một thời điểm. Tệp/hợp đồng dùng chung được tích hợp hoặc bàn giao tuần tự. Agent kiểm chứng mặc định không sửa mã triển khai; kiểm tra tích hợp khi các phần liên quan đã ổn định.

Mọi agent phải đọc điều khoản SPEC liên quan và báo điều phối khi có xung đột hoặc lựa chọn chưa được người dùng chốt. Điều phối hỏi lại người dùng và chờ quyết định trước khi làm phần phụ thuộc. Vai trò AI không thay đổi trách nhiệm P1/P2/P3/P4 hoặc mở rộng phạm vi task đã giao.

Chỉ điều phối cập nhật tiến độ chung, tổng hợp nghiệm thu và thực hiện commit/push trong phạm vi người dùng đã yêu cầu. Kết quả bàn giao phải có tệp thay đổi, lệnh/kết quả kiểm tra thực tế, bằng chứng và phần chưa chạy. Quy tắc chi tiết nằm trong [AGENTS.md](AGENTS.md); trình tự thực hiện được ghi ở `openspec/WORKFLOW.md` local.

Phiên hiện tại hỗ trợ tối đa 4 agent đồng thời kể cả điều phối; khởi chạy theo việc được giao, không tạo thêm công việc chỉ để đủ số agent. Tài liệu này không tự bật khả năng đa agent trong phiên khác; nếu phiên sau thiếu khả năng tương ứng, báo người dùng để thống nhất cách thực hiện.

## Đầu vào và nghiệm thu

- Đầu vào vector bám producer C11 và SPEC 3.2/10.4: bundle `vectors.npy`, `mapping.jsonl`, `manifest.json`, ID/thứ tự, float32/384/L2, cấu hình model/revision/prefix và hash nguồn. Đọc được mã producer không có nghĩa đã nhận bundle vector thật; P3 vẫn phụ trách sinh vector.
- P4 kiểm tra số lượng, ID, chiều, kiểu, giá trị hữu hạn, vector khác 0, chuẩn hóa và mapping; không tự chạy lại E5 cho toàn bộ sách/chunk thay P3.
- Thiếu đầu vào thật: kiểm thử bằng fixture/mock hợp lệ và ghi nhãn rõ; không lấy kết quả mock làm chứng cứ chất lượng AI hay nghiệm thu dữ liệu thật.
- Chỉ đánh dấu đạt phần đã có bằng chứng. Trạng thái trong Sheet là trạng thái do nhóm cập nhật, không thay cho kiểm chứng code.
- Sheet hiện để RAG phụ thuộc quyết định C51/C52. Chưa có quyết định GO thì không tự triển khai nhánh RAG. Nếu NO-GO, vẫn phải ghi RAG và các tiêu chí tương ứng chưa đạt đầy đủ SPEC.
- Các công việc đóng gói/triển khai cuối vẫn phải được xác nhận khi NO-GO, vì phụ thuộc C58 của C65 trong Sheet cần được nhóm điều chỉnh rõ.
- Chỉ đọc Sheet trong phạm vi công việc này. Chưa có yêu cầu cập nhật trạng thái hoặc ghi bằng chứng lên Google Sheets.

Theo quyết định ngày 15/11/2026, mỗi thư mục tuần chỉ giữ mục lục task, đặc tả task và nghiệm thu. Không lưu bộ mẫu, log, ảnh hoặc manifest kiểm thử dưới P4; không sửa lịch sử Git đã có. Coreach ghi tiến độ riêng và chỉ đính kèm trực tiếp PR liên quan. Việc thu gọn hồ sơ không thay thế kiểm thử thực tế hoặc làm mất yêu cầu truy vết của SPEC 16.2.
