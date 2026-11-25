# Chốt C41 Batch 1 — P3, ngày 23/11/2026

**Batch 1 hoàn thành cho demo nội bộ trên localhost tại Việt Nam: 4 tác phẩm, 43 mục đọc, 6.387 đoạn. Tiến độ toàn C41 là 4/20; chưa mở Batch 2/3.** Đây là nghiệm thu kỹ thuật của P3, không phải xác nhận của P4 hoặc phê duyệt phát hành công khai.

## Quyết định owner

P3 xác nhận trực tiếp ngày 23/11/2026:

> Tớ xác nhận approval Reader cho hai nguồn metadata/summary của Con nhà nghèo trong phạm vi demo nội bộ.

| Nguồn | Source ID |
|---|---|
| Metadata | R_8dad32a8-e983-405c-83df-67a645c8c225 |
| Summary | R_6e91f1a2-4f6e-447b-ab9a-f300ad5cd65b |

`p3_owner_approval.json` ghi `approved_by=P3`, `approval_date=2026-11-23`, phạm vi Reader metadata/summary internal demo localhost Việt Nam, dẫn chiếu xác nhận owner và `automated_review_tool=Codex`. Quyết định liên kết đúng book/work/source IDs, hash bản ghi nguồn, catalog và hồ sơ kiểm tra tự động; metadata/summary khớp bản đã kiểm tra. Ngày được ghi ở độ chính xác ngày do owner xác nhận, không tạo timestamp duyệt giả.

Không mở rộng sang phát hành công khai, phân phối bản sao, ảnh bìa hoặc quyền fulltext mới; không tạo giấy phép bên thứ ba. Hồ sơ fulltext riêng giữ nguyên. P3 là người xác nhận hiện tại; Codex là công cụ kiểm tra, không gán lại danh tính review lịch sử và không ghi P4 đã nghiệm thu.

## Bằng chứng nghiệm thu

| Hạng mục | Kết luận |
|---|---|
| Import / SQLite / loader | PASS — 4 book / 4 work / 43 mục / 6.387 đoạn |
| SQLite integrity / foreign keys | PASS — integrity OK, 0 lỗi FK |
| ASGI thật và HTTP TCP Uvicorn | PASS — cả bốn tác phẩm; 43 mục hợp lệ 200; nội dung, ID, thứ tự và offsets 6.387 đoạn khớp; ID sai 404 |
| Chính sách nguồn | Negative policy ASGI không phục vụ chương khi thiếu reviewer/phạm vi; không bỏ validator |
| Pytest Reader/policy | 62/62 PASS |
| Node dataset | 4/4 PASS |
| Frontend TypeScript/build | PASS |
| C42 regression | PASS — 28 mục / 4.301 đoạn; C42 nguyên vẹn |
| Browser E2E | ENVIRONMENT_BLOCKED — Edge đóng ngay khi Playwright launch; chưa chạy UI assertions |

Chỉ bổ sung hồ sơ owner liên kết ngoài dataset/snapshot; dữ liệu loader sử dụng không đổi. Đã đối chiếu lại 125 hash bảo vệ với hồ sơ self-acceptance, đều khớp. Vì vậy tái sử dụng bằng chứng kỹ thuật nêu trên, không dựng lại snapshot hoặc chạy lại pytest/HTTP/E5/FAISS/C45. Hash các file bằng chứng được lưu trong `closure_validation.json`; OpenSpec strict được chạy lại sau cập nhật tiến độ.

Bằng chứng gốc: `../c41-batch1-self-acceptance-20261123/summary.md`, `verification.json`, `http_tcp.json`, `final_status.json`; regression tại `../c41-reader-approval-20261123/c42_regression.json`. Các trạng thái NOT_RECORDED trong báo cáo cũ phản ánh thời điểm trước xác nhận P3; được bổ sung bởi quyết định hiện tại, không sửa lịch sử báo cáo.

Health HTTP từng trả 200 nhưng readiness false vì kiểm thử dùng snapshot_id riêng, không đổi active pointer; không kết luận toàn hệ thống sẵn sàng từ endpoint này.

## Trước demo

- Kiểm tra giao diện thật trên môi trường chạy được browser: ít nhất một sách mới và một sách C42; mục lục, chuyển chương, cuộn và UI lỗi.
- Xác nhận cấu hình demo trỏ đúng snapshot C41 đã kiểm chứng qua quy trình triển khai riêng; lượt này không đổi active snapshot.
- Giữ phạm vi localhost Việt Nam; đánh giá lại quyền và phạm vi nếu dự định phát hành công khai hoặc đổi nội dung/nguồn.

Không còn blocker approval P3 cho hai nguồn trong phạm vi đã xác nhận. Browser E2E vẫn là giới hạn cần hoàn tất trước demo. Có thể lập kế hoạch mở rộng sau Batch 1; lượt này dừng tại chốt bốn tác phẩm, không triển khai thêm.

## Phạm vi file

Tạo `p3_owner_approval.json`, `closure_validation.json`, `summary.md` trong thư mục báo cáo này; cập nhật `openspec/changes/c41-reader-fulltext20/tasks.md`. Không sửa catalog, source manifest, hồ sơ review tự động, nội dung/ID/hash/rights_status, snapshot C41/C42/r8 hoặc C45. Không stage, commit hoặc push.
