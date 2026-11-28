# C31/C33 — Code và kiểm thử bằng dữ liệu tổng hợp

Phần có thể chuẩn bị review riêng gồm `api/src/evaluation/`, CLI
`api/scripts/evaluate_recommendation.py`, thay đổi selector trong
`api/src/services/recommendation.py` và năm file `test_recommendation_*` liên quan
evaluation/review/revision/joint review/freeze code. Không kèm nhãn, summary,
rankings, protocol phê duyệt thật hoặc kết quả test chính thức.

## Kiểm thử

Dùng interpreter `.venv/Scripts/python.exe` của dự án và dependencies backend/
pipeline theo README. Trong PowerShell tại thư mục gốc:

```powershell
$env:PYTHONPATH = 'api;pipeline'
.venv/Scripts/python.exe -B -m pytest api/tests/test_recommendation_evaluation.py api/tests/test_recommendation_freeze_code.py api/tests/test_recommendation_joint_review.py api/tests/test_recommendation_review.py api/tests/test_recommendation_revision.py -q
```

Các test tái sử dụng `api/tests/recommendation_fixture.py` và tạo dữ liệu kỹ thuật
trong `tmp_path`; không cần release đánh giá nội bộ. Các ca metric/test-use trong
fixture kiểm tra công cụ, không phải lượt đo test chính thức trên dữ liệu thật.
Fixture scenario có 20 tình huống kỹ thuật, chia 8/12, seed tổng hợp 1–3 sách.

## Ranh giới dữ liệu

Không đưa các release, nhãn, phiếu chấm, evidence, báo cáo phân tích có trích nội
dung sách hoặc hồ sơ người duyệt vào PR public khi chưa xác minh quyền chia sẻ.
Gói nội bộ phải giữ đầy đủ đường dẫn và byte để validator/freeze tiếp tục kiểm
chứng được; không sửa code đã khóa hoặc hồ sơ chính thức để tách PR.

Không chạy CLI đánh giá chính thức để smoke test. Những kiểm tra fixture ở trên
đủ để kiểm thử hành vi kỹ thuật; chúng không chứng minh chất lượng gợi ý hay C40.
