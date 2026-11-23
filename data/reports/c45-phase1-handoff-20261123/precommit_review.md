# C45 pre-commit review

Không stage/commit trong lượt này. Commit riêng chỉ dùng các đường dẫn trong commit_manifest.json. `.gitignore` và `.gitattributes` đang modified chỉ thêm quy tắc C41, nên không đưa vào commit C45. Không lấy data/raw/c41_reader20_batch1 hoặc script/test C41.

Các báo cáo và OpenSpec C45 bị ignore: cần explicit `git add -f -- <exact-path>` ở lượt đã được cho phép stage; không sửa ignore dùng chung để lấy cả C41. Manifest ghi status/kích thước/hash từng file. Không đưa mọi báo cáo v8–v12 hay script khảo sát cũ vào commit; giữ đúng bốn baseline v12 và sáu báo cáo runtime được closure/checks_final tham chiếu.

Tái lập được kiểm bằng dependency manifest, file tồn tại/tracked và test; chưa thực hiện clean checkout Git độc lập. Root được suy từ __file__/import.meta.dirname; dùng đường dẫn repo và output mới. Absolute interpreter/cache paths trong bằng chứng cũ chỉ là chẩn đoán môi trường đã chạy, không phải cấu hình cần sao chép. Không đưa model/cache/venv vào commit. Runtime Node >=22 có --experimental-sqlite, Python và các dependencies khai báo trong pipeline/requirements-p3-demo.txt; pytest là công cụ kiểm thử cần có trong môi trường test.

Lệnh nhẹ: node --experimental-sqlite --test pipeline/tests/test_c45_phase1.mjs pipeline/tests/test_c45_review_replacements.mjs; python -B -m pytest -q -p no:cacheprovider pipeline/tests/test_importer_quarantine.py api/tests/test_eligibility.py; openspec validate c45-data-quality-audit --strict.

Lệnh tái lập closure: python -B pipeline/scripts/close_c45_phase1.py --output data/reports/<new-closure-dir>. Không chạy lại pipeline tạo embedding. Sau commit cần kiểm checkout thật và hash report dữ liệu; timestamp hoặc danh sách file bảo vệ có thể khác theo checkout.

C45 test dependencies are explicitly declared in pipeline/requirements-c45-tests.txt (includes the existing focused demo environment and pytest). Node 5/5 and OpenSpec strict PASS were rechecked during handoff; Python 28/28 evidence remains valid from closure because Python runtime/data/test source did not change. No fresh clean checkout was created.
