"""Resolve one immutable, read-only catalog handle per C25 request."""

import json
from contextlib import contextmanager
from pathlib import Path

from src.config import settings
from src.services.catalog import CatalogError, ID_PATTERN, check_id, open_catalog


class SnapshotService:
    @property
    def active_snapshot_id(self) -> str | None:
        try:
            path = settings.control_path / "active.json"
            if path.is_symlink():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            value = data.get("active_snapshot_id") or data.get("snapshot_id")
            return value if isinstance(value, str) and ID_PATTERN.fullmatch(value) else None
        except (OSError, ValueError, AttributeError):
            return None

    def get_snapshot_dir(self, snapshot_id: str | None = None) -> Path | None:
        sid = snapshot_id if snapshot_id is not None else self.active_snapshot_id
        if not isinstance(sid, str) or not ID_PATTERN.fullmatch(sid):
            return None
        root = settings.snapshot_path.resolve()
        path = root / sid
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_dir():
            return None
        return path

    @contextmanager
    def open_catalog(self, snapshot_id: str | None = None):
        if snapshot_id is not None:
            check_id(snapshot_id, "snapshot_id")
        sid = snapshot_id if snapshot_id is not None else self.active_snapshot_id
        if sid is None:
            raise CatalogError(503, "service_unavailable", "Danh mục chưa sẵn sàng")
        directory = self.get_snapshot_dir(sid)
        if directory is None:
            if snapshot_id is not None:
                raise CatalogError(404, "resource_not_found", "Phiên bản dữ liệu không còn được phục vụ")
            raise CatalogError(503, "service_unavailable", "Danh mục đang hoạt động chưa sẵn sàng")
        with open_catalog(directory, sid) as handle:
            yield handle

    def is_catalog_ready(self) -> bool:
        try:
            with self.open_catalog():
                return True
        except CatalogError:
            return False

    def is_search_ready(self) -> bool:
        return False

    def is_recommend_ready(self) -> bool:
        return False

    def is_rag_ready(self) -> bool:
        return False


snapshot_service = SnapshotService()

