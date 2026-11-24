# Tasks

## Trạng thái hiện hành — 23/11/2026

**Batch 3 hoàn thành về dữ liệu và kỹ thuật Reader: tổng 20/20 tác phẩm.** Snapshot thử nghiệm `c41-reader20-batch3-20261123`: 20 books / 20 works / 1.020 mục đọc / 13.292 đoạn; SQLite integrity/FK đạt; Reader ASGI và HTTP TCP kiểm toàn bộ, pytest 62/62, Node 8/8, OpenSpec strict và `git diff --check` đạt; 231/231 protected hashes khớp. Regression Batch 2 → Batch 3 giữ nguyên 702 mục / 12.035 đoạn cũ (bỏ qua `snapshot_id`). C42 chưa được đối chiếu trực tiếp với snapshot Batch 3; đã đạt trong hồi quy Batch 2. Browser E2E chưa chạy và cần kiểm trước demo. Snapshot không active; chưa có nghiệm thu P4 hoặc phát hành công khai. Báo cáo: `data/reports/c41-batch3-20261123/summary.md` và `acceptance.md`.

### Mốc đã chốt Batch 1 (giữ để truy vết)

**Batch 1 hoàn thành theo phạm vi bốn tác phẩm, P3 tự nghiệm thu cho demo nội bộ localhost Việt Nam. Tổng C41: 4/20 tác phẩm, chưa hoàn thành toàn bộ change.** SQLite/ASGI/HTTP TCP đạt 4 sách, 43 mục, 6.387 đoạn; pytest 62/62, Node 4/4, frontend build đạt. Browser E2E bị chặn khi khởi chạy Edge, cần kiểm tra giao diện trước demo. Không có xác nhận nghiệm thu P4. Hồ sơ chốt: `data/reports/c41-batch1-closure-20261123/summary.md`.

P3 xác nhận trực tiếp ngày 23/11/2026 cho đúng hai nguồn metadata/summary Con nhà nghèo; quyết định và hash liên kết tại `data/reports/c41-batch1-closure-20261123/p3_owner_approval.json`. Codex là công cụ kiểm tra tự động; P3 là người xác nhận. Không đổi dữ liệu loader hoặc quyền fulltext. Các ghi chú lỗi 503/chờ xác nhận bên dưới là lịch sử đã được xử lý; không phải blocker hiện hành. Tại mốc chốt Batch 1, Batch 2/3 chưa bắt đầu; trạng thái Batch 2 mới nhất ghi ở trên.

## 1. Batch 1 — kế thừa và xét nguồn

- [x] 1.1 Đối chiếu ID, nội dung và source metadata/summary C29, r8, C42; lưu kết quả trong báo cáo Batch 1.
- [x] 1.2 Tiếp nhận C29 vào thư mục C41, chuyển registry giữ ID và kiểm số 1 chương/39 đoạn, hash nguồn.
- [x] 1.3 Đối chiếu 14 mục đọc của bảy chương *Con nhà nghèo* giữa EPUB/HTML, cấu trúc bản Wikisource đã định danh và hash EPUB; ghi quyết định localhost cùng báo cáo nguồn và kiểm Node.
- [ ] 1.4 Ngoài phạm vi Batch 1 bốn tác phẩm đã chốt; giữ làm việc tương lai, chưa thực hiện: tìm bản *Số đỏ* có quyền của đúng ấn bản hoặc tách được nguyên tác với căn cứ; kiểm TOC, đoạn đầu/cuối trước khi duyệt. Bản 2003 chưa đạt phải có ngoại lệ.
- [x] 1.5 Dựng batch/snapshot C41 thử nghiệm riêng từ các sách approved; kiểm SQLite, offsets, ID, nguồn và hồi quy hash C42 trong báo cáo Batch 1.
  - Importer Python đạt 4/4 sách, 43/43 mục, 0 cách ly; hồi quy C42 SQLite/API đạt. Snapshot và API C41 còn chờ môi trường có PyICU thật, xem `data/raw/c41_reader20_batch1/integration_validation.json`.
  - Kiểm tiếp 23/11/2026: đã cài riêng PyICU thật 2.17, ICU 79.1, CLDR 49.0. Builder tạo SQLite 4/4 work, 43 mục, 6.387 đoạn; integrity/FK/hash/offset đạt nhưng snapshot bị loader từ chối (Reader ASGI 503). Hai nguồn metadata/summary Con nhà nghèo kế thừa r8 thiếu reviewer và có rights_note demo nội bộ, không đáp ứng validator Reader hiện hành. Xem `data/reports/c41-reader4-integration-20261123/summary.md`; chưa nghiệm thu Reader Batch 1. Không sửa approval hoặc policy production để vượt kiểm.
  - Bổ sung cùng ngày theo hướng A: kiểm tra hiện tại hai nguồn metadata/summary, xác nhận dữ kiện và mô tả do dự án biên soạn với nguồn đối chiếu, ghi quyết định riêng Reader localhost Việt Nam cùng reviewer AI/ngày thực tế tại `reader_metadata_summary_review.json`. Không hồi tố ngày duyệt, không sửa rights_status/ID/nội dung/fulltext hoặc validator. Snapshot `c41-reader4-approved-20261123` đạt loader và ASGI thật 4 sách / 43 mục / 6.387 đoạn; xem `data/reports/c41-reader-approval-20261123/reader_api.json`. Task này hoàn tất cho bốn tác phẩm hiện có, chưa đạt toàn C41 20 tác phẩm.

