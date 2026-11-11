# P4 — Báo cáo nghiệm thu tuần 1

Ngày kiểm chứng: 10/11/2026 (Asia/Saigon). Phạm vi phiên làm việc: C05, phần thành phần C14 và giao diện C18 theo các lựa chọn người dùng đã xác nhận.

## 1. Phạm vi và phiên bản

- Phân công: [02_Cong_viec](https://docs.google.com/spreadsheets/d/1cHc0yKiawuWja51Nftdvb0M-tIfRGtkdWiHmpcCWgww/edit#gid=96043016), đọc lại các hàng 10, 16, 19, 23 và H03/H04 ngày 10/11/2026. Không cập nhật trạng thái trên Sheet.
- Tài liệu gốc: `documents/SPEC.md` v0.1 ngày 06/11/2026; hash bản làm việc `7f4a97bf28972fabc8f5409c2f59d539e09093cfc07705f8075da1298ea3eecc`.
- Đặc tả task: [C05](C05.md), [C14](C14.md), [C18](C18.md).
- Base commit: `b37287e166c718356ecd494fd4ff996f11ebbfae`. Lượt kiểm chứng dùng các thay đổi chưa commit; không coi base commit là phiên bản đã chứa thay đổi. Hash mã/tài liệu và cấu hình build được ghi tại `evidence/source-manifest.json`.
- Môi trường: Windows 11 x86_64, Python 3.14.8; môi trường FAISS riêng `.venv`: faiss-cpu 1.15.1, NumPy 2.5.4, pytest 9.2.0; Node 24.21.0, npm 11.19.0, React 18.3.1, Vite 5.4.21. Browser test: Playwright Python 1.60.0 + Edge headless, phiên bản browser trong báo cáo JSON.
- Vector là fixture kỹ thuật, không chạy E5 và không có bàn giao C11 thật. Cấu hình E5 được kiểm tra là cấu hình khai báo theo SPEC, không phải bằng chứng đã sinh embedding thật.
- Các snapshot ID `c14-fixture-v1`, `reader-fixture-v1`, `browser-fixture-v1` chỉ thuộc dữ liệu kiểm thử. Không thay active pointer hoặc tạo snapshot phục vụ API.
- Hồ sơ OpenSpec local: `p4-w01-c05-faiss-smoke`, `p4-w01-c14-book-index`, `p4-w01-c18-reader`.

## 2. Kết quả từng task

| Task | Đã triển khai | Đã kiểm chứng | Kết luận trong phạm vi tuần 1 |
| --- | --- | --- | --- |
| C05 | Công cụ IndexFlatIP lưu/nạp/query và báo cáo JSON | 5 kiểm thử pytest; smoke thực 5 vector × 384, 3 query, 12 checks đạt | Đạt công cụ FAISS bằng vector giả theo C05 |
| C14 | Hàm kiểm tra vector, builder/loader, mapping, search/get_vector | 28 kiểm thử FAISS thật trên fixture; ví dụ thành phần lưu/nạp được | Đạt phần mã/thành phần và fixture; **chờ C11 để nghiệm thu tích hợp P3 thật** |
| C18 | Type theo SPEC, client đọc, mục lục/chương/Trước-Sau, lỗi/retry, chống response cũ, fixture chỉ dev | TypeScript + production build; **12/12 browser checks đạt**, ảnh 390/1280 | Đạt trình đọc cơ bản với fixture/mock; API và toàn văn thật thuộc C25/C29 chưa nghiệm thu |

Chưa kết luận hoạt động chung C01/C06/C19 hoặc việc hỗ trợ các thành viên đã hoàn thành; cần bằng chứng phối hợp riêng. Không ghi trạng thái hoàn thành thay P1/P2/P3.

## 3. Đối chiếu SPEC → task → kiểm chứng

| Căn cứ SPEC | Task / tiêu chí | Kết quả thực tế | Bằng chứng |
| --- | --- | --- | --- |
| 10.1/10.4 | C05-AC01–03 | FAISS thực, float32/L2/384; điểm khớp NumPy; round-trip giữ kết quả | [smoke report](evidence/c05-smoke.json), [5 pytest](evidence/c05-pytest.txt) |
| 16.2 | C05-AC04–05 | Phân biệt fixture; output cũ không bị ghi đè, kiểm tra thất bại trả exit khác 0 | Cùng báo cáo và log trên |
| 3, 9.3, 10.4 | C14-AC01–02 | Từ chối sai vector/ID/hash/model; mapping liên tiếp/duy nhất; lấy đúng bản sao vector | [28 pytest](evidence/c14-pytest.txt), [component report](evidence/c14-component.json) |
| 10.2/10.4 | C14-AC03 | Ranking so NumPy; hòa score chính xác theo book_id, không làm tròn | Cùng log C14 |
| 3, 14.6; một phần N06/N08 | C14-AC04–05 | Loader từ chối hash/row/ID/snapshot/metric/count/model hỏng; từ chối build đè | Cùng log C14; chưa nghiệm thu atomic activation toàn hệ thống |
| 16.2 | C14-AC06 | Báo rõ `real_p3_integration=false`, `full_snapshot=false` | [component report](evidence/c14-component.json) |
| 7.2, 12.4, 13.4 | C18-AC01–02 | Chương đầu và Trước/Sau hoạt động; URL giữ chapter và snapshot | [browser report](evidence/c18-browser.json) |
| 13.6; phần đọc E2E-09 | C18-AC03–04 | Retry cục bộ không tải lại mục lục/QA; response cũ không ghi đè; đổi sách bỏ nội dung cũ | Cùng browser report; không tuyên bố E2E-09 đầy đủ vì chưa có QA |
| 13.4; phần N07 | C18-AC05 | Bàn phím, mục lục thu/mở, nút ≥44px và không tràn ngang tại 390/1280 | [desktop](evidence/c18-desktop-1280.png), [mobile](evidence/c18-mobile-390.png), browser report |
| 16.2, phần N03 | C18-AC06 | Không có request QA; fixture chỉ dev và được bỏ khỏi bundle production | Browser report và [build log](evidence/c18-build.txt) |
| 12.4 | C18-AC07 | Response schema cũ, sai book và response không phải JSON bị chặn; nguồn cũ 404 không tự đổi active | Browser report |

Kết quả browser cụ thể và số bài đạt lấy từ JSON của lượt chạy cuối. Không suy rộng ra chất lượng AI hoặc API backend thật.

## 4. Lệnh và bằng chứng tái chạy

- C05: từ `pipeline`, `../.venv/Scripts/python.exe -B -m pytest tests/test_faiss_smoke.py -q --basetemp=../openspec/tmp/c05-pytest -p no:cacheprovider` → exit 0, 5 passed.
- Smoke: `../.venv/Scripts/python.exe -B -m ai_library.faiss_smoke --output-dir ../openspec/evidence/c05` → exit 0, 12 checks true. Dùng thư mục mới khi chạy lại.
- C14: từ `pipeline`, `../.venv/Scripts/python.exe -B -m pytest tests/test_book_index.py -q --basetemp=../openspec/tmp/c14-pytest -p no:cacheprovider` → exit 0, 28 passed.
- Python dependencies: `pip install --no-index -r pipeline/requirements-faiss.txt` xác nhận phiên bản đã có; `pip check` không phát hiện dependency hỏng. [Freeze môi trường](evidence/python-faiss-environment.txt).
- Web: từ `web`, `npm run build` → exit 0; TypeScript và Vite qua. [package-lock](../../../web/package-lock.json) lưu dependency đã cài.
- Browser: chạy dev localhost:3000 và production preview localhost:4173, rồi từ repo `python -B web/tests/check_reader_browser.py`. Dùng API mock/fixture, Edge thật; kết quả tại JSON.
- OpenSpec: cả ba change qua `openspec validate <change> --strict`; hồ sơ giữ local, chưa archive thay cho việc tích hợp thật.

## 5. Bàn giao

| Sản phẩm | Bên nhận | Vị trí | Trạng thái tiếp nhận |
| --- | --- | --- | --- |
| Công cụ thử FAISS | P3/P1/P2 | `pipeline/ai_library/faiss_smoke.py`, C05.md | Có mã/lệnh/bằng chứng; chưa xác nhận người nhận đã chạy |
| FAISS builder/loader + vector access | P3/P1/P2 | `pipeline/ai_library/book_index.py`, C14.md | Có helper và fixture; chờ hợp đồng dữ liệu C11 thật |
| Trình đọc cơ bản | P3/P2 và P4 tuần 2 | `web/src/pages/ReaderPage.tsx`, readerClient, C18.md | Chạy fixture; chờ API thật |

## 6. Xung đột, quyết định và phần chưa đạt

1. **C14:** người dùng chọn làm hàm NumPy/book_id/model config và fixture trước, bám cấu trúc vector SPEC. SPEC chưa chốt định dạng tệp nguồn P3; `vectors.npy + mapping JSONL + metadata JSON` chỉ là đề xuất, chưa áp đặt hoặc làm adapter. C11 thật chưa có trong repo.
2. **C18:** người dùng chọn sửa frontend theo SPEC 12.4, dùng fixture dev và giữ API thật ở C25 tuần 2. Type backend và frontend cũ đặt text/paragraphs ở response ngoài chapter; SPEC đặt trong chapter. Frontend đã sửa; backend/schema ở `api/src/schemas/reader.py` và routes đọc còn phải sửa trong **C25, chính P4**. Chưa có bằng chứng quy trách nhiệm tác giả mã khung.
3. **Build:** người dùng đồng ý bỏ 3 khai báo không dùng ở Header/ExplorePage. Không thay hành vi các trang đó.
4. Môi trường sandbox chặn ensurepip/esbuild/pytest temp và browser subprocess; đã chạy lại các thao tác cần thiết với quyền phù hợp. Docker CLI có nhưng daemon chưa chạy; chưa nghiệm thu Docker/VM/Linux.
5. `npm install` báo 2 cảnh báo dependency (1 moderate, 1 high). Chưa nâng cấp hoặc chạy audit fix vì nằm ngoài thay đổi đã chốt; cần đánh giá riêng trước triển khai công khai. Local dev/preview chỉ bind 127.0.0.1.
6. Chưa nghiệm thu chất lượng search/recommendation, 200–300 sách, 20 toàn văn, RAG/citation, SLA tải, activation/rollback hoặc toàn hệ thống.

## 7. Kết luận

Phần mã C05/C14 và trình đọc cơ bản C18 đã có kiểm chứng kỹ thuật bằng fixture. C14 còn chờ vector P3 thật; API/schema backend đọc thuộc C25 vẫn chưa hoàn tất. Đây là nghiệm thu phần việc P4 tuần 1 trong phạm vi đã thống nhất, **không phải xác nhận đạt đầy đủ SPEC hoặc tích hợp cuối tuần của cả nhóm**.

Ảnh, log, JSON và manifest nguồn nằm trong `evidence/`; không chứa API key hay toàn văn sách thật. Không dùng đường dẫn OpenSpec local làm bằng chứng duy nhất.

## 8. Kiểm chứng tích hợp PR #3 — 11/11/2026

Các mục 1–7 và bằng chứng trực tiếp trong `evidence/` ghi nhận lượt 10/11. Phần này ghi riêng lượt gộp feature `7fcaaaf0c763d6fab855b33b6a2e4fa77e061eda` với develop `43fd3be95c57dba8cbb8df2383f643de0fcea7fe`, theo gói người dùng đã duyệt. Không thay thế kết quả lịch sử hoặc suy ra API/vector thật đã nghiệm thu.

### Thay đổi đã đối chiếu

- Giải quyết 5 conflict Git: `web/package-lock.json`, `App.tsx`, `Header.tsx`, `ExplorePage.tsx`, `ReaderPage.tsx`; CSS/type tự gộp vẫn được review theo SPEC.
- Giữ nguyên lockfile feature, Header/Explore và khung demo/accessibility develop, Reader C18 và validator/transport. App đồng bộ pathname/query/snapshot, kể cả Back/Forward chỉ đổi query.
- Tách type nguồn demo/import khỏi API BookSource; chuẩn hóa mock chương theo SPEC 12.4 và offset Unicode theo 9.4. Nguồn C02 giữ trạng thái ban đầu; không thêm toàn văn.
- Giữ hai chế độ độc lập: danh mục C02 qua demo adapter, Reader qua API riêng hoặc fixture dev bật chủ động; không fallback ngầm. Link thử Reader trong DemoPanel mở đúng snapshot chương tự viết.
- Không sửa SPEC, data, pipeline hoặc API backend trong lượt tích hợp này. C05/C14 không chạy lại vì mã không đổi; chưa có nghiệm thu P3/API thật mới.

### Kết quả thực chạy

| Căn cứ SPEC | Kiểm chứng | Kết quả | Bằng chứng |
| --- | --- | --- | --- |
| 2.1, N08 phần frontend | `npm ci` với lock feature; `npm run build` | exit 0; TypeScript và production build đạt | [cài dependency](evidence/pr3-integration/npm-ci.txt), [build](evidence/pr3-integration/build.txt) |
| 9.4, 12.3–12.4, 13.4–13.5 | `node scripts/check-demo.mjs` | exit 0; 20 metadata C02 giữ quyền nguồn, không có toàn văn; mock chương nested và offset Unicode, route/layout/storage đạt | [checker demo](evidence/pr3-integration/demo-check.txt) |
| 12.4, 13.4/13.6, phần đọc E2E-09 | 12 browser checks C18 trên mã gộp | **12/12 đạt** bằng authored fixture/API mock | [C18 browser](evidence/pr3-integration/c18-browser.json) |
| 13.5 | Query-only snapshot, Back/Forward, Header href/seed count | đạt; URL ưu tiên storage, không ghi đè snapshot lưu của phiên thật | [6 integration checks](evidence/pr3-integration/pr3-integration-browser.json) |
| N07, 13.4 | C02 catalog/detail/Header/skip-link ở 390/1280, nút Đọc disabled, chọn seed, tìm kiếm minh họa | đạt, không tràn ngang; quyền pending hiển thị đúng | Cùng integration report; [mobile detail](evidence/pr3-integration/c02-detail-390.png), [desktop detail](evidence/pr3-integration/c02-detail-1280.png) |
| N03, 12.4 | Tách storage/demo/reader fixture; Reader không fallback demo khi API lỗi; production không chứa catalog/fixture | đạt, không gọi QA/provider thật | Cùng integration report |

Hai bộ browser tổng cộng **18/18 checks đạt**; không quy đổi thành điểm chất lượng AI. Môi trường Python 3.14.8, Playwright 1.60.0, Edge `157.0.4341.46`, Node 24.21.0/npm 11.19.0. Hash nguồn, lock và assets của lượt kiểm chứng trước commit nằm trong [source manifest tích hợp](evidence/pr3-integration/source-manifest.json).

Review chéo giữa các agent phần App/UI và type/demo không phát hiện lỗi mới chặn tích hợp. Đã xem ảnh Reader/C02 ở 390/1280. Bằng chứng mới nằm trong thư mục riêng; không ghi đè các ảnh/log/manifest 10/11.

### Giới hạn còn giữ

- Checker chủ động gây lỗi `storage unavailable (test)` để kiểm tra fallback; cảnh báo này là tình huống kiểm thử, checker kết thúc exit 0.
- `npm ci` vẫn báo hai cảnh báo dependency đã biết (1 moderate, 1 high); không nâng dependency hay chạy audit fix trong gói này.
- C02 chỉ metadata và nguồn pending; fixture Reader là văn bản tự viết. Chưa nghiệm thu API C25/C29, vector P3 thật, QA/citation, Docker/VM, triển khai công khai hoặc toàn bộ SPEC.
- Hồ sơ OpenSpec `p4-w01-pr3-integration` giữ local; báo cáo và evidence này đủ độc lập để review PR.
