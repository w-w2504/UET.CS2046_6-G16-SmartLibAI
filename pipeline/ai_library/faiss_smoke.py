"""C05: exercise real FAISS with synthetic vectors; never publishes a snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import faiss
import numpy as np

DIMENSION = 384
TOLERANCE = 1e-6


def synthetic_vectors() -> np.ndarray:
    """A fixed fixture, not E5 output or book content."""
    vectors = np.zeros((5, DIMENSION), dtype=np.float32)
    vectors[:4, :4] = np.eye(4, dtype=np.float32)
    vectors[4, :2] = 1.0
    faiss.normalize_L2(vectors)
    return vectors


def run_smoke_check(output_dir: Path) -> dict[str, Any]:
    """Save, reload and query IndexFlatIP, comparing every score to NumPy."""
    output_dir = Path(output_dir)
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise ValueError("Thư mục đầu ra phải mới hoặc rỗng; không ghi đè dữ liệu có sẵn")

    vectors = synthetic_vectors()
    queries = vectors[:3].copy()
    index = faiss.IndexFlatIP(DIMENSION)
    index.add(vectors)
    scores_before, rows_before = index.search(queries, len(vectors))
    expected_scores = queries @ vectors.T

    checks = {
        "fixture_float32": vectors.dtype == np.float32,
        "fixture_finite": bool(np.isfinite(vectors).all()),
        "fixture_normalized": bool(np.allclose(
            np.linalg.norm(vectors, axis=1), 1.0, atol=TOLERANCE, rtol=0,
        )),
        "index_shape": index.d == DIMENSION and index.ntotal == len(vectors),
        "nearest_rows": bool(np.array_equal(rows_before[:, 0], np.arange(len(queries)))),
        "all_rows_returned": all(
            np.array_equal(np.sort(row), np.arange(len(vectors))) for row in rows_before
        ),
    }
    # Do not index NumPy with invalid rows returned by a broken search.
    checks["scores_match_numpy"] = checks["all_rows_returned"] and bool(np.allclose(
        scores_before, np.take_along_axis(expected_scores, rows_before, axis=1),
        atol=TOLERANCE, rtol=0,
    ))
    checks["scores_descending"] = bool((np.diff(scores_before, axis=1) <= 0).all())
    if not all(checks.values()):
        raise RuntimeError("Kiểm chứng FAISS trước lưu thất bại: " + ", ".join(
            name for name, passed in checks.items() if not passed
        ))

    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "books.faiss"
    faiss.write_index(index, str(index_path))
    restored = faiss.read_index(str(index_path))
    scores_after, rows_after = restored.search(queries, len(vectors))
    checks.update({
        "restored_shape": restored.d == DIMENSION and restored.ntotal == len(vectors),
        "restored_metric": restored.metric_type == faiss.METRIC_INNER_PRODUCT,
        "restored_rows": bool(np.array_equal(rows_before, rows_after)),
        "restored_scores": bool(np.allclose(
            scores_before, scores_after, atol=TOLERANCE, rtol=0,
        )),
    })
    if not all(checks.values()):
        raise RuntimeError("Kiểm chứng FAISS sau nạp thất bại: " + ", ".join(
            name for name, passed in checks.items() if not passed
        ))

    report = {
        "status": "passed",
        "task_id": "C05",
        "data_kind": "synthetic_fixture",
        "claim": "faiss_roundtrip_only",
        "full_system_acceptance": False,
        "index_type": type(restored).__name__,
        "dimension": restored.d,
        "vector_count": restored.ntotal,
        "query_count": len(queries),
        "absolute_tolerance": TOLERANCE,
        "checks": checks,
        "nearest_rows": rows_after[:, 0].tolist(),
        "versions": {
            "python": platform.python_version(),
            "faiss_cpu": faiss.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
    }
    (output_dir / "smoke-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C05: kiểm chứng FAISS bằng vector giả 384 chiều")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_smoke_check(args.output_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({
            "status": "failed", "task_id": "C05", "data_kind": "synthetic_fixture",
            "message": str(exc),
        }, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
