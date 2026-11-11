# Frontend SmartLib AI — C04

React 18 + TypeScript + Vite 5, CSS và Lucide. Dùng Node.js 22 như Dockerfile.

## Chạy tại máy

Từ thư mục `web`, chạy `npm install` lần đầu.

- `npm run dev:demo`: đọc dữ liệu C02 trong repo, không gọi backend. Mở URL Vite in ra (mặc định http://localhost:3000).
- `npm run dev`: API thật, proxy `/api/v1` tới `http://localhost:8000`.
- `npm run build`: kiểm tra TypeScript và tạo `dist/`.
- `npm run preview`: xem bản production đã build; không có mock và cần cấu hình phục vụ API để tích hợp.
- `node scripts/check-demo.mjs`: kiểm tra fixture và các trạng thái demo.

Dừng server cũ bằng Ctrl+C trước khi đổi lệnh. Vite có thể chọn cổng khác khi 3000 đang bận.

## Phần dùng chung

- `App.tsx`: khung trang, route, 404 và Back/Forward bằng History API.
- `components/Header.tsx`: thanh điều hướng, số sách đã chọn.
- `components/ui.tsx`: `Button`, `Input` có label, `LoadingState`, `EmptyState`, `ErrorState` có callback thử lại.
- `components/BookCard.tsx`: nhận `book: BookSummary` và `onNavigate`.
- `styles/index.css`: màu/font, layout và breakpoint; giữ màu và kích thước theo mục 13.4 đặc tả.
- `services/apiClient.ts`: đầu mối gọi API; demo chỉ bật khi Vite DEV và `VITE_DEMO_MODE=true`.
- `services/demo.ts`: mô phỏng API bằng dữ liệu C02; tìm chuỗi và danh sách gợi ý chỉ để thử UI, chưa phải thuật toán AI.
- `services/c02Catalog.ts`, `catalogParser.ts`: đọc/kiểm tra JSONL và chuyển sang kiểu dữ liệu frontend; không sao chép sách vào component.
- `services/taxonomy.ts`: đổi mã thể loại/chủ đề sang nhãn tiếng Việt từ `data/taxonomy.json`.
- `types/api.ts`: kiểu dữ liệu hiện có, cần tiếp tục đối chiếu C03 khi tích hợp.
- `services/navigation.ts`: `withSnapshot(path)` cho href và điều hướng; ưu tiên snapshot trên URL, sau đó trạng thái tab. App tự áp dụng helper khi gọi `onNavigate`.

Điểm tích hợp: P1 tiếp tục form và `fetchBooks` nhánh `/search` trong `src/pages/ExplorePage.tsx`; P3 tiếp tục nhánh `/books`, BookCard, phân trang trong cùng file và `src/pages/DetailPage.tsx`; P4 tiếp tục `src/pages/ReaderPage.tsx`. Không cần tạo lại Header/footer trong các trang.

## Route và bàn giao

- `/`: Khám phá, danh mục và tìm kiếm — P3/P1 tiếp tục nghiệp vụ.
- `/books/:book_id`: Chi tiết — phối hợp P3.
- `/recommendations`: Gợi ý — P2 tiếp tục C27.
- `/read/:book_id/:chapter_id`: trang tạm Reader trong layout chung — P4 tiếp tục tại `src/pages/ReaderPage.tsx`. Route cũng chấp nhận `/read/:book_id`; hiện chưa tự tải chương đầu.

### Kiểm tra Reader khi C02 chưa có chương

Chạy `npm run dev:demo`, bấm **Kiểm tra trang tạm Reader** trong bảng demo hoặc mở trực tiếp `http://localhost:3000/read/SLB_B0001/chuong-minh-hoa` (thay cổng nếu Vite đang dùng cổng khác). `SLB_B0001` là ID sách C02; `chuong-minh-hoa` chỉ là ID thử route, không phải dữ liệu chương. Có thể dùng ID minh họa khác để kiểm tra trang tạm, reload và Back/Forward. Trang hiển thị ID nhận từ URL, mục lục trống và vùng chờ nội dung; không gọi API chương/QA.

Sách C02 có `fulltext_approved=false` vẫn hiển thị **Chỉ có thông tin sách**, cùng nút **Đọc sách/Đọc** bị disabled ở thẻ sách, chi tiết và kết quả gợi ý. Link kiểm thử Reader là đường vào trang tạm, không mở khóa toàn văn cho sách.

### Bàn giao P4

- File chính: `web/src/pages/ReaderPage.tsx`, nhận props `bookId`, `chapterId?`, `onNavigate` từ route trong `web/src/App.tsx`.
- Header, main, footer do `App.tsx` cung cấp. Giữ nguyên layout chung; triển khai mục lục và vùng nội dung tại các vị trí đang có trong ReaderPage.
- CSS bố cục trang tạm: `.reader-placeholder-layout` trong `web/src/styles/index.css`. Dùng lại `Button`, `LoadingState`, `EmptyState`, `ErrorState` từ `components/ui.tsx`.
- Khi có dữ liệu, nối API qua `apiRequest` trong `services/apiClient.ts`: `GET /books/:book_id/chapters` và `GET /chapters/:chapter_id`. Kiểu dữ liệu có sẵn trong `types/api.ts`.
- P4 bổ sung kiểm tra ID thật, chuyển chương đầu khi thiếu chapter_id, chương trước/sau, đồng bộ URL và trạng thái tải/rỗng/lỗi. Khung QA thuộc giai đoạn tiếp theo; trang tạm C04 chưa có chức năng hỏi đáp.

Các trang gọi chung API client để chuyển giữa demo và API thật. State demo C02 dùng `ai_library_demo_c02_v1`, tách với `ai_library_v1` và bộ demo tự tạo trước đây; không lưu ID mẫu vào phiên thật. Không đưa khóa Gemini vào frontend.

Liên kết nội bộ giữ `snapshot_id` nếu đã có, kể cả mở bằng href; snapshot trên URL được ưu tiên khi gọi API thật. Health chỉ khởi tạo phiên chưa có snapshot, không tự chuyển snapshot đang dùng. Demo chỉ có một bộ C02 nên query snapshot trong demo dùng để thử giữ URL, không mô phỏng nhiều phiên bản dữ liệu. Bộ chọn snapshot mới/xử lý xung đột ID đầy đủ cần tích hợp tiếp theo mục 13.5.

tabStorage kiểm tra cấu trúc trước khi dùng, báo trạng thái lưu lỗi và giữ lựa chọn trong bộ nhớ nếu sessionStorage không hoạt động. Điều hướng đặt focus vào vùng main; form tìm kiếm không lấy focus khỏi ô nhập khi nhận kết quả.

## Dữ liệu C02 và cách bổ sung sách

Nguồn duy nhất của demo là `data/raw/sample_batch/catalog.jsonl`, lấy nguyên byte từ commit `a9fa1d1` của PR #1 (C02). File gốc có 20 sách, các nguồn đang `pending`, `fulltext_approved=false`. Giao diện hiển thị đúng trạng thái Chờ duyệt và không tự bật Đọc/QA. Việc sử dụng local để thử UI không thay đổi trạng thái duyệt nguồn.

Khi có sách mới:

1. Thêm một dòng JSON vào `data/raw/sample_batch/catalog.jsonl`, cùng schema C02: `book_id`, `work_id`, `title`, `authors[]`, `genres[]`, `topics[]`, `summary`, `language`, `sources[]`, `cover_url`, `fulltext_approved`.
2. Cấp `book_id` mới cho mỗi ấn bản; giữ cùng `work_id` nếu là các ấn bản của một tác phẩm. Không tái sử dụng ID đã cấp cho sách khác. Nguồn giữ đủ `source_id`, `content_type`, URL, ghi chú và trạng thái quyền.
3. Nếu có mã thể loại/chủ đề mới, bổ sung nhãn vào `data/taxonomy.json`. Mã không có nhãn vẫn hiển thị được bằng chính mã đó.
4. Lưu file và refresh trình duyệt. Không cần sửa `BookCard`, danh sách hay trang chi tiết. Danh mục tự phân trang 20 sách/trang; sách mới dùng được trong tìm kiếm minh họa và lựa chọn gợi ý.

JSON sai hoặc ID trùng sẽ hiện lỗi kèm tên file/dòng; không âm thầm bỏ sách lỗi. Dữ liệu C02 được nạp động chỉ trong dev demo, không đưa catalog thô vào bundle production.

Adapter demo đã hỗ trợ dữ liệu toàn văn tương lai qua file tùy chọn `data/raw/sample_batch/chapters.jsonl` theo schema nhập của pipeline: mỗi dòng gồm `book_id`, `chapter_id`, `order_no`, `title`, `paragraphs[]` (chuỗi). Nút Đọc chỉ bật khi có đủ: `fulltext_approved=true`, nguồn `fulltext` đã `approved`, và chương tương ứng. P4 cần tiếp tục nối dữ liệu đó vào ReaderPage; hiện route luôn hiển thị trang tạm. Không tự tạo văn bản cho sách chỉ có metadata. Demo chưa bật RAG.

Khi chuyển sang API thật bằng `npm run dev`, frontend tiếp tục nhận các trường cùng hợp đồng qua `/api/v1/books`, `/books/:id`… Sách mới ở backend sẽ xuất hiện qua API sau khi nhóm nhập/phát hành dữ liệu; không phải sửa component. Phần backend danh mục trên nhánh hiện tại vẫn là skeleton, nên demo C02 chưa đồng nghĩa API thật đã được triển khai.

## Checklist kiểm tra thủ công

1. Chạy demo: xem 20 sách C02, mở chi tiết và nguồn Chờ duyệt; chọn sở thích, mở Gợi ý. Bộ C02 hiện chưa có sách đọc được.
2. Mở `/read/SLB_B0001/chuong-minh-hoa`, kiểm tra trang tạm có header/footer và đúng ID; thử Back/Forward, reload. ID minh họa không cần tồn tại trong dữ liệu. Route sai cấu trúc hiện 404.
3. Dùng bộ chọn trạng thái demo: tải chậm 2,5 giây, không kết quả, lỗi. Quay lại Bình thường để phục hồi. Với tìm kiếm/gợi ý, bấm gửi để xem trạng thái.
4. Tại 390 px và 1280 px: không tràn ngang, chữ đọc được, header và thao tác xuống dòng hợp lý.
5. Dùng Tab, Shift+Tab, Enter; kiểm tra skip link, label và focus rõ.
6. Chạy build trước khi bàn giao.

Kiểm tra tự động `node scripts/check-demo.mjs` gồm render route/layout (SSR), callback onRetry, liên kết snapshot, dữ liệu C02, mô phỏng sách mới và fallback storage. SSR không thay thế đo bố cục 390/1280 hoặc thao tác bàn phím trong trình duyệt. Chụp ảnh hai kích thước và bổ sung link commit/PR C04 trước khi nghiệm thu; PR #1 chỉ là dữ liệu C02.

C04 cung cấp nền tảng và dữ liệu C02 để làm song song, có phân trang danh mục. Thuật toán Search/Recommendation, bộ lọc đầy đủ, xử lý snapshot và nghiệp vụ QA thuộc các đầu việc tích hợp tiếp theo. Kiểm tra trực quan bằng trình duyệt vẫn cần thực hiện trước khi đánh dấu nghiệm thu UI.
