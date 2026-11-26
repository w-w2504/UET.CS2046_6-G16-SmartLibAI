# C45 Phase 2 — Reader provenance evidence

Cập nhật: 24/11/2026
Repository: `D:\UET.CS2046_6-G16-SmartLibAI`
Branch/HEAD: `feature/data-embedding` / `9cbd4ceb18e3e5d619a09b2986781cceda8eaf13`

Ma trận gồm **20 tác phẩm**: 8 ngoại lệ có đánh giá chuyên sâu (**3 VERIFIED, 4 PARTIAL, 1 UNVERIFIED theo đúng phạm vi từng record**) và 12 dòng `NOT_REASSESSED` để kiểm kê định danh/nguồn, không gán trạng thái quyền mới. `VERIFIED` chỉ áp dụng cho phạm vi cụ thể ghi trong từng record, không phải xác nhận quyền phân phối công khai.

## Kết quả

| Tác phẩm | Trạng thái | Kết luận hiện tại |
|---|---|---|
| Vim Galore — bản tiếng Việt | VERIFIED | README khớp revision Git pin; không khẳng định revision là HEAD `master` tại thời điểm tải. |
| Nửa chừng xuân | VERIFIED | Hai source metadata/summary pending tách khỏi source approved; kết luận API runtime kế thừa kiểm chứng C45 trước đó. Không truy vấn snapshot/API lại trong lượt này. |
| Giáo dục trong thế giới hậu COVID | VERIFIED | UNESCO 2020 và trang bản dịch công bố CC BY-SA 3.0 IGO. Reader ghi tác phẩm, UNESCO, dịch giả Lê Trung Nghĩa, URL nguồn/license, chuyển đổi định dạng/NFC/chia mục; không hiển thị ảnh, không hàm ý bảo trợ. Phạm vi xác nhận là nội dung text Reader. |
| Thơ ngụ ngôn La Fontaine | PARTIAL | Ấn bản 1951 ghi in theo bản Trung-Bắc Tân-Văn 1928; ghi Nguyễn Văn Vĩnh là dịch giả và Nguyễn Giang kiểm soát xếp chữ. Chưa đối chiếu bản 1928 hoặc xác định mọi phần phát sinh/hiệu đính 1951. |
| Đọc sách thông minh | PARTIAL | PDF catalog và EPUB Reader cùng version 2.0/tháng 1 2024, TOC khớp 11/11; 202/235 anchor khớp, 33 chưa phân loại. Chưa kết luận tương đương toàn văn. |
| Việt Nam phong tục | PARTIAL | Có chứng cứ thư mục độc lập về bản đăng năm 1915; Reader lấy từ scan/bản chép Khai Trí 1973 và có tên nhà sách cùng TOC trang in. Chưa có bản 1915 để so phần đầu/nội dung. |
| Nhập môn Triết học | PARTIAL | Trang OER Libero ghi bản Việt 2025 được dịch/tùy chỉnh và CC BY 4.0. PDF Reader ghi OpenStax/Rice, nhóm dịch và “Lưu hành nội bộ”. Chưa làm rõ ý nghĩa dòng này hoặc quan hệ cấp phép bản dịch với đúng phiên bản OpenStax. |
| Đạo đức, luân lý Đông Tây | UNVERIFIED | Scan 1926 và nội dung Reader xác nhận bài diễn thuyết Phan Châu Trinh cùng một phần tiểu sử riêng. Chữ ký `TRỨNG và HY` hiện là phát hiện chủ sở hữu báo cáo; danh tính và quyền phần tiểu sử chưa xác minh. |

## Attribution và nghĩa vụ đã đối chiếu

**Giáo dục trong thế giới hậu COVID:** nguồn UNESCO gắn CC BY-SA 3.0 IGO và dẫn điều khoản Open Access Repository. Bản tiếng Việt ghi dịch giả Lê Trung Nghĩa, ngày hoàn tất 08/03/2022 và URL bản gốc. Reader item đầu ghi tác giả tổ chức, tên tác phẩm, dịch giả, URL, license và các thay đổi định dạng; item kế tiếp giữ thông tin license/copyright. NOTICE nêu ShareAlike và không có endorsement. Không thấy ISBN trên trang bản quyền trích được. Đề xuất attribution nếu cần dùng ở ngoài demo: “International Commission on the Futures of Education, *Education in a post-COVID world: Nine ideas for public action* (UNESCO, 2020); bản dịch tiếng Việt Lê Trung Nghĩa (2022); CC BY-SA 3.0 IGO; bản Reader chuyển định dạng/NFC/chia mục, không gồm ảnh/bìa.”

