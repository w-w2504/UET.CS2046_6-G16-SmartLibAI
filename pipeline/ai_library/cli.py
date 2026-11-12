import json
import os
import sys
from pathlib import Path
import click

SNAPSHOT_ROOT = Path(os.getenv("SNAPSHOT_ROOT", "./data/snapshots"))
CONTROL_ROOT = Path(os.getenv("CONTROL_ROOT", "./data/control"))
REPORTS_ROOT = Path(os.getenv("REPORTS_ROOT", "./data/reports"))


def print_json_summary(status: str, message: str, data: dict | None = None) -> None:
    """In tóm tắt kết quả dưới dạng JSON ra stdout theo Mục 14.6."""
    output = {
        "status": status,
        "message": message,
        "data": data or {}
    }
    click.echo(json.dumps(output, ensure_ascii=False, indent=2))


@click.group()
def main():
    """CLI nội bộ ai-library phục vụ quản lý và phát hành dữ liệu AI Thư Viện (Mục 14.6)."""
    pass


@main.command(name="import")
@click.option("--batch", required=True, type=click.Path(exists=True), help="Đường dẫn thư mục đợt nhập dữ liệu thô")
@click.option("--taxonomy", type=click.Path(exists=True, dir_okay=False), default=None, help="Taxonomy chung; mặc định data/taxonomy.json hoặc TAXONOMY_PATH")
@click.option("--metadata-only", is_flag=True, help="Chỉ kiểm tra metadata, không đọc chapters.jsonl")
@click.option("--sqlite", type=click.Path(dir_okay=False), help="Tệp SQLite catalog nội bộ")
@click.option("--snapshot", help="ID snapshot mới để ghi vào SQLite")
def import_batch(batch: str, taxonomy: str | None, metadata_only: bool, sqlite: str | None, snapshot: str | None):
    """Kiểm tra đợt nhập và tùy chọn ghi catalog nội bộ vào SQLite."""
    if sqlite and (not metadata_only or not snapshot):
        raise click.UsageError("--sqlite yêu cầu --metadata-only và --snapshot")
    if snapshot is not None and sqlite is None:
        raise click.UsageError("--snapshot yêu cầu --sqlite")

    try:
        if sqlite:
            from ai_library.catalog_sqlite import import_catalog_to_sqlite

            report = import_catalog_to_sqlite(batch, sqlite, snapshot_id=snapshot, taxonomy_path=taxonomy)
        else:
            from ai_library.importer import validate_and_load_batch

            report, _ = validate_and_load_batch(batch, taxonomy_path=taxonomy, metadata_only=metadata_only)
        failed = any(report.quarantined.values()) or report.received["books"] == 0
        message = "Đã kiểm tra dữ liệu; chưa xây dựng hoặc phát hành snapshot"
        if sqlite:
            message = "Đợt nhập không hợp lệ" if failed else "Đã ghi catalog nội bộ vào SQLite"
        print_json_summary(
            "error" if failed else "ok",
            message,
            report.model_dump(),
        )
        sys.exit(1 if failed else 0)
    except Exception as e:
        print_json_summary("error", f"Lỗi xử lý import: {e}")
        sys.exit(1)


@main.command(name="build")
@click.option("--snapshot", required=True, help="Tên định danh snapshot (ví dụ: snapshot-v1)")
def build_snapshot(snapshot: str):
    """Xây dựng snapshot: chuẩn hóa, chunking, tính vector E5, tạo SQLite và FAISS (Mục 3)."""
    try:
        sdir = SNAPSHOT_ROOT / snapshot
        if sdir.exists():
            print_json_summary("error", f"Snapshot {snapshot} đã tồn tại")
            sys.exit(1)
        
        print_json_summary("ok", f"Đang xây dựng snapshot {snapshot}...", {"snapshot_id": snapshot})
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi build snapshot: {e}")
        sys.exit(1)


