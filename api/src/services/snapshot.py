import json
import logging
from pathlib import Path
from src.config import settings

logger = logging.getLogger("smartlib.snapshot")


class SnapshotService:
    """Quản lý trạng thái và nạp con trỏ Snapshot theo Mục 14.2 & 14.6."""

    def __init__(self):
        self._active_snapshot_id: str | None = None
        self._refresh()

    def _refresh(self) -> None:
        """Đọc con trỏ active.json từ CONTROL_ROOT."""
        active_file = settings.control_path / "active.json"
        if not active_file.exists():
            self._active_snapshot_id = None
            return

        try:
            with open(active_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._active_snapshot_id = data.get("active_snapshot_id") or data.get("snapshot_id")
        except Exception as e:
            logger.error(f"Lỗi khi đọc active.json: {e}")
            self._active_snapshot_id = None

    @property
    def active_snapshot_id(self) -> str | None:
        self._refresh()
        return self._active_snapshot_id

    def get_snapshot_dir(self, snapshot_id: str | None = None) -> Path | None:
        sid = snapshot_id or self.active_snapshot_id
        if not sid:
            return None
        snapshot_dir = settings.snapshot_path / sid
        if snapshot_dir.exists() and snapshot_dir.is_dir():
            return snapshot_dir
        return None

    def is_catalog_ready(self) -> bool:
        """catalog_ready chỉ true khi catalog và manifest nạp hợp lệ."""
        sdir = self.get_snapshot_dir()
        if not sdir:
            return False
        return (sdir / "catalog.sqlite").exists() and (sdir / "manifest.json").exists()

    def is_search_ready(self) -> bool:
        """search_ready cần catalog + encoder đúng revision + book index."""
        if not self.is_catalog_ready():
            return False
        sdir = self.get_snapshot_dir()
        if not sdir:
            return False
        return (sdir / "books.faiss").exists()

    def is_recommend_ready(self) -> bool:
        """recommend_ready có cùng phụ thuộc như search."""
        return self.is_search_ready()

    def is_rag_ready(self) -> bool:
        """rag_ready cần catalog, encoder, ít nhất một chỉ mục đoạn, khóa Gemini."""
        if not self.is_catalog_ready():
            return False
        if not settings.GEMINI_API_KEY:
            return False
        sdir = self.get_snapshot_dir()
        if not sdir:
            return False
        chunks_dir = sdir / "chunks"
        if not chunks_dir.exists() or not any(chunks_dir.glob("*.faiss")):
            return False
        return True


snapshot_service = SnapshotService()