**Nhập môn Triết học:** ghi nhận riêng hai lớp quyền. OpenStax/Rice là nguồn giáo trình; Libero Education và nhóm dịch thực hiện bản Việt/tùy chỉnh. Trang OER Libero công bố CC BY 4.0 cho bản Việt. Trang OpenStax hiện tại về Introduction to Philosophy hiển thị CC BY-NC-SA 4.0 trong khi tài liệu/credit của bản Việt ghi OpenStax CC BY 4.0. Chưa pin được đúng phiên bản/điều khoản gốc đã dùng và chưa có giải thích của Libero về “Lưu hành nội bộ”; vì vậy không kết luận bản PDF này được phân phối công khai theo CC BY 4.0. Attribution đang có trong Reader là cần thiết nhưng không tự giải quyết mâu thuẫn cấp phép.

**La Fontaine:** chứng cứ 1951 đủ cho kết luận hẹp rằng chính ấn bản tự nhận in theo bản 1928; BnF độc lập ghi ấn bản Vĩnh Thịnh 1951 và dịch giả. Điều đó không thay thế bản 1928 để chứng minh giống toàn văn. Người kiểm soát xếp chữ Nguyễn Giang được ghi riêng, không gán là dịch giả hay suy ra quyền với phần bổ sung.

## Việc còn mở và người cần quyết định

- **P3/P4 — Đạo đức, luân lý Đông Tây:** quyết định bỏ phần tiểu sử khỏi demo hoặc giữ sau khi có nguồn xác định người ký và căn cứ quyền riêng. Nếu giữ, rà attribution và chú thích hiệu đính Wikisource cho chính phần này.
- **P3/P4 — Nhập môn Triết học:** xin Libero xác nhận PDF/version cụ thể, phạm vi CC BY 4.0 và nội hàm “Lưu hành nội bộ”; xác nhận giấy phép OpenStax của đúng bản nền. Cho tới lúc đó không mở rộng phạm vi phân phối.
- **P3 — Đọc sách thông minh:** cung cấp/re-run đối chiếu 33 anchor đã lưu bằng công cụ có PDF extraction; phân loại thành khác biệt trích xuất, trình bày hoặc nội dung. Runtime PDF extraction bị chặn: Python interpreter hiện có không khởi chạy; web tool từ chối PDF quá lớn/không truy cập được. Không suy đoán 33 mục là lỗi nội dung.
- **P3/P4 — Việt Nam phong tục:** lấy scan đáng tin của bản 1915 để đối chiếu. Nếu không có, quyết định giữ phần đầu 1973 với mô tả chính xác hoặc loại paratext riêng của lần in 1973 khỏi demo sau review; không mô tả cả Reader chỉ là nguyên tác 1915.
- **La Fontaine:** không cần thêm việc để ghi nhận quan hệ thư mục 1951→1928; nếu muốn tuyên bố tương đương nội dung, cần bản 1928 và so sánh có lưu dấu.
- **Nửa chừng xuân:** không đổi pending/approved. Bằng chứng runtime đã có từ đợt trước; lượt này chỉ đối chiếu lại source_id trong catalog. Chưa đọc trực tiếp SQLite/API vì Python/SQLite CLI khả dụng không khởi chạy được.

## Ma trận 20 tác phẩm và giới hạn đếm

20 dòng trong `provenance_matrix.jsonl` có book_id/work_id/source_id toàn văn riêng, URL và chứng cứ theo từng dòng. 12 dòng `NOT_REASSESSED` chỉ xác nhận liên kết và trạng thái nguồn có trong catalog/registry; 8 dòng còn lại giữ đánh giá provenance chi tiết, kể cả UNVERIFIED của phần tiểu sử. Số 12 VERIFIED / 5 PARTIAL / 3 UNVERIFIED từ khảo sát trước là tally lịch sử, không tự biến thành tally mới từ trạng thái `approved`. Nghiệm thu dưới đây là **nghiệm thu kỹ thuật có ngoại lệ**, không phải cấp giấy phép hoặc chứng nhận quyền của mọi tác phẩm.

## Tính toàn vẹn, Git và phạm vi

Hash trước/sau cập nhật hồ sơ phải giữ nguyên:

- catalog: `dc0482879e0efbf554175a66f8d191c75efd73d50c738dead28c17e71838a0cc`
- registry: `738e736ee523f97962e27f3ac4b64b735a47f511a04524443081d6f81064a597`
- SQLite snapshot: `7985dc5d37139203965a04616068c359176bf6ffa6dcb99720da620b74408b7f`
- snapshot manifest: `998cec92f26836eb5f60b5a558cb750ad92a00e876af171f0a4ee999bf167cfe`
- rights count: 20 metadata approved, 20 summary approved, 20 fulltext approved, 1 metadata pending, 1 summary pending.