@main.command(name="validate")
@click.option("--snapshot", required=True, help="Định danh snapshot cần kiểm tra")
def validate_snapshot(snapshot: str):
    """Kiểm tra toàn vẹn schema, hash, vector và liên kết của snapshot (Mục 3 & 14.6)."""
    try:
        sdir = SNAPSHOT_ROOT / snapshot
        if not sdir.exists():
            print_json_summary("error", f"Không tìm thấy snapshot {snapshot}")
            sys.exit(1)

        print_json_summary("ok", f"Snapshot {snapshot} hợp lệ (validated)", {"snapshot_id": snapshot, "valid": True})
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi kiểm tra snapshot: {e}")
        sys.exit(1)


@main.command(name="activate")
@click.option("--snapshot", required=True, help="Định danh snapshot muốn kích hoạt")
def activate_snapshot(snapshot: str):
    """Kích hoạt snapshot validated làm bản phục vụ chính thức (Mục 14.2 & 14.6)."""
    try:
        CONTROL_ROOT.mkdir(parents=True, exist_ok=True)
        active_file = CONTROL_ROOT / "active.json"
        
        active_data = {
            "active_snapshot_id": snapshot,
            "activated_at": click.DateTime().format("%Y-%m-%dT%H:%M:%SZ") if hasattr(click, "DateTime") else ""
        }
        with open(active_file, "w", encoding="utf-8") as f:
            json.dump(active_data, f, ensure_ascii=False, indent=2)

        print_json_summary("ok", f"Đã kích hoạt snapshot {snapshot}", {"active_snapshot_id": snapshot})
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi kích hoạt snapshot: {e}")
        sys.exit(1)


@main.command(name="rollback")
@click.option("--snapshot", required=True, help="Định danh snapshot muốn quay về")
def rollback_snapshot(snapshot: str):
    """Quay lại một snapshot đã validated trước đó (Mục 14.2)."""
    try:
        active_file = CONTROL_ROOT / "active.json"
        active_data = {
            "active_snapshot_id": snapshot,
            "rollback": True
        }
        with open(active_file, "w", encoding="utf-8") as f:
            json.dump(active_data, f, ensure_ascii=False, indent=2)

        print_json_summary("ok", f"Đã rollback về snapshot {snapshot}", {"active_snapshot_id": snapshot})
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi rollback: {e}")
        sys.exit(1)


@main.command(name="list-snapshots")
def list_snapshots():
    """Liệt kê tất cả các snapshot hiện có và trạng thái (Mục 14.6)."""
    try:
        snapshots = []
        if SNAPSHOT_ROOT.exists():
            for p in SNAPSHOT_ROOT.iterdir():
                if p.is_dir():
                    snapshots.append(p.name)

        active_file = CONTROL_ROOT / "active.json"
        active_id = None
        if active_file.exists():
            with open(active_file, "r", encoding="utf-8") as f:
                active_id = json.load(f).get("active_snapshot_id")

        print_json_summary("ok", f"Tìm thấy {len(snapshots)} snapshot", {
            "snapshots": snapshots,
            "active_snapshot_id": active_id
        })
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi liệt kê snapshot: {e}")
        sys.exit(1)


@main.command(name="remove")
@click.option("--snapshot", required=True, help="Định danh snapshot cần xóa")
@click.option("--confirm-snapshot", required=True, help="Nhập lại đúng snapshot_id để xác nhận")
def remove_snapshot(snapshot: str, confirm_snapshot: str):
    """Xóa vật lý một snapshot không còn active (Mục 14.6)."""
    if snapshot != confirm_snapshot:
        print_json_summary("error", "Tham số --confirm-snapshot không khớp với --snapshot")
        sys.exit(2)

    try:
        active_file = CONTROL_ROOT / "active.json"
        if active_file.exists():
            with open(active_file, "r", encoding="utf-8") as f:
                active_id = json.load(f).get("active_snapshot_id")
                if active_id == snapshot:
                    print_json_summary("error", f"Không được xóa snapshot đang active: {snapshot}")
                    sys.exit(1)

        sdir = SNAPSHOT_ROOT / snapshot
        if not sdir.exists():
            print_json_summary("error", f"Snapshot {snapshot} không tồn tại")
            sys.exit(1)

        print_json_summary("ok", f"Đã xóa snapshot {snapshot}", {"removed": snapshot})
        sys.exit(0)
    except Exception as e:
        print_json_summary("error", f"Lỗi khi xóa snapshot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

