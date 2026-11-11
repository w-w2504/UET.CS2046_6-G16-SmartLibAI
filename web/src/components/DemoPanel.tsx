import { getScenario, scenarioKey } from '../services/demo';

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
        <a href="/read/B_reader_fixture?reader_fixture=1&snapshot_id=reader-fixture-v1">Kiểm tra trình đọc bằng chương mẫu</a>
        {' '}· Chương mẫu tự viết, tách biệt với sách C02.
      </p>
    </aside>
  );
}
