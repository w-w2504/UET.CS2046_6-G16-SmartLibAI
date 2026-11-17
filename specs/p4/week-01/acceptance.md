# P4 — Nghiệm thu tuần 1

Cập nhật hồ sơ ngày 18/11/2026. Phạm vi: C05, thành phần C14 và Reader C18; C14 đã bổ sung kiểm chứng E5 thật tái tạo cục bộ ngày18/11; chưa nghiệm thu toàn hệ thống.

## Căn cứ và bàn giao

- [SPEC gốc](../../../documents/SPEC.md), các mục 3.2, 9.3–9.4, 10.1/10.2/10.4, 12.4, 13.4–13.6, N06/N07/N08 và 16.2 theo phạm vi từng task.
- [C05](C05.md), [C14](C14.md), [C18](C18.md); chính P4, giữ phụ thuộc vector C11 của P3 và API/toàn văn C25/C29 tuần 2.
- [PR #3](https://github.com/w-w2504/UET.CS2046_6-G16-SmartLibAI/pull/3) đã merge vào develop, merge commit `69ffdd5d41ade0f5bce9f870963067906eb1e0ac`. Merge PR không tự xác nhận dữ liệu thật hoặc toàn bộ SPEC đạt.
- Lượt 10–11/11 dùng SPEC v0.1 có SHA-256 bản làm việc `7f4a97bf28972fabc8f5409c2f59d539e09093cfc07705f8075da1298ea3eecc`. Nền kiểm tra mới ngày 15/11 là develop `bc255061a7502a5020c1426a0d38f7a2bc606bc0`, SPEC bổ sung mục 3.2, SHA-256 `d0c47a8bdae1363f85c5fe47f017567a08a845460a1b79bffb9de27655264e09`.

## Kết quả đã kiểm chứng trước ngày 15/11

| Task / căn cứ SPEC | Đầu vào và thao tác | Kết quả thực | Giới hạn |
| --- | --- | --- | --- |
| C05 — 10.1/10.4, 16.2 | 5 vector fixture float32/L2/384, 3 query; xây IndexFlatIP, so NumPy, lưu và nạp lại | Ngày 10/11: 5 pytest và 12 kiểm tra smoke đạt | Chỉ công cụ FAISS; không sinh E5 hoặc đo chất lượng AI |
| C14 — 9.3, 10.2/10.4, phần N06/N08 | Vector/ID/hash/model fixture; builder/loader/mapping, get_vector bản sao, score giảm dần và hòa theo book_id; dữ liệu hỏng bị từ chối | Ngày 10/11: 28 pytest đạt | Thành phần index, chưa có bundle vector P3 thật/C11 hoặc snapshot phục vụ đầy đủ |
| C18 — 12.4, 13.4–13.6, phần đọc E2E-09 | Chương tự viết và API mock: mục lục/Trước-Sau, snapshot, timeout/retry riêng, bỏ response cũ, từ chối schema cũ, fixture chỉ dev | Ngày 10/11: build và 12/12 browser checks đạt | Chưa nghiệm thu API C25/toàn văn thật C29, QA hoặc citation |
| C18 tích hợp — N07, 13.4–13.6 | Feature `7fcaaaf` gộp develop `43fd3be`, mã tích hợp `07d60e0`; C02 metadata và Reader fixture độc lập; query/history/Header/storage, 390/1280, production không chứa catalog/fixture | Ngày 11/11: npm ci, checker demo, build, 12/12 C18 và 6/6 integration checks đạt | C02 tại lượt chạy chỉ metadata với nguồn pending; search/rec demo chưa là thuật toán AI |

Snapshot kiểm thử: `c14-fixture-v1`, `reader-fixture-v1`, `browser-fixture-v1`; không thay active pointer. E5 chỉ kiểm metadata khai báo theo SPEC, không chứng minh đã chạy model/tokenizer thật.

Môi trường đã dùng: Windows 11 x86_64; Python 3.14.8, faiss-cpu 1.15.1, NumPy 2.5.4, pytest 9.2.0; Node 24.21.0, npm 11.19.0, React 18.3.1, Vite 5.4.21. Browser: Playwright Python 1.60.0; Edge 157.0.4341.42 ngày 10/11 và 157.0.4341.46 ngày 11/11.

## Lệnh kiểm chứng lại trên nền mới

Từ `pipeline`, dùng Python có các dependency FAISS đã cài:

```powershell
../.venv/Scripts/python.exe -B -m pytest tests/test_faiss_smoke.py tests/test_book_index.py -q -p no:cacheprovider
../.venv/Scripts/python.exe -B -m ai_library.faiss_smoke --output-dir <new-temp-dir>
```

Từ `web` chạy `npm ci`, `node scripts/check-demo.mjs` và `npm run build`. Sau khi mở dev :3000, demo :3001, production preview :4173, chạy từ repo:

```powershell
python -B web/tests/check_reader_browser.py
python -B web/tests/check_pr3_integration.py
```

Hai script giữ lần lượt 12 và 6 tình huống; output chi tiết ở thư mục tạm ngoài P4, có thể chọn bằng `--output-dir` hoặc `SMARTLIB_EVIDENCE_DIR`. Smoke cần thư mục đích mới để tránh ghi đè. Không dùng kết quả lịch sử thay cho lượt kiểm tra trên nền mới.

**Lịch sử lượt 15/11:** khi đó đang chuẩn bị kiểm chứng lại sau cập nhật develop và thu gọn tài liệu; chưa ghi PASS hoặc số kiểm thử mới trước khi thực chạy. Nghiệm thu sẽ ghi lệnh, đầu vào, kết quả và giới hạn tại đây.

## Phụ thuộc và giới hạn còn giữ

- Lịch sử15/11: chưa có bundle/corpus mở rộng/toàn văn. Sau đó ngày18/11 người dùng đã tái tạo bundle20 bằng mã C11; kết quả bổ sung dưới đây thay trạng thái chờ bundle20 của C14. Corpus mở rộng và toàn văn vẫn chưa có.
- SPEC 3.2 mới chấp thuận metadata/tóm tắt C02 cho demo/C11 nội bộ; không bao gồm Reader, RAG hoặc phát hành công khai. Không dùng chấp thuận nội bộ để báo đã có nguồn public/toàn văn.
- C18 giữ retry riêng và transport Reader theo SPEC. Tuần 2 tiếp tục C25/C29; backend thật chạy trên fixture vẫn không phải sách thật đã nghiệm thu.
- Chưa kết luận task chung C01/C06/C19 hoặc công việc P1/P2/P3; chưa nghiệm thu search/rec theo baseline, RAG/citation, corpus200–300, 20 toàn văn, Docker/VM, SLA hoặc activation/rollback toàn hệ thống.
- Hai cảnh báo dependency npm đã biết chưa được xử lý trong PR #3; không tự nâng dependency khi thu gọn hồ sơ.
- Quyết định 15/11: báo cáo chỉ giữ căn cứ SPEC, phiên bản, input, lệnh, kết quả, giới hạn và PR; Coreach đính kèm trực tiếp PR. Việc bỏ log/ảnh khỏi thư mục P4 không miễn kiểm thử hoặc yêu cầu truy vết của SPEC 16.2.

## Kiểm chứng lại ngày18/11/2026

Đã tích hợp develop6b1e7c9 tại2989158. Toàn pipeline85 test đạt, gồm33 C05/C14; C18 browser12/12, tích hợp C02/C18 6/6, demo checker và build đạt. C29 qua backend thật với SQLite fixture6/6 đạt, tách khỏi nghiệm thu C18. Chưa nhận bundle E5 thật hoặc nguồn public mới để nghiệm thu dữ liệu.

Hồ sơ và regression tuần1 được cập nhật cùng [PR #12](https://github.com/w-w2504/UET.CS2046_6-G16-SmartLibAI/pull/12); không thay trạng thái nghiệm thu dữ liệu thật của C14.

Coreach ngày18/11: báo cáo C05/C14/C18 đã cập nhật và kiểm sau reload, đính kèm PR#12. Giữ deadline/người phụ trách/trạng thái; C14 vẫn chưa nghiệm thu bundle E5 thật.

## Nghiệm thu bổ sung C14 với E5 thật — 18/11/2026

- Căn cứ SPEC3.2/9.3/10.4/16.2, SHA-25620cad4f96ad02f7eb253c054d4b9efd341ccabd743b7c7c0dc43d7d463c72aea. Mã kiểm:2d80080; producer C11:77e39d3. Người dùng tự chạy C11; không đổi encoder/catalog/taxonomy. Python3.14.8, Torch2.10.0+cpu, Transformers4.57.6; E5 revision đúng SPEC.
- Input là bundle20 được tái tạo cục bộ từ20 metadata nội bộ đã duyệt. Manifest input SHA-256 b27b208dd56df4712dded4d2da463bbe6a35e635b76416e5de37688e034369b1; hash vectors c1cccaa34bbfa285bc26de156b1543c40bee667d8b503ce085c2808cb5da3118 và mapping3d282926dde07591ff92ffcc87ec844ff3502538ee1b8e0ed2ee5a9a4df7f65f khớp. Không báo là nhận file từ máy P3.
- Lệnh `python -B -m ai_library.c11_bundle --bundle data/reports/c11-local-20261118 --batch data/raw/sample_batch --taxonomy data/taxonomy.json --output-dir data/reports/c14-local-20261118 --snapshot c14-local-20261118 --data-kind p3_embeddings`: exit0,20 sách. Hash nguồn/artefact, cấu hình, ID/row/content_hash và float32/384/L2 đều đạt.
- Load lại bằng load_book_index:20/20 vector khớp chính xác;20 self-query đều top1 đúng. Sai số L2 tối đa8,48e-8; sai số điểm với phép tính float64 tối đa1,09e-7.
- Query thật “Cuộc sống và số phận người nông dân Việt Nam” qua E5 local đúng revision: top1SLB_B0001; thứ tự20 kết quả khớp phép tính độc lập, sai số điểm tối đa8,36e-8. Đây là smoke tích hợp, không phải điểm chất lượng AI hoặc số đo SLA/P95.
- Kết luận: **C14 đạt phạm vi thành phần với vector E5 thật**; có bộ FAISS/mapping và helper để P1/P2 dùng. Không thay active, không phát hành serving snapshot; corpus≥80 và toàn văn vẫn chưa nghiệm thu. Các ghi nhận chưa nhận bundle ở phía trên là lịch sử trước lượt kiểm này.
