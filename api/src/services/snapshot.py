"""Resolve one immutable, read-only catalog handle per C25 request."""

import json
from contextlib import contextmanager
from pathlib import Path

from ai_library.classroom_demo import check_demo_path
from src.config import settings
from src.services.catalog import CatalogError, ID_PATTERN, check_id, open_catalog


class SnapshotService:
    def demo_snapshot_dir(self, snapshot_id: str | None) -> Path:
        configured = settings.demo_snapshot
        if configured:
            path = Path(configured).absolute()
            try:
                check_demo_path(path)
                if (path.resolve().is_relative_to(settings.snapshot_path.resolve())
                        or path.is_symlink() or not ID_PATTERN.fullmatch(path.name)):
                    raise ValueError("Đường dẫn snapshot demo không hợp lệ")
            except (OSError, ValueError, RuntimeError) as exc:
                raise CatalogError(503, "service_unavailable", "Danh mục demo chưa sẵn sàng") from exc
            if snapshot_id in (None, path.name) and path.is_dir():
                return path
            if snapshot_id is not None:
                raise CatalogError(404, "resource_not_found", "Phiên bản dữ liệu không còn được phục vụ")
        raise CatalogError(503, "service_unavailable", "Danh mục demo chưa sẵn sàng")

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
    def open_catalog(self, snapshot_id: str | None = None, *, allow_demo: bool = True, filter_ai_sources: bool = False):
        if snapshot_id is not None:
            check_id(snapshot_id, "snapshot_id")
        if allow_demo and settings.demo_snapshot is not None:
            directory = self.demo_snapshot_dir(snapshot_id)
            with open_catalog(directory, directory.name, classroom_demo=True, filter_ai_sources=filter_ai_sources) as handle:
                yield handle
            return
        sid = snapshot_id if snapshot_id is not None else self.active_snapshot_id
        if sid is None:
            raise CatalogError(503, "service_unavailable", "Danh mục chưa sẵn sàng")
        directory = self.get_snapshot_dir(sid)
        if directory is None:
            if snapshot_id is not None:
                raise CatalogError(404, "resource_not_found", "Phiên bản dữ liệu không còn được phục vụ")
            raise CatalogError(503, "service_unavailable", "Danh mục đang hoạt động chưa sẵn sàng")
        with open_catalog(directory, sid, filter_ai_sources=filter_ai_sources) as handle:
            yield handle

    def is_catalog_ready(self) -> bool:
        try:
            with self.open_catalog():
                return True
        except CatalogError:
            return False

    def is_search_ready(self) -> bool:
        """Search giữ service C12/C16 và encoder C08 từ develop."""
        from src.services.search import search_service
        return search_service.is_ready()

    def is_recommend_ready(self) -> bool:
        """Validate the actual C13 serving source; encoder readiness is combined by health."""
        from src.services.recommendation_snapshot import load_recommendation_snapshot
        try:
            load_recommendation_snapshot()
            return True
        except CatalogError:
            return False

    def is_rag_ready(self) -> bool:
        """rag_ready cần catalog, encoder, ít nhất một chỉ mục đoạn, khóa Gemini."""
        if settings.demo_snapshot is not None or not self.is_catalog_ready():
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