Hồ sơ này được cập nhật cùng `openspec/changes/c45-data-quality-audit/tasks.md`; không sửa corpus, registry, rights, snapshot hoặc Reader. `git diff --check` được chạy trước/sau. Các file báo cáo bị rule hiện có `data/reports/*` trong `.gitignore` bỏ qua; không thay đổi ignore hay stage. Working tree có sẵn thay đổi khác trước lượt này, được giữ nguyên. Các giới hạn provenance về tiểu sử, bản dịch, bản in và so sánh định dạng được chấp nhận là ngoại lệ báo cáo trong phạm vi demo nội bộ, không tự biến thành VERIFIED.

## Chốt kỹ thuật C45 trên nhánh P3 — 26/11/2026

Branch: `feature/data-embedding`, HEAD `8a392e7e916a2d99c99bcfde45e64884015707aa`. Commit `72c4006cab247dbed17151407fe02366aa011dea` sửa manifest có trong lịch sử. Đã kiểm đủ 108 entry và sự tồn tại của file trên disk: **0 MISSING**. Hash raw working tree đạt **107/108**; theo quy tắc Git canonical LF đã khai báo cho file được theo dõi, hash đạt **108/108 PASS**. Trong 108 entry, hai file theo dõi có `text eol=lf` (`NOTICE.md`, `taxonomy.json`) được kiểm bằng bytes blob tại HEAD, đồng thời đối chiếu checkout sau chuẩn hóa EOL *chỉ trong bộ nhớ* với blob; 106 entry còn lại được kiểm bằng bytes gốc của file đã lưu (kể cả nguồn chỉ tồn tại cục bộ). Không coi file thiếu hoặc việc chuẩn hóa nội dung tùy ý là PASS.

| File | SHA-256 trong manifest và Git blob tại HEAD | SHA-256 bytes working tree | Kết luận |
|---|---|---|---|
| `NOTICE.md` | `bb72367dcdd0cf946b5c46138ed3af98fb67d7cae1f77412a6a8819974a74e15` | `467b80a7381f17c19dd5544607e6e46235ba0a9765d71eb053a6c5d07741aacd` | Raw checkout lệch vì 38 CRLF; blob HEAD có 38 LF, 8.989 bytes và khớp manifest. Checkout chuyển CRLF→LF trong bộ nhớ bằng đúng bytes blob: không có khác biệt nội dung khác. |

`.gitattributes` ở HEAD và working tree đều khai báo `NOTICE.md text eol=lf`; `git check-attr` xác nhận `text:set`, `eol:lf`, còn `git ls-files --eol` cho thấy `i/lf w/crlf`. `taxonomy.json` có `i/lf w/lf`, đạt cả raw và canonical. Các file nguồn không được Git theo dõi chỉ được xác minh bằng bytes gốc trên disk, không suy là có blob tại HEAD. **CORPUS MANIFEST: 108/108 PASS (canonical LF verification); raw Windows: 107/108.** Không sửa corpus hoặc manifest.

**Kết luận kiểm toán kỹ thuật: TECHNICAL CLOSURE — ACCEPTED WITH DOCUMENTED EXCEPTIONS.** Phần kiểm toán Phase 1 đã nghiệm thu kỹ thuật có ngoại lệ: 24 PASS / 7 WARNING / 0 FAIL / 2 UNVERIFIED, 33 checks, 9 exceptions (NOT_RERUN). Phần Reader Phase 2 có ma trận 20 tác phẩm, gồm 8 ca phân tích sâu (3 VERIFIED theo phạm vi ghi, 4 PARTIAL, 1 UNVERIFIED) và 12 ca kiểm kê NOT_REASSESSED; kiểm Reader và SQLite đã đạt từ lượt trước (NOT_RERUN). Các ngoại lệ provenance vẫn mở đúng phạm vi và không được tính PASS; kết luận kỹ thuật này dành cho demo nội bộ, không cấp quyền phân phối công khai.

Ngày 26/11/2026, **người dùng thông báo** nhóm đã xác nhận P3/P1 nghiệm thu Phase 1 (OpenSpec 7.1), P3/P4 nghiệm thu Phase 2 (7.2) và chấp nhận các ngoại lệ đã ghi trong phạm vi BTL/demo nội bộ. Đây là xác nhận được chuyển đạt qua người dùng, **không phải biên bản review hoặc chữ ký độc lập đính kèm**. Theo phạm vi nghiệm thu này, C45 được đóng về kỹ thuật; các checkbox có tiêu chí rộng hơn bằng chứng vẫn mở và không được coi PASS. Sai lệch raw checkout Windows được công bố rõ; nếu quy trình bàn giao sau này bắt buộc hash trực tiếp bytes checkout, cần khôi phục LF an toàn ở checkout rồi kiểm lại. Các mục API/browser ngoài phạm vi audit chỉ kiểm khi tích hợp demo; không kết luận quyền phát hành công khai.

Hồ sơ kết thúc chỉ sửa báo cáo C45 và `tasks.md`. Git có thay đổi trước đó ở `.gitignore`, `.gitattributes`, script/dataset C41; các thay đổi ngoài C45 và stash dự phòng được giữ nguyên.