- [x] 1.6 Ghi xác nhận P3 cho hai nguồn metadata/summary Con nhà nghèo, liên kết hash với hồ sơ tự động và tái sử dụng bằng chứng kỹ thuật không đổi; chốt Batch 1 bốn tác phẩm, giữ giới hạn browser E2E.

## 2. Batch 2 — tám tác phẩm (phạm vi điều chỉnh theo P3 ngày 23/11/2026)

- [x] 2.1 Xác minh tám nguồn tác phẩm/ấn bản/bản dịch, giấy phép metadata/summary/fulltext và phạm vi Reader; đối chiếu 10 catalog tracked, không có bản ghi trùng tên chuẩn hóa; ghi review/NOTICE/hash và cách ly tác phẩm có sơ đồ không phù hợp Reader chữ.
- [x] 2.2 Chuẩn hóa tám tác phẩm mới vào batch riêng, giữ 43 mục/6.387 đoạn Batch 1; bộ tích hợp 12 tác phẩm có 702 mục/12.035 đoạn; importer/schema/registry/Unicode và Node 8/8 đạt. Sửa một đoạn NBSP cuối dòng trong dữ liệu mới, không sửa validator.
- [x] 2.3 ASGI và HTTP/Uvicorn thật kiểm cả 12 sách, toàn bộ 702 mục/12.035 đoạn, ID/chunk sai 404; snapshot integrity/FK/hash đạt; pytest 62/62 và Node 8/8. Báo cáo `data/reports/c41-batch2-20261123/summary.md`; không đổi active snapshot hoặc nghiệm thu thay P4.

## 3. Batch 3 — tám tác phẩm

- [x] 3.1 Xác minh nguồn, ấn bản, giấy phép, provenance và ID cho tám tác phẩm; ghi review/NOTICE/hash.
- [x] 3.2 Trích xuất và xác thực dữ liệu; tổng hợp 20 `work_id` duy nhất, 1.020 mục đọc và 13.292 đoạn; không có tác phẩm cách ly.
- [x] 3.3 Dựng snapshot Reader thử nghiệm riêng; SQLite integrity/FK, ASGI thật và HTTP TCP/Uvicorn đều PASS cho toàn bộ tác phẩm/mục đọc/đoạn. Hash 231/231 PASS, hồi quy Batch 2 giữ nguyên toàn bộ nội dung ngoài `snapshot_id`; pytest 62/62, Node 8/8 và OpenSpec strict PASS. Bằng chứng: `data/reports/c41-batch3-20261123/`.
- [x] 3.4 Ghi nghiệm thu kỹ thuật P3 cho dữ liệu/API 20/20; không ghi nhận P4 đã nghiệm thu, không đổi active snapshot. Browser E2E cần thực hiện trước demo.

## 4. Nghiệm thu liên kết

- [ ] 4.1 Bàn giao bộ C41, manifest và ngoại lệ cho P4; P4 xác nhận tích hợp Reader chính thức.
- [ ] 4.2 Bàn giao provenance và kết quả QA cho C45 Phase 2; kiểm báo cáo audit đọc đúng hash/phạm vi nguồn C41.
