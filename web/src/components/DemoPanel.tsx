import { getScenario, scenarioKey } from '../services/demo';

import { withSnapshot } from '../services/navigation';

export function DemoPanel() {
  return (
    <aside className="demo-panel app-container" aria-label="Chế độ kiểm thử C04">
      <p><strong>Demo với dữ liệu C02</strong> · Dùng để kiểm thử giao diện, chưa chạy AI. Quyền sử dụng hiển thị theo từng nguồn.</p>
      <label htmlFor="demo-scenario">Trạng thái thử </label>
      <select id="demo-scenario" value={getScenario()} onChange={e => {
        try { sessionStorage.setItem(scenarioKey, e.target.value); window.location.reload(); }
        catch { alert('Trình duyệt cần cho phép sessionStorage để đổi trạng thái thử.'); }
      }}>
        <option value="normal">Bình thường</option>
        <option value="slow">Tải chậm (2,5 giây)</option>
        <option value="empty">Không có kết quả</option>
        <option value="error">Lỗi kết nối</option>
      </select>
      <p style={{ marginTop: 12 }}>
        <a href={withSnapshot('/read/SLB_B0001/chuong-minh-hoa')}>Kiểm tra trang tạm Reader</a>
        {' '}· ID chương chỉ minh họa đường dẫn, chưa có nội dung đọc.
      </p>
    </aside>
  );
}
